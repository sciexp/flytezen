.DEFAULT_GOAL := help

ENV_PREFIX ?= ./
ENV_FILE := $(wildcard $(ENV_PREFIX)/.env)

ifeq ($(strip $(ENV_FILE)),)
$(info $(ENV_PREFIX)/.env file not found, skipping inclusion)
else
include $(ENV_PREFIX)/.env
export
endif

GIT_SHORT_SHA = $(shell git rev-parse --short HEAD)
GIT_BRANCH = $(shell git rev-parse --abbrev-ref HEAD)

##@ Utility
help: ## Display this help. (Default). Update `.PHONY: target` in Makefile if target name could conflict with file or directory.
# based on "https://gist.github.com/prwhite/8168133?permalink_comment_id=4260260#gistcomment-4260260"
	@grep -hE '^[A-Za-z0-9_ \-]*?:.*##.*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

##@ Utility
help_sort: ## Display alphabetized version of help.
	@grep -hE '^[A-Za-z0-9_ \-]*?:.*##.*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'


#--------
# package
#--------

test: ## Run tests. See pyproject.toml for configuration.
	poetry run pytest

test-cov-xml: ## Run tests with coverage
	poetry run pytest --cov-report=xml

lint: ## Run linter
	poetry run ruff format .
	poetry run ruff --fix .

lint-check: ## Run linter in check mode
	poetry run ruff format --check .
	poetry run ruff .

typecheck: ## Run typechecker
	poetry run pyright
	
docs-build: ## Build documentation
	poetry run mkdocs build

docs-serve: ## Serve documentation
docs-serve: docs-build
	poetry run mkdocs serve

lock: ## Lock dependencies.
	poetry lock --no-update

export_pip_requirements: ## Export requirements.txt for pip.
export_pip_requirements: lock
	poetry export \
	--format=requirements.txt \
	--with=test \
	--output=requirements.txt \
	--without-hashes


#------------------
# local dev cluster
#------------------

local_cluster_install: ## Install localctl CLI to manage local dev cluster.
	@(which localctl > /dev/null && echo "\nlocalctl already installed\n") || \
	(cd ./scripts && ./localctl install) && \
	which localctl && localctl -h

local_cluster_start: ## Start local dev cluster.
	@localctl start

local_cluster_stop: ## Stop local dev cluster.
	@localctl stop

local_cluster_info: ## Print local dev cluster info.
	@localctl info

local_cluster_help: ## Print local dev cluster help.
	@localctl -h

local_cluster_remove: ## Remove local dev cluster.
	@localctl -v remove

# make -n build_local_image WORKFLOW_IMAGE=localhost:30000/flytezen
build_local_image: ## Build local image.
	@echo "building image: $(LOCAL_CONTAINER_REGISTRY)/$(GH_REPO_NAME):$(GIT_BRANCH)"
	@echo
	docker images -a --digests $(LOCAL_CONTAINER_REGISTRY)/$(GH_REPO_NAME)
	@echo
	docker build -t $(LOCAL_CONTAINER_REGISTRY)/$(GH_REPO_NAME):$(GIT_BRANCH) -f $(ACTIVE_DOCKERFILE) .
	@echo
	docker push $(LOCAL_CONTAINER_REGISTRY)/$(GH_REPO_NAME):$(GIT_BRANCH)
	@echo
	docker images -a --digests $(LOCAL_CONTAINER_REGISTRY)/$(GH_REPO_NAME)

# Use as: make remove_local_image 
# or: make remove_local_image GIT_BRANCH=tag-other-than-current-branch
# or: make remove_local_image GIT_BRANCH=sha256:<image-digest>
remove_local_image: ## Remove local image.
	@echo "removing image: $(LOCAL_CONTAINER_REGISTRY)/$(GH_REPO_NAME):$(GIT_BRANCH)"
	@echo
	docker images -a --digests $(LOCAL_CONTAINER_REGISTRY)/$(GH_REPO_NAME)
	@echo
	# Check if GIT_BRANCH is a sha256 digest
	if echo $(GIT_BRANCH) | grep -qE 'sha256:[0-9a-f]{64}'; then \
	    docker rmi $(LOCAL_CONTAINER_REGISTRY)/$(GH_REPO_NAME)@$(GIT_BRANCH); \
	else \
	    docker rmi $(LOCAL_CONTAINER_REGISTRY)/$(GH_REPO_NAME):$(GIT_BRANCH); \
	fi
	@echo
	docker images -a --digests $(LOCAL_CONTAINER_REGISTRY)/$(GH_REPO_NAME)


#---------------
# workflow setup
#---------------

flyte_info: ## Print flyte version and config.
flyte_info: flyte_config flyte_meta get_projects get_project get_workflows get_workflow get_tasks

flyte_config: ## Print config file
	@printf "\033[1;34m\nCONFIGURATION:\n\n\033[0m"
	@echo "config file: $$FLYTECTL_CONFIG"
	@grep -v '^\s*#' $$FLYTECTL_CONFIG | grep -v '^\s*$$'

flyte_meta: ## Print flyte version and config validation.
	@printf "\033[1;34m\nMETADATA:\n\n\033[0m"
	@echo "config file: $$FLYTECTL_CONFIG"
	flytectl version
	@printf "\n"
	flytectl config validate

get_projects: ## Get list of all projects.
	@printf "\033[1;34m\nPROJECTS:\n\n\033[0m"
	@echo "config file: $$FLYTECTL_CONFIG"
	flytectl get project

get_project: ## Get list of all projects.
	@printf "\033[1;34m\nPROJECT DOMAINS:\n\n\033[0m"
	@echo "config file: $$FLYTECTL_CONFIG"
	flytectl get project $(WORKFLOW_PROJECT) -o yaml

get_workflows: ## Get list of all workflows in a project-domain pair.
	@printf "\033[1;34m\nWORKFLOWS:\n\n\033[0m"
	@echo "config file: $$FLYTECTL_CONFIG"
	flytectl get workflows \
		--project $(WORKFLOW_PROJECT) \
		--domain $(WORKFLOW_DOMAIN)

WORKFLOW_VERSION ?= $(GH_REPO_NAME)-$(GIT_BRANCH)-$(GIT_SHORT_SHA)

get_workflow: ## Get workflow representation ( dot, yaml, doturl, json ).
	@printf "\033[1;34m\n$$WORKFLOW_IMPORT_PATH:\n\n\033[0m"
	@echo "config file: $$FLYTECTL_CONFIG"
	flytectl get workflows \
		--project $(WORKFLOW_PROJECT) \
		--domain $(WORKFLOW_DOMAIN) \
		--version $(WORKFLOW_VERSION) \
		-o $(WORKFLOW_OUTPUT_FORMAT) \
		$(WORKFLOW_IMPORT_PATH)

get_tasks: ## Get workflow tasks representation ( table ).
	@printf "\033[1;34m\nTASKS:\n\n\033[0m"
	@echo "config file: $$FLYTECTL_CONFIG"
	flytectl get tasks \
		--project $(WORKFLOW_PROJECT) \
		--domain $(WORKFLOW_DOMAIN)

get_executions: ## Get all executions ( table, excluded from flyte_info ).
	@printf "\033[1;34m\nEXECUTIONS:\n\n\033[0m"
	@echo "config file: $$FLYTECTL_CONFIG"
	flytectl get executions \
		--project $(WORKFLOW_PROJECT) \
		--domain $(WORKFLOW_DOMAIN)

WORKFLOW_IMAGE_TAG ?= $(GIT_SHORT_SHA)

package_workflows: ## Package workflows.
	@printf "\033[1;34m\nPACKAGE WORKFLOWS:\n\n\033[0m"
	@echo "config file: $$FLYTECTL_CONFIG"
	@echo "git branch: $(GIT_BRANCH)"
	@echo "git commit: $(GIT_SHORT_SHA)"
	@echo "workflow image: $(WORKFLOW_IMAGE):$(WORKFLOW_IMAGE_TAG)"
	@echo "workflow version: $(WORKFLOW_VERSION)"
	pyflyte \
		--pkgs workflows \
		package \
		--image $(WORKFLOW_IMAGE):$(WORKFLOW_IMAGE_TAG) \
		--force

register_workflows: ## Register workflows.
	@printf "\033[1;34m\nREGISTER WORKFLOWS:\n\n\033[0m"
	@echo "config file: $$FLYTECTL_CONFIG"
	flytectl register files \
		--project $(WORKFLOW_PROJECT) \
		--domain $(WORKFLOW_DOMAIN) \
		--archive flyte-package.tgz \
		--version "$(WORKFLOW_VERSION)"

package_and_register: ## Package and register workflows.
package_and_register: package_workflows register_workflows 


#-------------------
# workflow execution
#-------------------

run_help: ## Print hydra help for execute script.
	poetry run flytezen --help

# Capture additional arguments to pass to hydra-zen cli
# converting them to make do-nothing targets
# supports passing hydra overrides as ARGS, e.g.:
#   make run HYDRA_OVERRIDES="entity_config.inputs.logistic_regression.max_iter=2000 execution_context=local_shell"
HYDRA_OVERRIDES = $(filter-out $@,$(MAKECMDGOALS))
%:
	@:

.PHONY: run
run: ## Run registered workflow in remote dev mode. (default)
	poetry run flytezen $(HYDRA_OVERRIDES)

run_dev: ## Run registered workflow in remote prod mode. (ci default)
	poetry run flytezen execution_context=remote_dev $(HYDRA_OVERRIDES)

run_prod: ## Run registered workflow in remote prod mode. (ci default)
	poetry run flytezen execution_context=remote_prod $(HYDRA_OVERRIDES)

run_local_cluster: ## Run registered workflow in local cluster dev mode.
	poetry run flytezen execution_context=local_cluster_dev $(HYDRA_OVERRIDES)

run_local: ## Run registered workflow in local shell mode. (only with all python tasks)
	poetry run flytezen execution_context=local_shell $(HYDRA_OVERRIDES)

multirun: ## Run registered workflow with multiple hyperparameter sets.
	poetry run flytezen --multirun workflow.hyperparameters.C=0.2,0.5

run_async: ## Run registered workflow (async).
	poetry run flytezen execution_context.wait=False

run_cli_hp_config: ## Dispatch unregistered run from flytekit cli
	pyflyte run \
	--remote \
	--project $(WORKFLOW_PROJECT) \
	--domain $(WORKFLOW_DOMAIN) \
	--image $(WORKFLOW_IMAGE):$(GIT_BRANCH) \
	$(WORKFLOW_FILE) \
	$(WORKFLOW_NAME) \
	--hyperparameters $(WORKFLOW_FILE_WORKFLOW_ARGS)

run_cli_hp_config_local: ## Dispatch unregistered run from flytekit cli
	pyflyte run \
	$(WORKFLOW_FILE) \
	$(WORKFLOW_NAME) \
	--hyperparameters $(WORKFLOW_FILE_WORKFLOW_ARGS)


#-------------
# CI
#-------------

browse: ## Open github repo in browser at HEAD commit.
	gh browse $(GIT_SHORT_SHA)

GH_ACTIONS_DEBUG ?= false

ci: ## Run CI (GH_ACTIONS_DEBUG default is false).
	gh workflow run "CI" --ref $(GIT_BRANCH) -f debug_enabled=$(GH_ACTIONS_DEBUG)

build_images: ## Run Build Images (GH_ACTIONS_DEBUG default is false).
	gh workflow run "Build Images" --ref $(GIT_BRANCH) -f debug_enabled=$(GH_ACTIONS_DEBUG)

ci_view_workflow: ## Open CI workflow summary.
	gh workflow view "CI"

build_images_view_workflow: ## Open Build Images workflow summary.
	gh workflow view "Build Images"

# CPU | MEM | DISK | MACHINE_TYPE
# ----|-----|------|----------------
#   2 |   8 |   32 | basicLinux32gb
#   4 |  16 |   32 | standardLinux32gb
#   8 |  32 |   64 | premiumLinux
#  16 |  64 |  128 | largePremiumLinux
MACHINE_TYPE ?= standardLinux32gb
codespace_create: ## Create codespace. make -n codespace_create MACHINE_TYPE=largePremiumLinux
	gh codespace create -R $(GH_REPO) -b $(GIT_BRANCH) -m $(MACHINE_TYPE)

code: ## Open codespace in browser.
	gh codespace code -R $(GH_REPO) --web

codespace_list: ## List codespace.
	PAGER=cat gh codespace list

codespace_stop: ## Stop codespace.
	gh codespace stop

codespace_delete: ## Delete codespace.
	gh codespace delete

docker_login: ## Login to ghcr docker registry. Check regcreds in $HOME/.docker/config.json.
	docker login ghcr.io -u $(GH_ORG) -p $(GITHUB_TOKEN)

EXISTING_IMAGE_TAG ?= main
NEW_IMAGE_TAG ?= $(GIT_BRANCH)

# Default bumps main to the checked out branch for dev purposes
tag_images: ## Add tag to existing images, (default main --> branch, override with make -n tag_images NEW_IMAGE_TAG=latest).
	crane tag $(WORKFLOW_IMAGE):$(EXISTING_IMAGE_TAG) $(NEW_IMAGE_TAG)
	crane tag ghcr.io/$(GH_ORG)/$(GH_REPO):$(EXISTING_IMAGE_TAG) $(NEW_IMAGE_TAG)

list_gcr_workflow_image_tags: ## List images in gcr.
	gcloud container images list --repository=$(GCP_ARTIFACT_REGISTRY_PATH)                                                                                                                             │
	gcloud container images list-tags $(WORKFLOW_IMAGE)


#----
# nix
#----

meta: ## Generate nix flake metadata.
	nix flake metadata --impure
	nix flake show --impure

up: ## Update nix flake lock file.
	nix flake update --impure --accept-flake-config
	nix flake check --impure

dup: ## Debug update nix flake lock file.
	nix flake update --impure --accept-flake-config
	nix flake check --show-trace --print-build-logs --impure

re: ## Reload direnv.
	direnv reload

al: ## Enable direnv.
	direnv allow

devshell_info: ## Print devshell info.
	nix build .#devShells.$(shell nix eval --impure --expr 'builtins.currentSystem').default --impure
	nix path-info --recursive ./result
	du -chL ./result
	rm ./result

cache: ## Push devshell to cachix
	nix build --json \
	.#devShells.$(shell nix eval --impure --expr 'builtins.currentSystem').default \
	--impure \
	--accept-flake-config | \
	jq -r '.[].outputs | to_entries[].value' | \
	cachix push $(CACHIX_CACHE_NAME)

devcontainer: ## Build devcontainer.
	nix run .#devcontainerNix2Container.copyToDockerDaemon --accept-flake-config --impure

# The default value for DEVCONTAINER_IMAGE FQN can be completely overriden to
# support specification of tags or digests (see .example.env and create .env)
DEVCONTAINER_IMAGE ?= ghcr.io/sciexp/flytezendev
# DEVCONTAINER_IMAGE=ghcr.io/sciexp/flytezendev:main
# DEVCONTAINER_IMAGE=ghcr.io/sciexp/flytezendev@sha256:055bb57be472144bb140e20870320da8d9fa39daf69a57d2464596b974d34138

drundc: ## Run devcontainer. make drundc DEVCONTAINER_IMAGE=
	docker run --rm -it $(DEVCONTAINER_IMAGE)

adhocpkgs: ## Install adhoc nix packages. make adhocpkgs ADHOC_NIX_PKGS="gnugrep fzf"
	nix profile list
	$(foreach pkg, $(ADHOC_NIX_PKGS), nix profile install nixpkgs#$(pkg);)
	nix profile list

.PHONY: jupyter
jupyter: ## Run jupyter lab in devcontainer. make jupyter DEVCONTAINER_IMAGE=ghcr.io/sciexp/flytezendev@sha256:055bb57be472144bb140e20870320da8d9fa39daf69a57d2464596b974d34138
	@echo "Attempting to start jupyter lab in"
	@echo
	@echo "DEVCONTAINER_IMAGE: $(DEVCONTAINER_IMAGE)"
	@echo
	docker compose -f containers/compose.yaml up -d jupyter
	@echo
	$(MAKE) jupyter_logs

jupyter_logs: ## Print docker-compose logs.
	@echo
	@echo "Ctrl/cmd + click the http://127.0.0.1:8888/lab?token=... link to open jupyter lab in your default browser"
	@echo
	@trap 'printf "\n  use \`make jupyter_logs\` to reattach to logs or \`make jupyter_down\` to terminate\n\n"; exit 2' SIGINT; \
	while true; do \
		docker compose -f containers/compose.yaml logs -f jupyter; \
	done

jupyter_down: compose_list
jupyter_down: ## Stop docker-compose containers.
	docker compose -f containers/compose.yaml down jupyter
	$(MAKE) compose_list

compose_list: ## List docker-compose containers.
	@echo
	docker compose ls
	@echo
	docker compose -f containers/compose.yaml ps --services
	@echo
	docker compose -f containers/compose.yaml ps
	@echo

image_digests: ## Print image digests.
	@echo
	docker images -a --digests $(DEVCONTAINER_IMAGE)
	@echo

.PHONY: digest
digest: ## Print image digest from tag. make digest DEVCONTAINER_IMAGE=
	@echo
	docker inspect --format='{{index .RepoDigests 0}}' $(DEVCONTAINER_IMAGE)
	@echo

jupyter_manual: ## Prefer `make -n jupyter` to this target. make jupyter_manual DEVCONTAINER_IMAGE=
	docker run --rm -it -p 8888:8888 \
	$(DEVCONTAINER_IMAGE) \
	jupyter lab --allow-root --ip=0.0.0.0 /root/flytezen

findeditable: ## Find *-editable.pth files in the nix store.
	rg --files --glob '*editable.pth' --hidden --no-ignore --follow /nix/store/

#-------
# system
#-------

uninstall_nix: ## Uninstall nix.
	(cat /nix/receipt.json && \
	/nix/nix-installer uninstall) || echo "nix not found, skipping uninstall"

install_nix: ## Install nix. Check script before execution: https://install.determinate.systems/nix .
install_nix: uninstall_nix
	@which nix > /dev/null || \
	curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install

install_direnv: ## Install direnv to `/usr/local/bin`. Check script before execution: https://direnv.net/ .
	@which direnv > /dev/null || \
	(curl -sfL https://direnv.net/install.sh | bash && \
	sudo install -c -m 0755 direnv /usr/local/bin && \
	rm -f ./direnv)
	@echo "see https://direnv.net/docs/hook.html"

setup_dev: ## Setup nix development environment.
setup_dev: install_direnv install_nix
	@. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh && \
	nix profile install nixpkgs#cachix && \
	echo "trusted-users = root $$USER" | sudo tee -a /etc/nix/nix.conf && sudo pkill nix-daemon && \
	cachix use devenv

qemu: ## Install qemu with arm64 support.
	docker run --privileged --rm tonistiigi/binfmt --install arm64

.PHONY: devshell
devshell: ## Enter nix devshell. See use_flake in `direnv stdlib`.
	./scripts/flake

cdirenv: ## !!Enable direnv in zshrc.!!
	@if ! grep -q 'direnv hook zsh' "${HOME}/.zshrc"; then \
		printf '\n%s\n' 'eval "$$(direnv hook zsh)"' >> "${HOME}/.zshrc"; \
	fi

cstarship: ## !!Enable starship in zshrc.!!
	@if ! grep -q 'starship init zsh' "${HOME}/.zshrc"; then \
		printf '\n%s\n' 'eval "$$(starship init zsh)"' >> "${HOME}/.zshrc"; \
	fi

catuin: ## !!Enable atuin in zshrc.!!
	@if ! grep -q 'atuin init zsh' "${HOME}/.zshrc"; then \
		printf '\n%s\n' 'eval "$$(atuin init zsh)"' >> "${HOME}/.zshrc"; \
	fi

czsh: ## !!Enable zsh with command line info and searchable history.!!
czsh: catuin cstarship cdirenv

install_flytectl: ## Install flytectl. Check script before execution: https://docs.flyte.org/ .
	@which flytectl > /dev/null || \
	(curl -sL https://ctl.flyte.org/install | bash)

install_just: ## Install just. Check script before execution: https://just.systems/ .
	@which cargo > /dev/null || (curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh)
	@cargo install just

install_poetry: ## Install poetry. Check script before execution: https://python-poetry.org/docs/#installation .
	@which poetry > /dev/null || (curl -sSL https://install.python-poetry.org | python3 -)

install_crane: ## Install crane. Check docs before execution: https://github.com/google/go-containerregistry/blob/main/cmd/crane/doc/crane.md .
	@which crane > /dev/null || ( \
		set -e; \
		CRANE_VERSION="0.16.1"; \
		OS=$$(uname -s | tr '[:upper:]' '[:lower:]'); \
		ARCH=$$(uname -m); \
		case $$ARCH in \
			x86_64|amd64) ARCH="x86_64" ;; \
			aarch64|arm64) ARCH="arm64" ;; \
			*) echo "Unsupported architecture: $$ARCH" && exit 1 ;; \
		esac; \
		TMP_DIR=$$(mktemp -d); \
		trap 'rm -rf "$$TMP_DIR"' EXIT; \
		echo "Downloading crane $$CRANE_VERSION for $$OS $$ARCH to $$TMP_DIR"; \
		FILENAME="go-containerregistry_$$OS"_$$ARCH".tar.gz"; \
		URL="https://github.com/google/go-containerregistry/releases/download/v$$CRANE_VERSION/$$FILENAME"; \
		curl -sSL "$$URL" | tar xz -C $$TMP_DIR; \
		sudo mv $$TMP_DIR/crane /usr/local/bin/crane; \
		echo "Crane installed successfully to /usr/local/bin/crane" \
	)

env_print: ## Print a subset of environment variables defined in ".env" file.
	env | grep "GITHUB\|GH_\|GCP_\|FLYTE\|WORKFLOW" | sort

# gh secret set GOOGLE_APPLICATION_CREDENTIALS_DATA --repo="$(GH_REPO)" --body='$(shell cat $(GCP_GACD_PATH))'
ghsecrets: ## Update github secrets for GH_REPO from ".env" file.
	@echo "secrets before updates:"
	@echo
	PAGER=cat gh secret list --repo=$(GH_REPO)
	@echo
	gh secret set FLYTE_CLUSTER_ENDPOINT --repo="$(GH_REPO)" --body="$(FLYTE_CLUSTER_ENDPOINT)"
	gh secret set FLYTE_OAUTH_CLIENT_SECRET --repo="$(GH_REPO)" --body="$(FLYTE_OAUTH_CLIENT_SECRET)"
	gh secret set FLYTECTL_CONFIG --repo="$(GH_REPO)" --body="$(FLYTECTL_CONFIG)"
	gh secret set CODECOV_TOKEN --repo="$(GH_REPO)" --body="$(CODECOV_TOKEN)"
	gh secret set GCP_PROJECT_ID --repo="$(GH_REPO)" --body="$(GCP_PROJECT_ID)"
	gh secret set GCP_STORAGE_SCOPES --repo="$(GH_REPO)" --body="$(GCP_STORAGE_SCOPES)"
	gh secret set GCP_STORAGE_CONTAINER --repo="$(GH_REPO)" --body="$(GCP_STORAGE_CONTAINER)"
	gh secret set GCP_ARTIFACT_REGISTRY_PATH --repo="$(GH_REPO)" --body="$(GCP_ARTIFACT_REGISTRY_PATH)"
	@echo
	@echo secrets after updates:
	@echo
	PAGER=cat gh secret list --repo=$(GH_REPO)

ghvars: ## Update github secrets for GH_REPO from ".env" file.
	@echo "variables before updates:"
	@echo
	PAGER=cat gh variable list --repo=$(GH_REPO)
	@echo
	gh variable set WORKFLOW_IMAGE --repo="$(GH_REPO)" --body="$(WORKFLOW_IMAGE)"
	@echo
	@echo variables after updates:
	@echo
	PAGER=cat gh variable list --repo=$(GH_REPO)

update_config: ## Update flytectl config file from template.
	yq e '.admin.endpoint = strenv(FLYTE_CLUSTER_ENDPOINT) | .storage.stow.config.project_id = strenv(GCP_PROJECT_ID) | .storage.stow.config.scopes = strenv(GCP_STORAGE_SCOPES) | .storage.container = strenv(GCP_STORAGE_CONTAINER)' \
	$(FLYTECTL_CONFIG_TEMPLATE) > $(FLYTECTL_CONFIG)

tree: ## Print directory tree.
	tree -a --dirsfirst -L 4 -I ".git|.direnv|*pycache*|*ruff_cache*|*pytest_cache*|outputs|multirun|conf|scripts|site|*venv*|.coverage"

approve_prs: ## Approve github pull requests from bots: PR_ENTRIES="2-5 10 12-18"
	for entry in $(PR_ENTRIES); do \
		if [[ "$$entry" == *-* ]]; then \
			start=$${entry%-*}; \
			end=$${entry#*-}; \
			for pr in $$(seq $$start $$end); do \
				@gh pr review $$pr --approve; \
			done; \
		else \
			@gh pr review $$entry --approve; \
		fi; \
	done

CURRENT_BRANCH_OR_SHA = $(shell git symbolic-ref --short HEAD 2>/dev/null || git rev-parse HEAD)

get_pr_source_branch: ## Get source branch from detached head as in PR CI checkouts.
ifndef PR
	$(error PR is not set. Usage: make get_pr_source_branch PR=<PR_NUMBER>)
endif

	@echo "Current Branch or SHA: $(CURRENT_BRANCH_OR_SHA)"

	# The command
	# 	gh pr checkout --detach $(PR)
	# checks out the PR source branch commit which is NOT equivalent to checking
	# out the staged merge commit. The latter is what occurs in PR CI checkouts
	# which is available at `refs/pull/$(PR)/merge` and we store in $(PR)-merge
	git fetch --force origin pull/$(PR)/merge:$(PR)-merge
	git checkout $(PR)-merge

	git fetch origin +refs/heads/*:refs/remotes/origin/*
	PAGER=cat git log -1
	@echo "\nExtracted Source Commit SHA:"
	git log -1 --pretty=%B | grep -oE 'Merge [0-9a-f]{40}' | awk '{print $$2}'
	@echo "\nExtracted Source Branch Name:"
	source_commit_sha=$$(git log -1 --pretty=%B | grep -oE 'Merge [0-9a-f]{40}' | awk '{print $$2}') && \
	git branch -r --contains $$source_commit_sha | grep -v HEAD | sed -n 's|origin/||p' | xargs

	@echo "\nReturning to Branch or SHA: $(CURRENT_BRANCH_OR_SHA)"
	git checkout $(CURRENT_BRANCH_OR_SHA)
