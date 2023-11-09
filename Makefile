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

#-------------
# flyte
#-------------

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

get_workflow: ## Get workflow representation ( dot, yaml, doturl, json ).
	@printf "\033[1;34m\n$$WORKFLOW_NAME:\n\n\033[0m"
	@echo "config file: $$FLYTECTL_CONFIG"
	flytectl get workflows \
		--project $(WORKFLOW_PROJECT) \
		--domain $(WORKFLOW_DOMAIN) \
		--version $(WORKFLOW_VERSION) \
		-o $(WORKFLOW_OUTPUT_FORMAT) \
		$(WORKFLOW_NAME)

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

package_workflows: ## Package workflows.
	@printf "\033[1;34m\nPACKAGE WORKFLOWS:\n\n\033[0m"
	@echo "config file: $$FLYTECTL_CONFIG"
	pyflyte \
		--pkgs workflows \
		package \
		--image $(WORKFLOW_IMAGE) \
		--force

register_workflows: ## Register workflows.
	@printf "\033[1;34m\nREGISTER WORKFLOWS:\n\n\033[0m"
	@echo "config file: $$FLYTECTL_CONFIG"
	flytectl register files \
		--project $(WORKFLOW_PROJECT) \
		--domain $(WORKFLOW_DOMAIN) \
		--archive flyte-package.tgz \
		--version "$$(git rev-parse HEAD)"

package_and_register: ## Package and register workflows.
package_and_register: package_workflows register_workflows 

#-------------
# CI
#-------------

ci: ## Run CI with debug enabled.
	gh workflow run "CI" --ref main -f debug_enabled=true


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

env_print: ## Print a subset of environment variables defined in ".env" file.
	env | grep "GITHUB\|GH_\|GCP_\|FLYTE\|WORKFLOW" | sort

# gh secret set GOOGLE_APPLICATION_CREDENTIALS_DATA --repo="$(GH_REPO)" --body='$(shell cat $(GCP_GACD_PATH))'
# gh secret set CODECOV_TOKEN --repo="$(GH_REPO)" --body="$(CODECOV_TOKEN)"
# gh secret set GCP_SERVICE_ACCOUNT --repo="$(GH_REPO)" --body="$(GCP_SERVICE_ACCOUNT)"
# gh secret set TEST_PYPI_TOKEN --repo="$(GH_REPO)" --body="$(TEST_PYPI_TOKEN)"
ghsecrets: ## Update github secrets for GH_REPO from ".env" file.
	gh secret list --repo=$(GH_REPO)
	gh secret set FLYTE_CLUSTER_ENDPOINT --repo="$(GH_REPO)" --body="$(FLYTE_CLUSTER_ENDPOINT)"
	gh secret set FLYTE_OAUTH_CLIENT_SECRET --repo="$(GH_REPO)" --body="$(FLYTE_OAUTH_CLIENT_SECRET)"
	gh secret set FLYTECTL_CONFIG --repo="$(GH_REPO)" --body="$(FLYTECTL_CONFIG)"
	gh secret set GCP_PROJECT_ID --repo="$(GH_REPO)" --body="$(GCP_PROJECT_ID)"
	gh secret set GCP_STORAGE_SCOPES --repo="$(GH_REPO)" --body="$(GCP_STORAGE_SCOPES)"
	gh secret set GCP_STORAGE_CONTAINER --repo="$(GH_REPO)" --body="$(GCP_STORAGE_CONTAINER)"
	gh secret set WORKFLOW_PROJECT --repo="$(GH_REPO)" --body="$(WORKFLOW_PROJECT)"
	gh secret set WORKFLOW_DOMAIN --repo="$(GH_REPO)" --body="$(WORKFLOW_DOMAIN)"
	gh secret set WORKFLOW_NAME --repo="$(GH_REPO)" --body="$(WORKFLOW_NAME)"
	gh secret list --repo=$(GH_REPO)

update_config: ## Update flytectl config file from template.
	yq ea \
		'.admin.endpoint = strenv(FLYTE_CLUSTER_ENDPOINT) | \
		.storage.stow.config.project_id = strenv(GCP_PROJECT_ID) | \
		.storage.stow.config.scopes = strenv(GCP_STORAGE_SCOPES) | \
		.storage.container = strenv(GCP_STORAGE_CONTAINER)' \
		config-template.yaml > config.yaml

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