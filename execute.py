import os
import subprocess

from dotenv import load_dotenv
from flytekit.configuration import Config
from flytekit.remote import FlyteRemote
from hydra_zen import make_config, store, to_yaml, zen

load_dotenv()

WORKFLOW_PROJECT = os.getenv("WORKFLOW_PROJECT")
WORKFLOW_DOMAIN = os.getenv("WORKFLOW_DOMAIN")
WORKFLOW_NAME = os.getenv("WORKFLOW_NAME")

if not (WORKFLOW_PROJECT and WORKFLOW_DOMAIN and WORKFLOW_NAME):
    raise ValueError(
        "WORKFLOW_PROJECT, WORKFLOW_DOMAIN, and WORKFLOW_NAME must be set in the .env file"
    )

# -------------------
# configure workflow
# -------------------


def git_info_to_workflow_version():
    git_branch = (
        subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        .strip()
        .decode()
    )
    git_short_sha = (
        subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
        .strip()
        .decode()
    )

    remote_url = (
        subprocess.check_output(["git", "config", "--get", "remote.origin.url"])
        .strip()
        .decode()
    )
    repo_name = remote_url.split("/")[-1].rstrip(".git")

    return f"{repo_name}-{git_branch}-{git_short_sha}"


# builds = make_custom_builds_fn(populate_full_signature=True)
# pbuilds = make_custom_builds_fn(zen_partial=True, populate_full_signature=True)

FlyteConfig = make_config(
    WORKFLOW_PROJECT=WORKFLOW_PROJECT,
    WORKFLOW_DOMAIN=WORKFLOW_DOMAIN,
    WORKFLOW_NAME=WORKFLOW_NAME,
    WORKFLOW_VERSION=git_info_to_workflow_version(),
    INPUTS={"hyperparameters": {"C": 0.2}},
)

flyte_config_store = store(group="workflow")
flyte_config_store(FlyteConfig, name="flyte_config")


@store(
    name="flyte_workflow_execution",
    hydra_defaults=["_self_", {"workflow": "flyte_config"}],
)
def task_function(workflow):
    print("Executing Flyte workflow")
    print(to_yaml(workflow))

    print("Flyte configuration")
    flyte_config = Config.auto()
    remote = FlyteRemote(config=flyte_config)

    flyte_wf = remote.fetch_workflow(
        project=workflow.WORKFLOW_PROJECT,
        domain=workflow.WORKFLOW_DOMAIN,
        name=workflow.WORKFLOW_NAME,
        version=workflow.WORKFLOW_VERSION,
    )

    print(flyte_wf.name)
    remote.execute(
        entity=flyte_wf,
        inputs=workflow.INPUTS,
        project=workflow.WORKFLOW_PROJECT,
        domain=workflow.WORKFLOW_DOMAIN,
    )


if __name__ == "__main__":
    store.add_to_hydra_store()
    zen(task_function).hydra_main(
        config_name="flyte_workflow_execution",
        version_base="1.2",
        config_path=".",
    )
