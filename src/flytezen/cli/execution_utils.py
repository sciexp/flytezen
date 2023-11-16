import logging
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import timedelta
from typing import List, Tuple

from flytekit import WorkflowExecutionPhase
from flytekit.exceptions.system import FlyteSystemException
from flytekit.exceptions.user import FlyteTimeout
from flytekit.remote import FlyteRemote
from flytekit.remote.executions import FlyteWorkflowExecution


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
        git_branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip().decode()
        git_short_sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).strip().decode()
        remote_url = subprocess.check_output(["git", "config", "--get", "remote.origin.url"]).strip().decode()
        repo_name = remote_url.split("/")[-1].rstrip(".git")
        return repo_name, git_branch, git_short_sha
    except subprocess.CalledProcessError as e:
        logger.error(f"Error obtaining git information: {e}")
        raise


def get_user_input(input_queue):
    """
    Gets user input and puts it in the queue.
    """
    user_input = input("Terminate workflow execution? (y/N after 1 min.): ")
    input_queue.put(user_input)


def wait_for_workflow_completion(
    execution: FlyteWorkflowExecution, remote: FlyteRemote, logger: logging.Logger
) -> None:
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
                if completed_execution.error is None:
                    break
                else:
                    logger.error(f"Execution failed with error:\n\n{completed_execution.error}\n")
                    sys.exit(1)
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

        synced_execution = remote.sync(execution)
        if synced_execution.closure.phase in [WorkflowExecutionPhase.RUNNING]:
            try:
                if response in ["y", "yes"]:
                    remote.terminate(execution, "KeyboardInterrupt confirmed termination")
                    logger.info("Workflow execution terminated.")
                else:
                    logger.warning(f"\nExiting script without terminating workflow execution:\n\n{execution}\n")
            except FlyteSystemException as e:
                logger.error(f"Error while trying to terminate the execution: {e}")
        else:
            logger.info(f"Workflow execution already in terminal state: {synced_execution.closure.phase}")

        sys.exit()
