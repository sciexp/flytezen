# flytezen

A template for hydra-zen configuration of Flyte workflow execution.

## Directory tree

```tree
flyte-zen/
  src/
    flytezen/               # Core package code
      __init__.py
      common/               # Common utilities and shared code
        __init__.py
         ...
        ...

      cli/                   # CLI-related code
        __init__.py
        main.py              # Entry point for the CLI
        execute.py           # Workflow execution script, adapted for CLI
        execution_utils.py   # Utility functions for execution

      workflows/             # Workflow definitions
        __init__.py
        example.py
        lrwine.py
        ...

  tests/                    # Unit tests
    ...
  .env                      # Environment variables
  .gitignore
  LICENSE
  README.md
  pyproject.toml            # Project metadata and dependencies
```

## flyte-template

A template for the recommended layout of a Flyte enabled repository for code written in python using [flytekit](https://docs.flyte.org/projects/flytekit/en/latest/).

### Usage

To get up and running with your Flyte project, we recommend following the
[Flyte getting started guide](https://docs.flyte.org/en/latest/getting_started.html).

We recommend using a git repository to version this project, so that you can
use the git sha to version your Flyte workflows.
