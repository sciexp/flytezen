# flytezen

A template for hydra-zen configuration of Flyte workflow execution.

## Layout

<details>

<summary>tree</summary>

```tree
.
├── .argo
│   └── build.yaml
├── .devcontainer
│   ├── devcontainer.Dockerfile
│   └── devcontainer.json
├── .flyte
│   ├── config-browser.yaml
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
│   │   ├── build-images.yaml
│   │   └── labeler.yml
│   ├── .gitkeep
│   ├── codecov.yml
│   ├── labels.yml
│   └── renovate.json
├── .vscode
│   ├── extensions.json
│   ├── launch.json
│   ├── settings.json
│   └── tasks.json
├── containers
│   ├── Dockerfile
│   ├── gpu.Dockerfile
│   └── pkg.Dockerfile
├── environments
│   └── conda
│       ├── conda-linux-64.lock.yml
│       ├── conda-lock.yml
│       └── virtual-packages.yml
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
├── .dockerignore
├── .env
├── .envrc
├── .example.env
├── .gitignore
├── LICENSE
├── Makefile
├── README.md
├── flake.lock
├── flake.nix
├── poetry.lock
├── poetry.toml
├── pyproject.toml
└── requirements.txt

18 directories, 58 files
```

</details>
