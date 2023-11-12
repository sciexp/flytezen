import importlib
import os
import subprocess

from dotenv import load_dotenv
from flytekit.configuration import Config, SerializationSettings, ImageConfig
from flytekit.remote import FlyteRemote
from hydra_zen import make_config, store, to_yaml, zen

# builds = make_custom_builds_fn(populate_full_signature=True)
# pbuilds = make_custom_builds_fn(zen_partial=True, populate_full_signature=True)

load_dotenv()

WORKFLOW_PROJECT = os.getenv("WORKFLOW_PROJECT")
WORKFLOW_DOMAIN = os.getenv("WORKFLOW_DOMAIN")
WORKFLOW_NAME = os.getenv("WORKFLOW_NAME")
WORKFLOW_IMAGE = os.getenv("WORKFLOW_IMAGE")

if not (WORKFLOW_PROJECT and WORKFLOW_DOMAIN and WORKFLOW_NAME and WORKFLOW_IMAGE):
    raise ValueError(
        "WORKFLOW_PROJECT,"
        "WORKFLOW_DOMAIN,"
        "WORKFLOW_NAME,"
        "WORKFLOW_IMAGE,"
        "must all be set in the .env file"
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

    return repo_name, git_branch, git_short_sha


repo_name, git_branch, git_short_sha = git_info_to_workflow_version()
WORKFLOW_VERSION = f"{repo_name}-{git_branch}-{git_short_sha}"


def load_workflow(workflow_name: str):
    package_name, module_name, func_name = workflow_name.split(".")
    workflow_module = importlib.import_module(f"{package_name}.{module_name}")
    return getattr(workflow_module, func_name)


FlyteConfig = make_config(
    name=WORKFLOW_NAME,
    project=WORKFLOW_PROJECT,
    domain=WORKFLOW_DOMAIN,
    version=WORKFLOW_VERSION,
    image=WORKFLOW_IMAGE,
    tag=git_short_sha,
    inputs={"hyperparameters": {"C": 0.2}},
)

flyte_config_store = store(group="workflow")
flyte_config_store(FlyteConfig, name="flyte_config")


# ----------------
# execute workflow
# ----------------


@store(
    name="flyte_workflow_execution",
    hydra_defaults=["_self_", {"workflow": "flyte_config"}],
)
def task_function(workflow):
    print(to_yaml(workflow))

    entity = load_workflow(workflow.name)
    remote = FlyteRemote(
        config=Config.auto(),
        default_project=workflow.project,
        default_domain=workflow.domain,
    )

    print(f"Registering workflow:\n\n\t{workflow.name}\n")
    serialization_settings = SerializationSettings(
        ImageConfig.auto(img_name=f"{workflow.image}:{workflow.tag}")
    )
    remote.register_workflow(
        entity=entity,
        serialization_settings=serialization_settings,
        version=workflow.version,
    )

    print(f"Executing workflow:\n\n\t{workflow.name}\n")
    remote.execute(
        entity=entity,
        version=workflow.version,
        inputs=workflow.inputs,
        wait=True,
        execution_name_prefix=workflow.version,
    )


if __name__ == "__main__":
    store.add_to_hydra_store()
    zen(task_function).hydra_main(
        config_name="flyte_workflow_execution",
        version_base="1.2",
        config_path=".",
    )
