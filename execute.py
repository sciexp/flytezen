import os
from dataclasses import dataclass

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
from workflows.lrwine import Hyperparameters


@dataclass_json
@dataclass
class WorkflowConfigClass:
    import_path: str
    project: str
    domain: str
    version: str
    image: str
    tag: str
    wait: bool
    hyperparameters: Hyperparameters


def execute_workflow(workflow: WorkflowConfigClass):
    """
    Executes the given workflow based on the Hydra configuration.

    Args:
        workflow: Hydra configuration object for the workflow execution.
    """
    config_yaml = to_yaml(workflow)
    tree = rich.tree.Tree("WORKFLOW", style="dim", guide_style="dim")
    tree.add(rich.syntax.Syntax(config_yaml, "yaml", theme="monokai"))
    rich.print(tree)

    entity = load_workflow(workflow.import_path)
    remote = FlyteRemote(
        config=FlyteConfig.auto(),
        default_project=workflow.project,
        default_domain=workflow.domain,
    )

    logger.info(f"Registering workflow:\n\n\t{workflow.import_path}\n")
    serialization_settings = SerializationSettings(
        ImageConfig.auto(img_name=f"{workflow.image}:{workflow.tag}")
    )
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
    logger.info(f"Execution submitted:\n\n{execution}\n")
    logger.info(f"Execution url:\n\n{remote.generate_console_url(execution)}\n")

    if workflow.wait:
        wait_for_workflow_completion(execution, remote, logger)


if __name__ == "__main__":
    load_dotenv()
    logger = configure_logging()

    check_required_env_vars(
        [
            "WORKFLOW_PROJECT",
            "WORKFLOW_DOMAIN",
            "WORKFLOW_IMPORT_PATH",
            "WORKFLOW_IMAGE",
        ],
        logger,
    ) or exit(1)

    store = ZenStore(deferred_hydra_store=False)

    hydra_conf = HydraConf(
        hydra_logging={"version": 1, "root": None, "disable_existing_loggers": False},
        job_logging={"version": 1, "root": None, "disable_existing_loggers": False},
    )
    store(hydra_conf)

    repo_name, git_branch, git_short_sha = git_info_to_workflow_version(logger)
    workflow_version = f"{repo_name}-{git_branch}-{git_short_sha}"

    store(
        execute_workflow,
        workflow=WorkflowConfigClass(
            import_path=os.environ.get("WORKFLOW_IMPORT_PATH"),
            project=os.environ.get("WORKFLOW_PROJECT"),
            domain=os.environ.get("WORKFLOW_DOMAIN"),
            version=workflow_version,
            image=os.environ.get("WORKFLOW_IMAGE"),
            tag=git_short_sha,
            wait=True,
            hyperparameters=Hyperparameters(C=0.2, max_iter=2500),
        ),
    )

    store.add_to_hydra_store()

    zen(execute_workflow).hydra_main(
        config_path=None,
        config_name="execute_workflow",
        version_base="1.3",
    )
