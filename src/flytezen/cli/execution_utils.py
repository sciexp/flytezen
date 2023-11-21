import logging
import os
import queue
import secrets
import subprocess
import sys
import threading
import time
from datetime import timedelta
from textwrap import dedent
from typing import List, Tuple

from flytekit import WorkflowExecutionPhase
from flytekit.exceptions.system import FlyteSystemException
from flytekit.exceptions.user import FlyteTimeout
from flytekit.remote import FlyteRemote
from flytekit.remote.executions import FlyteWorkflowExecution
from hydra.conf import HelpConf, HydraConf, JobConf


def random_alphanumeric_suffix(input_string: str = "", length: int = 3) -> str:
    return input_string.join(
        secrets.choice("abcdefghijklmnopqrstuvwxyz0123456789")
        for _ in range(length)
    )


def check_required_env_vars(
    required_vars: List[str], logger: logging.Logger
) -> bool:
    """
    Checks required environment variables for workflow configuration.
    """

    missing_vars = [var for var in required_vars if os.environ.get(var) is None]
    if missing_vars:
        missing_vars_str = ", ".join(missing_vars)
        logger.error(
            f"Missing required environment variables: {missing_vars_str}"
        )
        return False
    return True


def git_info_to_workflow_version(
    logger: logging.Logger,
) -> Tuple[str, str, str]:
    """
    Retrieves git information for workflow versioning.
    """
    try:
        git_branch = (
            subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"]
            )
            .strip()
            .decode()
        )
        git_short_sha = (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
            .strip()
            .decode()
        )
        remote_url = (
            subprocess.check_output(
                ["git", "config", "--get", "remote.origin.url"]
            )
            .strip()
            .decode()
        )
        repo_name = remote_url.split("/")[-1].rstrip(".git")
        for string in [repo_name, git_branch, git_short_sha]:
            if any(char.isupper() for char in string):
                logger.warning(
                    f"String '{string}' contains capitalized characters. Converting to lowercase."
                )

        return repo_name.lower(), git_branch.lower(), git_short_sha.lower()
    except subprocess.CalledProcessError as e:
        logger.error(f"Error obtaining git information: {e}")
        raise


def generate_hydra_config() -> HydraConf:
    return HydraConf(
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
        help=HelpConf(
            header=dedent(
                """
                This is the ${hydra.help.app_name} help accessible via `${hydra.help.app_name} -h`.

                Use `${hydra.help.app_name} -c job` to view the ${hydra.help.app_name} configuration alone.
                See the end of this help page for instructions on how to install shell tab completion for
                configuration overrides.

                ${hydra.help.app_name} is the CLI of a template designed to illustrate the integration of:

                  * hydra-zen (https://mit-ll-responsible-ai.github.io/hydra-zen/),
                  * hydra (https://hydra.cc/), and
                  * omegaconf (https://omegaconf.readthedocs.io/),

                which provide configuration management, with

                  * flyte(kit) (https://flyte.org/),

                which manages the registration and execution of Flyte workflows.
                ${hydra.help.app_name} can be adapted as an auxiliary component of any python package,
                enhancing its capabilities in managing complex workflow configuration
                and execution.

                Running `${hydra.help.app_name} -c job` displays the current configuration of ${hydra.help.app_name}.
                This reflects what will be executed if `flytezen` is run without arguments.

                Use `${hydra.help.app_name} -c hydra` to view the associated hydra configuration.

                """
            ),
            footer=dedent(
                """
                You can test CLI configuration overrides after `-c job`, e.g.:

                  * `${hydra.help.app_name} -c job mode=prod`
                  * `${hydra.help.app_name} -c job name=wf import_path=${hydra.help.app_name}.workflows.example`
                  # This example will fail if you set a workflow with different inputs.
                  * `${hydra.help.app_name} -c job inputs.logistic_regression.penalty=l1`

                This will generate `== Config ==` above resolved in context of the command line overrides.
                Removing the `-c job` flag will execute the workflow with the specified configuration.
                The resolved configuration will be stored in the `outputs` or `multirun` directories.

                Use `${hydra.help.app_name} --hydra-help` to view the hydra help.
                This contains, for example, the commands to install shell tab completion.
                For example in bash or zsh, if the active configuration has path `inputs.logistic_regression`
                representing the parameters of a sklearn.linear_model.LogisticRegression instance:

                > eval "$$(flytezen -sc install=bash)"
                > flytezen inputs.logistic_regression. [TAB]
                inputs.logistic_regression.C=                  inputs.logistic_regression.fit_intercept=
                inputs.logistic_regression._target_=           inputs.logistic_regression.intercept_scaling=
                inputs.logistic_regression.class_weight.       inputs.logistic_regression.l1_ratio=
                inputs.logistic_regression.dual=               inputs.logistic_regression.max_iter=
                ..."""
            ),
            template=dedent(
                """
                ${hydra.help.header}
                == Config ==
                Override anything in the config (foo.bar=value)

                $CONFIG
                ${hydra.help.footer}
                """
            ),
        ),
        job=JobConf(name="flytezen"),
    )


def get_user_input(input_queue):
    """
    Gets user input and puts it in the queue.
    """
    user_input = input("Terminate workflow execution? (y/N after 1 min.): ")
    input_queue.put(user_input)


def wait_for_workflow_completion(
    execution: FlyteWorkflowExecution,
    remote: FlyteRemote,
    logger: logging.Logger,
) -> None:
    """
    Waits for the execution to complete, checking status at regular intervals.
    """
    timeout_duration = timedelta(seconds=3.0)
    synced_execution = None
    try:
        while True:
            try:
                completed_execution = remote.wait(
                    execution, timeout=timeout_duration
                )
                logger.info(f"Execution completed:\n\n{completed_execution}\n")
                if completed_execution.error is None:
                    break
                else:
                    logger.error(
                        f"Execution failed with error:\n\n{completed_execution.error}\n"
                    )
                    sys.exit(1)
            except FlyteTimeout:
                synced_execution = remote.sync(execution)
                logger.info(f"Current status:\n\n{synced_execution}\n")
                time.sleep(timeout_duration.total_seconds())
    except KeyboardInterrupt:
        if synced_execution is not None:
            logger.info(f"Status at KeyboardInterrupt:\n\n{synced_execution}\n")
        else:
            logger.info(
                "KeyboardInterrupt caught before execution status sync."
            )

        input_queue = queue.Queue()
        input_thread = threading.Thread(
            target=get_user_input, args=(input_queue,)
        )
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
                    remote.terminate(
                        execution, "KeyboardInterrupt confirmed termination"
                    )
                    logger.info("Workflow execution terminated.")
                else:
                    logger.warning(
                        f"\nExiting script without terminating workflow execution:\n\n{execution}\n"
                    )
            except FlyteSystemException as e:
                logger.error(
                    f"Error while trying to terminate the execution: {e}"
                )
        else:
            logger.info(
                f"Workflow execution already in terminal state: {synced_execution.closure.phase}"
            )

        sys.exit()
