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
from hydra_zen import ZenStore, make_config, make_custom_builds_fn, to_yaml, zen
from omegaconf import DictConfig

from flytezen.cli.execution_utils import (
    EntityConfig,
    generate_entity_configs,
    generate_hydra_config,
    git_info_to_workflow_version,
    random_alphanumeric_suffix,
    wait_for_workflow_completion,
)
from flytezen.logging import configure_logging

logger = configure_logging("execute")
builds = make_custom_builds_fn(populate_full_signature=True)


class ExecutionMode(str, Enum):
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

    # LOCAL = 1
    # DEV = 2
    # PROD = 3
    LOCAL = "local"
    DEV = "dev"
    PROD = "prod"

    # def __str__(self):
    #     return self.value


@dataclass_json
@dataclass
class ExecutionContext:
    """
    Represents the execution configuration for a workflow.

    This dataclass encapsulates settings related to the execution environment,
    including the mode of execution, container image details, and workflow
    versioning information.

    Attributes:
        name (ExecutionMode): The execution mode, which dictates how and where the workflow is executed.
        image (str): The full name of the container image to be used in the execution, including the registry path.
        tag (str): The tag appended to the container image, usually git branch (DEV) or commit hash (PROD).
        version (str): A string representing the version of the workflow, typically including a commit hash or other identifiers.
    """

    # name: ExecutionMode = ExecutionMode.DEV
    mode: str = "dev"
    image: str = "ghcr.io/sciexp/flytezen"
    tag: str = "main"
    version: str = f"flytezen-main-{random_alphanumeric_suffix()}"
    package_path: str = "src"
    import_path: str = "flytezen.workflows"
    project: str = "flytesnacks"
    domain: str = "development"
    wait: bool = True


def execute_workflow(
    zen_cfg: DictConfig,
    execution_context: ExecutionContext,
    # name: str = "training_workflow",
    # inputs: Dict[str, Any] = {},
    entity_config: EntityConfig,
    # entities: EntityConfigs,
    # entities: Dict[str, Any],
    # package_path: str = "src",
    # import_path: str = "flytezen.workflows.lrwine",
    # project: str = "flytesnacks",
    # domain: str = "development",
    # wait: bool = True,
) -> None:
    """
    Executes the given workflow based on the Hydra configuration. The execution
    mode is controlled by the 'mode' parameter, which is an instance of the
    ExecutionContext dataclass. This dataclass encapsulates execution configuration
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
      in the ExecutionContext image. The image used is tagged with the git short
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
        mode (ExecutionContext): An instance of ExecutionContext specifying the execution environment and settings.
        inputs (Dict[str, Any]): Inputs to the workflow function. Keys are argument names, values are the inputs.

        TODO: Dynamic configuration of `inputs` argument should be required, but it is placed
        at the bottom due to the length in printing the config.
        The parameters should be reorderd in hydra/to_yaml and this can then be moved
        to the top of the arg list and made required.

    Raises:
        Sets exit status one if an invalid execution mode is specified.
    """
    config_yaml = to_yaml(zen_cfg)
    tree = rich.tree.Tree("execute_workflow", style="dim", guide_style="dim")
    tree.add(rich.syntax.Syntax(config_yaml, "yaml", theme="monokai"))
    rich.print(tree)

    module = importlib.import_module(
        f"{execution_context.import_path}.{entity_config.module_name}"
    )
    entity = getattr(module, entity_config.entity_name)

    # https://github.com/flyteorg/flytekit/blob/dc9d26bfd29d7a3482d1d56d66a806e8fbcba036/flytekit/clis/sdk_in_container/run.py#L477
    # if execution_context.mode == ExecutionMode.LOCAL:
    if execution_context.mode == "local":
        output = entity(**entity_config.inputs)
        logger.info(f"Workflow output:\n\n{output}\n")
        return

    remote = FlyteRemote(
        config=FlyteConfig.auto(),
        default_project=execution_context.project,
        default_domain=execution_context.domain,
    )
    image_config = ImageConfig.auto(
        img_name=f"{execution_context.image}:{execution_context.tag}"
    )

    # if execution_context.mode == ExecutionMode.DEV:
    if execution_context.mode == "dev":
        logger.warning(
            "This execution_context.mode is intended for development purposes only.\n\n"
            "Please use 'prod' execution_context.mode for production or CI environments.\n\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger.debug(
                f"Packaged tarball temporary directory:\n\n\t{tmp_dir}\n"
            )
            _, upload_url = remote.fast_package(
                pathlib.Path(execution_context.package_path),
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
    # elif execution_context.mode == ExecutionMode.PROD:
    elif execution_context.mode == "prod":
        logger.info(
            f"Registering workflow:\n\n\t{entity_config.module_name}.{entity_config.entity_name}\n"
        )
        serialization_settings = SerializationSettings(
            image_config=image_config
        )
    else:
        logger.error(
            f"Invalid workflow registration mode: {execution_context.mode}. "
            "Please set the 'name' of ExecutionContext to one of the following: "
            f"{', '.join([e.value for e in ExecutionMode])}."
        )
        sys.exit(1)

    remote.register_workflow(
        entity=entity,
        serialization_settings=serialization_settings,
        version=execution_context.version,
    )
    execution = remote.execute(
        entity=entity,
        inputs=entity_config.inputs,
        version=execution_context.version,
        execution_name_prefix=execution_context.version,
        wait=False,
    )
    logger.info(f"Execution submitted:\n\n{execution}\n")
    logger.info(f"Execution url:\n\n{remote.generate_console_url(execution)}\n")

    if execution_context.wait:
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
    Main function that executes the workflow in one of the three modes
    determined by the config group mode (local, dev, prod):

    - In 'local' mode, it executes the workflow locally without a remote
    - In 'dev' mode, it uses the container execution_context.imagewith execution_context.tag current
      branch tag for execution. This allows executing a copy of updated local
      workflow on the remote prior to building a new image.
    - In 'prod' mode, it uses the container image with the git short SHA tag
      just after building an image. This is primarily for CI execution.

    See the `execute_workflow` function for more details.

    Note this logic regarding the image tag is independent of setting domain to
    "development", "staging", "production", etc.

    The workflow version is also separately determined based on the current git
    repo name, branch, and commit SHA.
    """

    load_dotenv()

    # equivalent to
    # hydra_zen.wrapper._implementations.store
    # except in name
    store = ZenStore(
        name="flytezen",
        deferred_to_config=True,
        deferred_hydra_store=True,
    )

    store(generate_hydra_config())

    repo_name, git_branch, git_short_sha = git_info_to_workflow_version(logger)

    workflow_image = os.environ.get(
        "WORKFLOW_IMAGE",
        "localhost:30000/flytezen",
    )
    ExecutionContextConf = builds(ExecutionContext)
    ContextConf = builds(ExecutionContext)
    local_execution_context = ContextConf(
        # mode=ExecutionContext.LOCAL,
        mode="local",
        image="",
        tag="",
        version=f"{repo_name}-{git_branch}-{git_short_sha}-local-{random_alphanumeric_suffix()}",
    )
    dev_execution_context = ContextConf(
        # mode=ExecutionContext.DEV,
        mode="dev",
        image=workflow_image,
        tag=git_branch,
        version=f"{repo_name}-{git_branch}-{git_short_sha}-dev-{random_alphanumeric_suffix()}",
    )
    prod_execution_context = ContextConf(
        # mode=ExecutionContext.PROD,
        mode="prod",
        image=workflow_image,
        tag=git_short_sha,
        version=f"{repo_name}-{git_branch}-{git_short_sha}",
    )

    # Define the [execution] execution_context store
    execution_context_store = store(group="execution_context")
    execution_context_store(local_execution_context, name="local")
    execution_context_store(dev_execution_context, name="dev")
    execution_context_store(prod_execution_context, name="prod")

    # Define the entity store
    entity_config_store = store(group="entity_config")

    # The parent module whose submodules you want to iterate over
    parent_module_path = "flytezen.workflows"
    generate_entity_configs(parent_module_path, entity_config_store, logger)

    hydra_defaults = [
        "_self_",
        {"execution_context": "dev"},
        {"entity_config": "lrwine_training_workflow"},
    ]
    # for name, entity in entities.items():
    #     hydra_defaults.append({f"entities.{name}": "base"})
    logger.info(f"hydra_defaults: {hydra_defaults}")
    # hydra_defaults.append("_self_")

    # default_entity_name = "lrwine_training_workflow"
    # default_entity = entities[default_entity_name]

    # store(
    #     execute_workflow,
    #     mode=dev_mode,
    #     # entity=default_entity,
    #     entities=entities,
    #     name="execute_workflow",
    #     hydra_defaults=hydra_defaults,
    # )

    store(
        make_config(
            hydra_defaults=[
                "_self_",
                {"execution_context": "dev"},
                {"entity_config": "lrwine_training_workflow"},
            ],
            execution_context=None,
            entity_config=None,
        ),
        name="execute_workflow",
    )

    store.add_to_hydra_store(overwrite_ok=True)

    zen(execute_workflow).hydra_main(
        config_path=None,
        config_name="execute_workflow",
        version_base="1.3",
    )


if __name__ == "__main__":
    """
    This script executes a Flyte workflow configured with hydra-zen.
    > flytezen --help.

    == Configuration groups ==
    First override default group values (group=option)

    entity_config: example_wf, lrwine_training_workflow
    execution_context: dev, local, prod


    == Config ==
    Then override any element in the config (foo.bar=value)

    execution_context:
      _target_: flytezen.cli.execute.ExecutionContext
      mode: dev
      image: localhost:30000/flytezen
      tag: main
      version: flytezen-main-16323b3-dev-a8x
      name: training_workflow
      package_path: src
      import_path: flytezen.workflows
      project: flytesnacks
      domain: development
      wait: true
    entity_config:
      _target_: flytezen.cli.execution_utils.EntityConfig
      inputs:
        logistic_regression:
          _target_: flytezen.workflows.lrwine.LogisticRegressionInterface
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
      module_name: lrwine
      entity_name: training_workflow
      entity_type: PythonFunctionWorkflow

    Example usage:
        > flytezen -h
        > flytezen
        > flytezen \
            execution_context=dev \
            entity_config=lrwine_training_workflow
        > flytezen \
            entity_config.inputs.logistic_regression.C=0.4 \
            entity_config.inputs.logistic_regression.max_iter=1200
        > flytezen \
            --multirun entity_config.inputs.logistic_regression.C=0.2,0.5

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
