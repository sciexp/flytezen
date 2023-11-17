# """Test cases for the cli package."""


def test_load_execute():
    import flytezen.cli.execute

    hasattr(flytezen.cli.execute, "execute_workflow")
    print(flytezen.cli.execute.__file__)


def test_load_execution_utils():
    import flytezen.cli.execution_utils

    hasattr(flytezen.cli.execution_utils, "wait_for_workflow_completion")
    print(flytezen.cli.execution_utils.__file__)
