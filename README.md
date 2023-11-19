# flytezen

A template for hydra-zen configuration of Flyte workflow execution.

## Directory tree

<details>

<summary>tree</summary>

```tree
.
├── .argo
│   └── build.yaml
├── .flyte
│   ├── config-local.yaml
│   ├── config-template.yaml
│   └── config.yaml
├── .github
│   ├── actions
│   │   ├── setup_environment
│   │   │   └── action.yml
│   │   └── tag-build-push-container
│   ├── workflows
│   │   ├── CI.yaml
│   │   └── build-images.yaml
│   └── .gitkeep
├── containers
│   ├── Dockerfile
│   └── pkg.Dockerfile
├── src
│   ├── flytezen
│   │   ├── cli
│   │   │   ├── __init__.py
│   │   │   ├── execute.py
│   │   │   └── execution_utils.py
│   │   ├── workflows
│   │   │   ├── __init__.py
│   │   │   ├── example.py
│   │   │   └── lrwine.py
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── configuration.py
│   │   └── logging.py
│   └── .gitkeep
├── tests
│   ├── __init__.py
│   ├── conftest.py
│   └── test_cli.py
├── .coverage
├── .dockerignore
├── .env
├── .envrc
├── .example.env
├── .gitignore
├── LICENSE
├── Makefile
├── README.md
├── poetry.lock
└── pyproject.toml

14 directories, 35 files
```

</details>

## flyte-template

A template for the recommended layout of a Flyte enabled repository for code written in python using [flytekit](https://docs.flyte.org/projects/flytekit/en/latest/).

### Usage

To get up and running with your Flyte project, we recommend following the
[Flyte getting started guide](https://docs.flyte.org/en/latest/getting_started.html).

We recommend using a git repository to version this project, so that you can
use the git sha to version your Flyte workflows.
