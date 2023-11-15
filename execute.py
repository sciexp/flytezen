import logging
import os
from dataclasses import dataclass
from typing import Any

import rich.syntax
import rich.tree
from dataclasses_json import dataclass_json
from dotenv import load_dotenv
from flytekit.configuration import Config as FlyteConfig
from flytekit.configuration import ImageConfig, SerializationSettings
from flytekit.remote import FlyteRemote
from hydra.conf import HydraConf
from hydra_zen import ZenStore, to_yaml, zen

from execution_utils import (
    check_required_env_vars,
    configure_logging,
    git_info_to_workflow_version,
    load_workflow,
    wait_for_workflow_completion,
)


@dataclass_json
@dataclass
class WorkflowConfigClass:
    """
    A dataclass representing configuration for a workflow execution.

    Attributes:
        import_path (str): The import path of the workflow function to execute.
        config_class (str): The name of the configuration class containing hyperparameters.
        project (str): The Flyte project in which to register or execute the workflow.
        domain (str): The Flyte domain in which to register or execute the workflow.
        version (str): The version of the workflow, including a git commit hash or other identifier(s).
        mode (str): Mode of workflow registration - 'dev' for fast registration and
                                          'prod' for manual registration.
        image (str): The container image FQN to use for executing the workflow.
        tag (str): The tag to append to the container image FQN to use for executing the workflow.
        wait (bool): Flag indicating whether to wait for the workflow execution to complete or run async.
        hyperparameters (Any): An instance of the configuration class defined by `config_class`, containing
                               hyperparameters for the workflow.
    """

    import_path: str
    config_class: str
    project: str
    domain: str
    version: str
    mode: str
    image: str
    tag: str
    wait: bool
    hyperparameters: Any


def execute_workflow(workflow: WorkflowConfigClass) -> None:
    """
    Executes the given workflow based on the Hydra configuration.

    The function supports two modes of execution controlled by 'mode':
    - 'dev': Executes a copy of the local workflow on the remote. This mode is used for
      development purposes, where changes to the workflow code can be tested remotely
      without needing to rebuild and push the container image.
    - 'prod': Registers the workflow on the remote and then executes it. This mode is
      intended for production or CI environments, where the workflow is executed against
      a container image that has been built and pushed to the registry specified in
      workflow.image.

    When the registration mode is set to dev, the workflow version is appended with '-dev'.

    Args:
        workflow: Hydra configuration object for the workflow execution.

    Raises:
        Exit status set to one if 'mode' is set to an invalid value.
    """
    config_yaml = to_yaml(workflow)
    tree = rich.tree.Tree("WORKFLOW", style="dim", guide_style="dim")
    tree.add(rich.syntax.Syntax(config_yaml, "yaml", theme="monokai"))
    rich.print(tree)

    _, entity = load_workflow(workflow.import_path)
    remote = FlyteRemote(
        config=FlyteConfig.auto(),
        default_project=workflow.project,
        default_domain=workflow.domain,
    )
    image_config = ImageConfig.auto(img_name=f"{workflow.image}:{workflow.tag}")

    if workflow.mode == "dev":
        # In dev mode, we execute a copy of the local workflow on the remote.
        # This is meant to mimic the fast registration mode of the pyflyte cli:
        #   pyflyte run \
        #   --remote \
        #   --project $(WORKFLOW_PROJECT) \
        #   --domain $(WORKFLOW_DOMAIN) \
        #   --image $(WORKFLOW_IMAGE):$(GIT_BRANCH) \
        #   $(WORKFLOW_FILE) \
        #   $(WORKFLOW_NAME) \
        #   --hyperparameters $(WORKFLOW_FILE_WORKFLOW_ARGS)
        # See the Makefile or run `make -n run_unregistered`
        logger.info("Executing a copy of the local workflow on the remote.")
        execution = remote.execute_local_workflow(
            entity=entity,
            inputs={"hyperparameters": workflow.hyperparameters},
            version=workflow.version + "-dev",
            execution_name_prefix=workflow.version,
            image_config=image_config,
            wait=False,
        )
    elif workflow.mode == "prod":
        # In prod mode, we register the workflow on the remote and then execute it.
        # This requires that a container image with code equivalent to the current
        # local copy has been built. As such, this is primarily meant to be used
        # in CI where the image is built and pushed to the registry just prior to
        # executing the workflow.
        logger.info(f"Registering workflow:\n\n\t{workflow.import_path}\n")
        serialization_settings = SerializationSettings(image_config=image_config)
        remote.register_workflow(
            entity=entity,
            serialization_settings=serialization_settings,
            version=workflow.version,
        )

        execution = remote.execute(
            entity=entity,
            inputs={"hyperparameters": workflow.hyperparameters},
            version=workflow.version,
            execution_name_prefix=workflow.version,
            wait=False,
        )
    else:
        logger.error(
            f"Invalid workflow registration mode: {workflow.mode}. "
            "Please set WORKFLOW_REGISTRATION_MODE to either 'dev' or 'prod' in your environment."
        )
        exit(1)
    logger.info(f"Execution submitted:\n\n{execution}\n")
    logger.info(f"Execution url:\n\n{remote.generate_console_url(execution)}\n")

    if workflow.wait:
        wait_for_workflow_completion(execution, remote, logger)


def main(logger: logging.Logger) -> None:
    """
    Main function that executes the workflow on the remote in one of two modes determined
    by "WORKFLOW_REGISTRATION_MODE":

    - In 'dev' mode, it uses the container image with the current branch tag for execution.
      This allows executing a copy of updated local workflow on the remote
      prior to building a new image.
    - In 'prod' mode, it uses the container image with the git short SHA tag just after
      building an image. This is primarily for CI execution.

    Note this logic regarding the image tag is independent of setting domain to "development",
    "staging", "production", etc.

    The workflow version is also separately determined based on the current git repo name,
    branch, and commit SHA.
    """

    load_dotenv()

    check_required_env_vars(
        [
            "WORKFLOW_IMPORT_PATH",
            "WORKFLOW_CONFIG_CLASS_NAME",
            "WORKFLOW_PROJECT",
            "WORKFLOW_DOMAIN",
            "WORKFLOW_REGISTRATION_MODE",
            "WORKFLOW_IMAGE",
        ],
        logger,
    ) or exit(1)

    store = ZenStore(deferred_hydra_store=False)

    hydra_conf = HydraConf(
        defaults=[
            {"output": "default"},
            {"launcher": "basic"},  # joblib
            {"sweeper": "basic"},
            {"help": "default"},
            {"hydra_help": "default"},
            {"hydra_logging": "none"},  # default
            {"job_logging": "none"},  # default
            {"callbacks": None},
            {"env": "default"},
        ],
    )
    store(hydra_conf)

    repo_name, git_branch, git_short_sha = git_info_to_workflow_version(logger)
    workflow_version = f"{repo_name}-{git_branch}-{git_short_sha}"
    workflow_import_path = os.environ.get("WORKFLOW_IMPORT_PATH")
    module, _ = load_workflow(workflow_import_path)
    workflow_config_class_name = os.environ.get("WORKFLOW_CONFIG_CLASS_NAME")
    config_class = getattr(module, workflow_config_class_name)

    workflow_registration_mode = os.environ.get("WORKFLOW_REGISTRATION_MODE")
    if workflow_registration_mode == "dev":
        image_tag = git_branch
    elif workflow_registration_mode == "prod":
        image_tag = git_short_sha
    else:
        logger.error(
            f"Invalid workflow registration mode: {workflow_registration_mode}. "
            "Please set WORKFLOW_REGISTRATION_MODE to either 'dev' or 'prod' in your environment."
        )
        exit(1)

    store(
        execute_workflow,
        workflow=WorkflowConfigClass(
            import_path=workflow_import_path,
            config_class=workflow_config_class_name,
            project=os.environ.get("WORKFLOW_PROJECT"),
            domain=os.environ.get("WORKFLOW_DOMAIN"),
            version=workflow_version,
            mode=workflow_registration_mode,
            image=os.environ.get("WORKFLOW_IMAGE"),
            tag=image_tag,
            wait=True,
            hyperparameters=config_class(),
        ),
    )

    store.add_to_hydra_store()

    zen(execute_workflow).hydra_main(
        config_path=None,
        config_name="execute_workflow",
        version_base="1.3",
    )


if __name__ == "__main__":
    """
    This script executes a Flyte workflow configured with hydra-zen.
    ❯ python execute.py --help

    == Config ==
    Override anything in the config (foo.bar=value)

    _target_: __main__.execute_workflow
    workflow:
    _target_: __main__.WorkflowConfigClass
    import_path: workflows.lrwine.training_workflow
    config_class: Hyperparameters
    project: flytesnacks
    domain: development
    version: flyte-template-main-16323b3
    mode: dev
    image: ghcr.io/org/flyte-template
    tag: main
    wait: true
    hyperparameters:
        _target_: workflows.lrwine.Hyperparameters
        C: 0.3
        max_iter: 2500


    Example usage:

    ❯ python execute.py workflow.hyperparameters.C=0.4 workflow.hyperparameters.max_iter=1200
    ❯ python execute.py --multirun workflow.hyperparameters.C=0.2,0.5
    """
    logger = configure_logging()
    main(logger)
