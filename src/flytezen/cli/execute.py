import importlib
import inspect
import os
import pathlib
import sys
import tempfile
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

import rich.syntax
import rich.tree
from dataclasses_json import dataclass_json
from dotenv import load_dotenv
from flytekit.configuration import Config as FlyteConfig
from flytekit.configuration import (
    FastSerializationSettings,
    ImageConfig,
    SerializationSettings,
)
from flytekit.remote import FlyteRemote
from hydra_zen import ZenStore, make_custom_builds_fn, to_yaml, zen
from omegaconf import DictConfig

from flytezen.cli.execution_utils import (
    check_required_env_vars,
    generate_hydra_config,
    git_info_to_workflow_version,
    random_alphanumeric_suffix,
    wait_for_workflow_completion,
)
from flytezen.logging import configure_logging

logger = configure_logging("execute")
builds = make_custom_builds_fn(populate_full_signature=True)


class ExecutionModeName(Enum):
    """
    Enumerates the possible execution modes for a workflow.

    Attributes:
        LOCAL: Represents a local execution mode, where the workflow is executed
        locally without remote registration.
        DEV: Represents a development execution mode, where the workflow is
        executed remotely for development purposes. This mode is used for
        testing workflow code changes remotely without needing to rebuild and
        push the container image so long as one with the current branch tag
        already exists.
        PROD: Represents a production execution mode, where the workflow is
        registered and executed remotely, intended for production or continuous
        integration (CI) environments. The image tag is set to the git commit
        short SHA.
    """

    LOCAL = "local"
    DEV = "dev"
    PROD = "prod"

    def __str__(self):
        return self.value


@dataclass_json
@dataclass
class ExecutionMode:
    """
    Represents the execution configuration for a workflow.

    This dataclass encapsulates settings related to the execution environment,
    including the mode of execution, container image details, and workflow
    versioning information.

    Attributes:
        name (ExecutionModeName): The execution mode, which dictates how and where the workflow is executed.
        image (str): The full name of the container image to be used in the execution, including the registry path.
        tag (str): The tag appended to the container image, usually git branch (DEV) or commit hash (PROD).
        version (str): A string representing the version of the workflow, typically including a commit hash or other identifiers.
    """

    name: ExecutionModeName = ExecutionModeName.DEV
    image: str = "ghcr.io/sciexp/flytezen"
    tag: str = "main"
    version: str = f"flytezen-main-{random_alphanumeric_suffix()}"


def execute_workflow(
    zen_cfg: DictConfig,
    package_path: str = "src",
    import_path: str = "flytezen.workflows.lrwine",
    name: str = "training_workflow",
    project: str = "flytesnacks",
    domain: str = "development",
    wait: bool = True,
    mode: ExecutionMode = ExecutionMode(),
    inputs: Dict[str, Any] = {},
) -> None:
    """
    Executes the given workflow based on the Hydra configuration. The execution
    mode is controlled by the 'mode' parameter, which is an instance of the
    ExecutionMode dataclass. This dataclass encapsulates execution configuration
    details including the execution environment name (local, dev, prod),
    container image details, and versioning information.

    The 'mode' parameter allows for the following execution environments:
    - LOCAL: Attempts to execute the workflow locally without registering it on
      the remote.
    - DEV: Executes a copy of the local workflow on the remote for development
      purposes. This mode allows for testing changes to the workflow code
      remotely without needing to rebuild and push the container image. However,
      rebuilding and pushing the image may be required for significant
      dependency changes. The workflow version is appended with a random
      alphanumeric string. This mode is intended for development purposes only
      and should not be used in production or CI environments.
    - PROD: Registers the workflow on the remote and then executes it, intended
      for production or CI environments. This mode executes the workflow against
      a container image that has been built and pushed to the registry specified
      in the ExecutionMode image. The image used is tagged with the git short
      SHA.

    In all modes, the workflow is registered with Flyte and executed. The
    function logs various informational messages, including the execution URL,
    and optionally waits for workflow completion based on the `wait` flag in the
    workflow configuration.

    Args:
        zen_cfg (DictConfig): Configuration for the execution.
        package_path (str): The path to the workflow package.
        import_path (str): The import path of the workflow function to execute.
        name (str): The name of the workflow function to execute.
        project (str): The Flyte project in which to register or execute the workflow.
        domain (str): The Flyte domain in which to register or execute the workflow.
        wait (bool): Flag indicating whether to wait for the workflow execution to complete.
        mode (ExecutionMode): An instance of ExecutionMode specifying the execution environment and settings.
        inputs (Dict[str, Any]): Inputs to the workflow function. Keys are argument names, values are the inputs.

        TODO: Dynamic configuration of `inputs` argument should be required, but it is placed
        at the bottom due to the length in printing the config.
        The parameters should be reorderd in hydra/to_yaml and this can then be moved
        to the top of the arg list and made required.

    Raises:
        Sets exit status one if an invalid execution mode is specified.
    """
    config_yaml = to_yaml(zen_cfg)
    tree = rich.tree.Tree("workflow", style="dim", guide_style="dim")
    tree.add(rich.syntax.Syntax(config_yaml, "yaml", theme="monokai"))
    rich.print(tree)

    module = importlib.import_module(import_path)
    entity = getattr(module, name)

    # https://github.com/flyteorg/flytekit/blob/dc9d26bfd29d7a3482d1d56d66a806e8fbcba036/flytekit/clis/sdk_in_container/run.py#L477
    if mode.name == ExecutionModeName.LOCAL:
        output = entity(**inputs)
        logger.info(f"Workflow output:\n\n{output}\n")
        return

    remote = FlyteRemote(
        config=FlyteConfig.auto(),
        default_project=project,
        default_domain=domain,
    )
    image_config = ImageConfig.auto(img_name=f"{mode.image}:{mode.tag}")

    if mode.name == ExecutionModeName.DEV:
        logger.warning(
            "This mode.name is intended for development purposes only.\n\n"
            "Please use 'prod' mode.name for production or CI environments.\n\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger.debug(
                f"Packaged tarball temporary directory:\n\n\t{tmp_dir}\n"
            )
            _, upload_url = remote.fast_package(
                pathlib.Path(package_path),
                output=tmp_dir,
            )
        logger.info(f"Workflow package uploaded to:\n\n  {upload_url}\n")

        serialization_settings = SerializationSettings(
            image_config=image_config,
            fast_serialization_settings=FastSerializationSettings(
                enabled=True,
                destination_dir="/root",
                distribution_location=upload_url,
            ),
        )
    elif mode.name == ExecutionModeName.PROD:
        logger.info(f"Registering workflow:\n\n\t{import_path}\n")
        serialization_settings = SerializationSettings(
            image_config=image_config
        )
    else:
        logger.error(
            f"Invalid workflow registration mode: {mode.name}. "
            "Please set the 'name' of ExecutionMode to one of the following: "
            f"{', '.join([e.value for e in ExecutionModeName])}."
        )
        sys.exit(1)

    remote.register_workflow(
        entity=entity,
        serialization_settings=serialization_settings,
        version=mode.version,
    )
    execution = remote.execute(
        entity=entity,
        inputs=inputs,
        version=mode.version,
        execution_name_prefix=mode.version,
        wait=False,
    )
    logger.info(f"Execution submitted:\n\n{execution}\n")
    logger.info(f"Execution url:\n\n{remote.generate_console_url(execution)}\n")

    if wait:
        wait_for_workflow_completion(execution, remote, logger)


def generate_workflow_inputs(
    workflow_import_path: str = "flytezen.workflows.lrwine",
    workflow_name: str = "training_workflow",
) -> Dict[str, Any]:
    module = importlib.import_module(workflow_import_path)
    workflow = getattr(module, workflow_name)

    if not callable(workflow):
        value_error_message = f"Workflow '{workflow_name}' is not callable"
        raise ValueError(value_error_message)

    inputs = {}

    for name, param in inspect.signature(workflow).parameters.items():
        param_type = param.annotation
        default = param.default

        # Check if the type is a built-in type (like int, str, etc.)
        if isinstance(param_type, type) and param_type.__module__ == "builtins":
            inputs[name] = default
        else:
            # Dynamically import the type if it's not a built-in type
            type_module = importlib.import_module(param_type.__module__)
            custom_type = getattr(type_module, param_type.__name__)

            # CustomTypeConf = builds(custom_type)
            # inputs[name] = CustomTypeConf()
            inputs[name] = builds(custom_type)

    return inputs


def main() -> None:
    """
    Main function that executes the workflow on the remote in one of two modes
    determined by "WORKFLOW_REGISTRATION_MODE":

    - In 'dev' mode, it uses the container mode.imagewith mode.tag current
      branch tag for execution. This allows executing a copy of updated local
      workflow on the remote prior to building a new image.
    - In 'prod' mode, it uses the container image with the git short SHA tag
      just after building an image. This is primarily for CI execution.

    Note this logic regarding the image tag is independent of setting domain to
    "development", "staging", "production", etc.

    The workflow version is also separately determined based on the current git
    repo name, branch, and commit SHA.
    """

    load_dotenv()

    check_required_env_vars(
        [
            "WORKFLOW_NAME",
            "WORKFLOW_PACKAGE_PATH",
            "WORKFLOW_IMPORT_PATH",
            "WORKFLOW_PROJECT",
            "WORKFLOW_DOMAIN",
        ],
        logger,
    ) or sys.exit(1)

    store = ZenStore(name="flytezen", deferred_hydra_store=False)

    store(generate_hydra_config())

    repo_name, git_branch, git_short_sha = git_info_to_workflow_version(logger)

    workflow_image = os.environ.get(
        "WORKFLOW_IMAGE",
        "localhost:30000/flytezen",
    )
    ModeConf = builds(ExecutionMode)
    local_mode = ModeConf(
        name=ExecutionModeName.LOCAL,
        image="",
        tag="",
        version=f"{repo_name}-{git_branch}-{git_short_sha}-local-{random_alphanumeric_suffix()}",
    )
    dev_mode = ModeConf(
        name=ExecutionModeName.DEV,
        image=workflow_image,
        tag=git_branch,
        version=f"{repo_name}-{git_branch}-{git_short_sha}-dev-{random_alphanumeric_suffix()}",
    )
    prod_mode = ModeConf(
        name=ExecutionModeName.PROD,
        image=workflow_image,
        tag=git_short_sha,
        version=f"{repo_name}-{git_branch}-{git_short_sha}",
    )

    mode_store = store(group="mode")
    mode_store(local_mode, name="local")
    mode_store(dev_mode, name="dev")
    mode_store(prod_mode, name="prod")

    workflow_import_path = os.environ.get("WORKFLOW_IMPORT_PATH")
    workflow_name = os.environ.get("WORKFLOW_NAME")

    # TODO: Build workflow inputs dynamically from workflow import path to allow
    #       overrides from the hydra CLI.
    #
    # WorkflowConf = builds(generate_workflow_inputs)
    #
    # The separate dependency on the workflow import path and name
    # here and in ExecutionConf prevents hydra CLI override of the workflow
    # from propagating to the dynamic instantiation of the workflow inputs.
    workflow_inputs = generate_workflow_inputs(
        workflow_import_path=workflow_import_path,
        workflow_name=workflow_name,
    )

    # For parameters marked as `NOT overridable`,
    # the value is determined by the env var
    # and cannot be overriden by the hydra CLI.
    # You can combine env vars and hydra CLI overrides
    # > WORKFLOW_NAME=wf \
    # > WORKFLOW_IMPORT_PATH=flytezen.workflows.example \
    # > flytezen \
    # > wait=false \
    # > inputs.name=flyte
    ExecutionConf = builds(
        execute_workflow,
        # package_path=os.environ.get("WORKFLOW_PACKAGE_PATH"), # Overridable
        import_path=workflow_import_path,  # NOT overridable, determines inputs
        name=workflow_name,  # NOT overridable, determines inputs
        mode=dev_mode,  # Overridable, groups dev | local | prod
        inputs=workflow_inputs,  # Overridable subcomponents, see `flytezen -h`
        # project=os.environ.get("WORKFLOW_PROJECT"), # Overridable
        # domain=os.environ.get("WORKFLOW_DOMAIN"), # Overridable
        # wait=True, # Overridable
    )

    store(
        ExecutionConf,
        name="execute_workflow",
        hydra_defaults=["_self_", {"mode": "dev"}],
    )

    store.add_to_hydra_store()

    zen(execute_workflow).hydra_main(
        config_name="execute_workflow",
        version_base="1.3",
        config_path=None,
    )


if __name__ == "__main__":
    """
    This script executes a Flyte workflow configured with hydra-zen. > flytezen
    --help.

    == Config ==
    Override anything in the config (foo.bar=value)

    _target_: flytezen.cli.execute.execute_workflow
    zen_cfg: ???
    name: training_workflow
    package_path: src
    import_path: flytezen.workflows.lrwine
    project: flytesnacks
    domain: development
    wait: true
    mode:
      _target_: flytezen.cli.execute.ExecutionMode
      name: DEV
      image: localhost:30000/flytezen
      tag: main
      version: flytezen-main-16323b3-dev-a8x
    inputs:
      logistic_regression:
        _target_: sklearn.linear_model._logistic.LogisticRegression
        penalty: l2
        dual: false
        tol: 0.0001
        C: 1.0
        fit_intercept: true
        intercept_scaling: 1
        class_weight: null
        random_state: null
        solver: lbfgs
        max_iter: 100
        multi_class: auto
        verbose: 0
        warm_start: false
        n_jobs: null
        l1_ratio: null

    Example usage:
        > flytezen -h
        > flytezen \
            inputs.logistic_regression.C=0.4 \
            inputs.logistic_regression.max_iter=1200
        > flytezen \
            --multirun inputs.logistic_regression.C=0.2,0.5

        See the the hydra config output in the git-ignored `./outputs` or
        `./multirun` directories. These are also stored as an artifact of
        the CI actions workflow in the `Upload config artifact` step.

    Warning:
        Hydra command-line overrides are only intended to be supported for
        inputs. Do not override workflow-level parameters. This will lead to
        unexpected behavior. You can modify workflow parameters with `.env` or
        environment variables. Note  `version` and `tag` are determined
        automatically in python based on `mode`. The workflow execution
        parameters are stored in the hydra config output for reference.
    """
    main()
