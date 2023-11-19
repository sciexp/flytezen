.DEFAULT_GOAL := help

ENV_PREFIX ?= ./
ENV_FILE := $(wildcard $(ENV_PREFIX)/.env)

ifeq ($(strip $(ENV_FILE)),)
$(info $(ENV_PREFIX)/.env file not found, skipping inclusion)
else
include $(ENV_PREFIX)/.env
export
endif

##@ Utility
help: ## Display this help. (Default)
# based on "https://gist.github.com/prwhite/8168133?permalink_comment_id=4260260#gistcomment-4260260"
	@grep -hE '^[A-Za-z0-9_ \-]*?:.*##.*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

##@ Utility
help_sort: ## Display alphabetized version of help.
	@grep -hE '^[A-Za-z0-9_ \-]*?:.*##.*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

#---------
# flytezen
#---------

test: ## Run tests. See pyproject.toml for configuration.
	poetry run pytest

test-cov-xml: ## Run tests with coverage
	poetry run pytest --cov-report=xml

lint: ## Run linter
	poetry run black .
	poetry run ruff --fix .

lint-check: ## Run linter in check mode
	poetry run black --check .
	poetry run ruff .

typecheck: ## Run typechecker
	poetry run pyright

#------------------
# local dev cluster
#------------------

local_image: ## Build local image.
	@echo "building image: $(WORKFLOW_IMAGE):$(GIT_BRANCH)"
	@echo
	docker images -a $(WORKFLOW_IMAGE)
	@echo
	docker build -t $(WORKFLOW_IMAGE):$(GIT_BRANCH) -f $(ACTIVE_DOCKERFILE) .
	@echo
	docker push $(WORKFLOW_IMAGE):$(GIT_BRANCH)
	@echo
	docker images -a $(WORKFLOW_IMAGE)

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

GIT_SHORT_SHA = $(shell git rev-parse --short HEAD)
GIT_BRANCH = $(shell git rev-parse --abbrev-ref HEAD)
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

.PHONY: run
run: ## Run registered workflow (sync).
	poetry run flytezen

multirun: ## Run registered workflow (sync) with multiple hyperparameter sets.
	poetry run flytezen --multirun workflow.hyperparameters.C=0.2,0.5

run_async: ## Run registered workflow (async).
	poetry run flytezen workflow.wait=False

run_unregistered: ## Dispatch unregistered run from flytekit cli
	pyflyte run \
	--remote \
	--project $(WORKFLOW_PROJECT) \
	--domain $(WORKFLOW_DOMAIN) \
	--image $(WORKFLOW_IMAGE):$(GIT_BRANCH) \
	$(WORKFLOW_FILE) \
	$(WORKFLOW_NAME) \
	--hyperparameters $(WORKFLOW_FILE_WORKFLOW_ARGS)

run_local: ## Dispatch unregistered run from flytekit cli
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

docker_login: ## Login to ghcr docker registry. Check regcreds in $HOME/.docker/config.json.
	docker login ghcr.io -u $(GH_ORG) -p $(GITHUB_TOKEN)

tag_images: ## Tag latest docker images.
	crane tag $(WORKFLOW_IMAGE):$(WORKFLOW_IMAGE_TAG) $(GLOBAL_IMAGE_TAG)
	crane tag ghcr.io/$(GH_ORG)/$(GH_REPO):$(WORKFLOW_IMAGE_TAG) $(GLOBAL_IMAGE_TAG)

#-------------
# system / dev
#-------------

install_direnv: ## Install direnv to `/usr/local/bin`. Check script before execution: https://direnv.net/ .
	@which direnv > /dev/null || \
	(curl -sfL https://direnv.net/install.sh | bash && \
	sudo install -c -m 0755 direnv /usr/local/bin && \
	rm -f ./direnv)
	@echo "see https://direnv.net/docs/hook.html"

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
	gh variable set WORKFLOW_PROJECT --repo="$(GH_REPO)" --body="$(WORKFLOW_PROJECT)"
	gh variable set WORKFLOW_DOMAIN --repo="$(GH_REPO)" --body="$(WORKFLOW_DOMAIN)"
	gh variable set WORKFLOW_NAME --repo="$(GH_REPO)" --body="$(WORKFLOW_NAME)"
	gh variable set WORKFLOW_PACKAGE_PATH --repo="$(GH_REPO)" --body="$(WORKFLOW_PACKAGE_PATH)"
	gh variable set WORKFLOW_IMPORT_PATH --repo="$(GH_REPO)" --body="$(WORKFLOW_IMPORT_PATH)"
	gh variable set WORKFLOW_IMAGE --repo="$(GH_REPO)" --body="$(WORKFLOW_IMAGE)"
	gh variable set WORKFLOW_REGISTRATION_MODE --repo="$(GH_REPO)" --body="prod"
	@echo
	@echo variables after updates:
	@echo
	PAGER=cat gh variable list --repo=$(GH_REPO)

update_config: ## Update flytectl config file from template.
	yq e \
		'.admin.endpoint = strenv(FLYTE_CLUSTER_ENDPOINT) | \
		.storage.stow.config.project_id = strenv(GCP_PROJECT_ID) | \
		.storage.stow.config.scopes = strenv(GCP_STORAGE_SCOPES) | \
		.storage.container = strenv(GCP_STORAGE_CONTAINER)' \
		.flyte/config-template.yaml > .flyte/config.yaml

tree: ## Print directory tree.
	tree -a --dirsfirst -L 4 -I ".git|.direnv|*pycache*|*ruff_cache*|*pytest_cache*|outputs|multirun|.vscode|conf|scripts"

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
