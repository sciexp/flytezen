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
│   ├── CODEOWNERS
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
├── devshell
├── flake.lock
├── flake.nix
├── poetry.lock
├── poetry.toml
├── pyproject.toml
└── requirements.txt

18 directories, 57 files
```

</details>

## Acknowledgements

<details><summary>selected dependencies</summary>
<p>

* [flocken](https://github.com/mirkolenz/flocken)
* [flytekit](https://github.com/flyteorg/flytekit)
* [hydra-zen](https://github.com/mit-ll-responsible-ai/hydra-zen)
* [poetry2nix](https://github.com/nix-community/poetry2nix)

see also [flake.nix](flake.nix), [pyproject.toml](./pyproject.toml), [.github](./github/), and all of the core tools there and above are built upon

</p>
</details>
