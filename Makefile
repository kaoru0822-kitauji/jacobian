.DEFAULT_GOAL := help

UV_RUN := uv run --locked
PYTEST_ARGS ?=
TESTS ?=
EVAL_ARGS ?=
CORE_TEST_PATHS := tests/unit tests/contract tests/checkers tests/reference
INTEGRATION_TEST_PATHS := tests/integration tests/end_to_end

.PHONY: help setup hooks fix lint lint-full typecheck test test-fast test-core test-integration test-contracts test-checkers test-mcp test-storage test-lean test-failed build check check-static validate-full agent-eval

help: ## Show available developer commands.
	@awk 'BEGIN {FS = ":.*## "; printf "Jacobian developer commands:\n\n"} /^[a-zA-Z_-]+:.*## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Install the locked development environment.
	uv sync --locked --dev

hooks: setup ## Install pre-commit hooks.
	$(UV_RUN) pre-commit install --install-hooks

fix: ## Apply Ruff fixes and formatting.
	$(UV_RUN) ruff check --fix .
	$(UV_RUN) ruff format .

lint: ## Run the fast Ruff lint and format checks.
	$(UV_RUN) ruff check .
	$(UV_RUN) ruff format --check .

lint-full: lint ## Add dependency and dead-code checks.
	$(UV_RUN) deptry .
	$(UV_RUN) vulture src tests --min-confidence=80

security-audit: ## Audit dependencies for known vulnerabilities.
	$(UV_RUN) pip-audit

typecheck: ## Run strict static type checking.
	$(UV_RUN) mypy

test: ## Run tests; narrow with TESTS=... and PYTEST_ARGS=....
	$(UV_RUN) pytest -m "not lean_runtime" $(TESTS) $(PYTEST_ARGS)

test-fast: ## Run the sequential core feedback loop.
	$(UV_RUN) pytest -n 0 -m "not lean_runtime" \
		$(if $(TESTS),$(TESTS),$(CORE_TEST_PATHS)) $(PYTEST_ARGS)

test-core: ## Run the directory-owned core suites.
	$(UV_RUN) pytest -m "not lean_runtime" \
		$(if $(TESTS),$(TESTS),$(CORE_TEST_PATHS)) $(PYTEST_ARGS)

test-integration: ## Run the directory-owned integration suites.
	$(UV_RUN) pytest -m "not lean_runtime" \
		$(if $(TESTS),$(TESTS),$(INTEGRATION_TEST_PATHS)) $(PYTEST_ARGS)

test-contracts: ## Run contract tests.
	$(UV_RUN) pytest -n 0 tests/contract $(PYTEST_ARGS)

test-checkers: ## Run independent checker tests.
	$(UV_RUN) pytest -n 0 tests/checkers $(PYTEST_ARGS)

test-mcp: ## Run focused local and remote MCP integration tests.
	$(UV_RUN) pytest -n 0 tests/integration/test_mcp_adapter.py \
		tests/integration/test_remote_mcp.py $(PYTEST_ARGS)

test-storage: ## Run artifact, registry, and workspace integration tests.
	$(UV_RUN) pytest -n 0 tests/integration/test_artifact_store.py \
		tests/integration/test_checker_registry.py \
		tests/integration/test_plugin_registry_snapshots.py \
		tests/integration/test_workspaces.py $(PYTEST_ARGS)

test-lean: ## Run pinned Lean tests serially; narrow with TESTS=... and PYTEST_ARGS=....
	$(UV_RUN) pytest -n 0 -m lean_runtime $(TESTS) $(PYTEST_ARGS)

test-failed: ## Re-run failures from the previous pytest invocation.
	$(UV_RUN) pytest --lf -m "not lean_runtime" $(PYTEST_ARGS)

build: ## Build Python source and wheel distributions.
	uv build

check: lint test-fast ## Run the fast routine local handoff checks.

check-static: lint-full typecheck build ## Run CI-owned static and package checks locally.

validate-full: lint-full typecheck test test-lean build ## Run broad local validation (slow and exceptional; not every CI lane).

agent-eval: ## Plan a local agent eval; execution requires explicit EVAL_ARGS.
	$(UV_RUN) python benchmarks/agent_ab.py $(EVAL_ARGS)
