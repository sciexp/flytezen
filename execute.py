import importlib
import logging
import os
import subprocess

import rich.syntax
import rich.tree
from dotenv import load_dotenv
from flytekit.configuration import Config, ImageConfig, SerializationSettings
from flytekit.remote import FlyteRemote
from hydra.conf import HydraConf
from hydra_zen import make_config, store, to_yaml, zen
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# -----
# setup
# -----

# The following are required to disable hydra's default logging configuration
# It is equivalent to overriding the hydra/hydra_logging and hydra/job_logging
#   python execute.py hydra/hydra_logging=none hydra/job_logging=none
# see
#   https://mit-ll-responsible-ai.github.io/hydra-zen/generated/hydra_zen.ZenStore.html
#   https://hydra.cc/docs/tutorials/basic/running_your_app/logging/
hydra_conf = HydraConf(
    hydra_logging={"version": 1, "root": None, "disable_existing_loggers": False},
    job_logging={"version": 1, "root": None, "disable_existing_loggers": False},
)

store(hydra_conf)

load_dotenv()

console_theme = Theme(
    {
        "logging.level.info": "dim cyan",
        "logging.level.warning": "magenta",
        "logging.level.error": "bold red",
        "logging.level.debug": "green",
    }
)

console = Console(theme=console_theme)

rich_handler = RichHandler(
    console=console,
    rich_tracebacks=True,
    show_time=True,
    show_level=True,
    show_path=False,
    markup=True,
    log_time_format="[%X]",
)

valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
invalid_log_level = None
if log_level not in valid_log_levels:
    invalid_log_level = log_level
    log_level = "INFO"

logging.basicConfig(
    level=log_level,
    format="%(name)s %(message)s",
    datefmt="[%X]",
    handlers=[rich_handler],
)

logger = logging.getLogger("execute")

if isinstance(invalid_log_level, str):
    logger.warning(
        "Invalid log level: [bold red]{}[/bold red]\n"
        "Defaulting to [green]'INFO'[/green]\n"
        "Valid log levels are: {}".format(invalid_log_level, valid_log_levels)
    )

def check_required_env_vars(*vars):
    missing_vars = [var for var in vars if os.environ.get(var) is None]
    if missing_vars:
        missing_vars_str = ", ".join(missing_vars)
        logger.error(f"Missing required environment variables: {missing_vars_str}")
        return False
    return True


load_dotenv()

required_vars = [
    "WORKFLOW_PROJECT",
    "WORKFLOW_DOMAIN",
    "WORKFLOW_NAME",
    "WORKFLOW_IMAGE",
]
if check_required_env_vars(*required_vars):
    WORKFLOW_PROJECT = os.environ.get("WORKFLOW_PROJECT")
    WORKFLOW_DOMAIN = os.environ.get("WORKFLOW_DOMAIN")
    WORKFLOW_NAME = os.environ.get("WORKFLOW_NAME")
    WORKFLOW_IMAGE = os.environ.get("WORKFLOW_IMAGE")
else:
    logger.error("Exiting due to missing environment variables.")
    exit(1)

# -------------------
# configure workflow
# -------------------

# builds = make_custom_builds_fn(populate_full_signature=True)
# pbuilds = make_custom_builds_fn(zen_partial=True, populate_full_signature=True)


def git_info_to_workflow_version():
    try:
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
    except subprocess.CalledProcessError as e:
        logger.error(f"Error obtaining git information: {e}")
        raise

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
    wait=True,
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
    config_yaml = to_yaml(workflow)
    tree = rich.tree.Tree("WORKFLOW", style="dim", guide_style="dim")
    tree.add(rich.syntax.Syntax(config_yaml, "yaml", theme="monokai"))
    rich.print(tree)

    entity = load_workflow(workflow.name)
    remote = FlyteRemote(
        config=Config.auto(),
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

    logger.info(f"Executing workflow:\n\n\t{workflow.name}\n")
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
        import time
        from datetime import timedelta
        from flytekit.exceptions.user import FlyteTimeout
        timeout_duration = timedelta(seconds=3.0)  # Set timeout duration as a timedelta object
        try:
            while True:
                try:
                    completed_execution = remote.wait(execution, timeout=timeout_duration)
                    logger.info(f"Execution completed:\n\n{completed_execution}\n")
                    break
                except FlyteTimeout:
                    synced_execution = remote.sync(execution)
                    logger.info(f"Current status:\n\n{synced_execution}\n")
                    time.sleep(timeout_duration.total_seconds())
        except KeyboardInterrupt:
            logger.info(f"Status at KeyboardInterrupt:\n\n{synced_execution}\n")
            logger.error("KeyboardInterrupt")
            exit()

if __name__ == "__main__":
    store.add_to_hydra_store()
    zen(task_function).hydra_main(
        config_name="flyte_workflow_execution",
        version_base="1.2",
        config_path=".",
    )
