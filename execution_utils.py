import importlib
import logging
import os
import queue
import subprocess
import threading
import time
from datetime import timedelta
from typing import Any, List, Tuple

from flytekit.exceptions.user import FlyteTimeout
from flytekit.remote import FlyteRemote
from flytekit.remote.executions import FlyteWorkflowExecution
from hydra.conf import HydraConf
from hydra_zen import store
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme


def configure_logging() -> logging.Logger:
    """
    Configures logging with rich handler and checks for valid log level from environment.
    Defaults to `INFO` if no valid log level is found.
    """
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

    if log_level not in valid_log_levels:
        log_level = "INFO"

    logging.basicConfig(
        level=log_level,
        format="%(name)s %(message)s",
        datefmt="[%X]",
        handlers=[rich_handler],
    )
    return logging.getLogger("execute")


def check_required_env_vars(required_vars: List[str], logger: logging.Logger) -> bool:
    """
    Checks required environment variables for workflow configuration.
    """

    missing_vars = [var for var in required_vars if os.environ.get(var) is None]
    if missing_vars:
        missing_vars_str = ", ".join(missing_vars)
        logger.error(f"Missing required environment variables: {missing_vars_str}")
        return False
    return True


def git_info_to_workflow_version(logger: logging.Logger) -> Tuple[str, str, str]:
    """
    Retrieves git information for workflow versioning.
    """
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
        repo_name = remote_url.split("/")[-1].rstrip(".git")
        return repo_name, git_branch, git_short_sha
    except subprocess.CalledProcessError as e:
        logger.error(f"Error obtaining git information: {e}")
        raise


def load_workflow(workflow_name: str) -> Any:
    """
    Loads the specified workflow.
    """
    package_name, module_name, func_name = workflow_name.split(".")
    workflow_module = importlib.import_module(f"{package_name}.{module_name}")
    return getattr(workflow_module, func_name)


def configure_hydra() -> None:
    """
    Configures Hydra:
        - disable default logging.
    """
    hydra_conf = HydraConf(
        hydra_logging={"version": 1, "root": None, "disable_existing_loggers": False},
        job_logging={"version": 1, "root": None, "disable_existing_loggers": False},
    )
    store(hydra_conf)


def get_user_input(input_queue):
    """
    Gets user input and puts it in the queue.
    """
    user_input = input("Terminate workflow execution? (y/N after 1 min.): ")
    input_queue.put(user_input)


def wait_for_workflow_completion(execution: FlyteWorkflowExecution, remote: FlyteRemote, logger: logging.Logger) -> None:
    """
    Waits for the execution to complete, checking status at regular intervals.
    """
    timeout_duration = timedelta(seconds=3.0)
    synced_execution = None
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
        if synced_execution is not None:
            logger.info(f"Status at KeyboardInterrupt:\n\n{synced_execution}\n")
        else:
            logger.info("KeyboardInterrupt caught before execution status sync.")

        input_queue = queue.Queue()
        input_thread = threading.Thread(target=get_user_input, args=(input_queue,))
        input_thread.daemon = True
        input_thread.start()

        try:
            response = input_queue.get(timeout=60)
            response = response.strip().lower()
        except queue.Empty:
            response = "n"

        if response in ["y", "yes"]:
            remote.terminate(execution, "KeyboardInterrupt confirmed termination")
            logger.info("Workflow execution terminated.")
        else:
            logger.warning(
                f"\nExiting script without terminating workflow execution:\n\n{execution}\n"
            )

        exit()
