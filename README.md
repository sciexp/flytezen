# flytezen

A template for hydra-zen configuration of Flyte workflow execution.

- [Quick start](#quick-start)
- [Layout](#layout)
- [Acknowledgements](#acknowledgements)

## Quick start

See `make | grep codespace`, run `make codespace_create code`, or

[![codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/?hide_repo_select=true&ref=main&repo=723447526&skip_quickstart=true&machine=standardLinux32gb&devcontainer_path=.devcontainer%2Fdevcontainer.json)

This provides a zero install demonstration of the supported development environment that depends on the [nix](https://nixos.org/) package manager or open container images built with it. See `make | grep nix` or `make -n setup_dev` to setup a local copy of this environment.

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
│   │   ├── CD.yaml
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

18 directories, 58 files
```

</details>

## Acknowledgements

### Selected dependencies

- [flocken](https://github.com/mirkolenz/flocken)
- [flytekit](https://github.com/flyteorg/flytekit)
- [hydra-zen](https://github.com/mit-ll-responsible-ai/hydra-zen)
- [poetry2nix](https://github.com/nix-community/poetry2nix)

See also [flake.nix](./flake.nix), [pyproject.toml](./pyproject.toml), and [.github](./.github/).
