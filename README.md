# flytezen

A template for hydra-zen configuration of Flyte workflow execution.

## Layout

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
│   │   │   ├── execution_config.py
│   │   │   └── execution_utils.py
│   │   ├── workflows
│   │   │   ├── __init__.py
│   │   │   ├── example.py
│   │   │   └── lrwine.py
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── configuration.py
│   │   ├── constants.py
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

14 directories, 38 files
```

</details>
