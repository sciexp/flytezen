import os

import rich.syntax
import rich.tree
from dotenv import load_dotenv
from flytekit.configuration import Config as FlyteConfig
from flytekit.configuration import ImageConfig, SerializationSettings
from flytekit.remote import FlyteRemote
from hydra_zen import make_config, store, to_yaml, zen

from execution_utils import (
    check_required_env_vars,
    configure_hydra,
    configure_logging,
    git_info_to_workflow_version,
    load_workflow,
    wait_for_workflow_completion,
)


@store(
    name="workflow_execution",
    hydra_defaults=["_self_", {"workflow": "workflow_config"}],
)
def execute_workflow(workflow):
    """
    Executes the given workflow based on the Hydra configuration.

    Args:
        workflow: Hydra configuration object for the workflow execution.
    """
    config_yaml = to_yaml(workflow)
    tree = rich.tree.Tree("WORKFLOW", style="dim", guide_style="dim")
    tree.add(rich.syntax.Syntax(config_yaml, "yaml", theme="monokai"))
    rich.print(tree)

    entity = load_workflow(workflow.name)
    remote = FlyteRemote(
        config=FlyteConfig.auto(),
        default_project=workflow.project,
        default_domain=workflow.domain,
    )

    logger.info(f"Registering workflow:\n\n\t{workflow.name}\n")
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
        inputs=workflow.inputs,
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
            "WORKFLOW_NAME",
            "WORKFLOW_IMAGE",
        ],
        logger,
    ) or exit(1)

    configure_hydra()

    repo_name, git_branch, git_short_sha = git_info_to_workflow_version(logger)
    workflow_version = f"{repo_name}-{git_branch}-{git_short_sha}"

    WorkflowConfig = make_config(
        name=os.environ.get("WORKFLOW_NAME"),
        project=os.environ.get("WORKFLOW_PROJECT"),
        domain=os.environ.get("WORKFLOW_DOMAIN"),
        version=workflow_version,
        image=os.environ.get("WORKFLOW_IMAGE"),
        tag=git_short_sha,
        wait=False,
        inputs={"hyperparameters": {"C": 0.2}},
    )

    workflow_config_store = store(group="workflow")
    workflow_config_store(WorkflowConfig, name="workflow_config")

    store.add_to_hydra_store()
    zen(execute_workflow).hydra_main(
        config_name="workflow_execution",
        version_base="1.2",
        config_path="./conf",
    )
