.DEFAULT_GOAL := help

UV_RUN := uv run --frozen
PYTEST_ARGS ?=
TESTS ?=
EVAL_ARGS ?=

.PHONY: help setup hooks fix lint lint-full typecheck test test-fast test-contracts test-checkers test-mcp test-storage test-lean test-failed refresh-lean-test-durations build check check-static validate-full agent-eval

help: ## Show available developer commands.
	@awk 'BEGIN {FS = ":.*## "; printf "Jacobian developer commands:\n\n"} /^[a-zA-Z_-]+:.*## / {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

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

test-fast: ## Run the sequential non-integration feedback loop.
	$(UV_RUN) pytest -n 0 -m "not integration and not end_to_end and not lean_runtime" \
		tests/unit tests/contract tests/checkers tests/reference $(PYTEST_ARGS)

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

refresh-lean-test-durations: ## Refresh Lean CI shard timings serially.
	@durations=$$(mktemp .lean_test_durations.XXXXXX); \
	trap 'rm -f "$$durations"' EXIT; \
	printf '{}\n' > "$$durations"; \
	$(UV_RUN) pytest -n 0 -m lean_runtime --store-durations \
		--clean-durations --durations-path "$$durations" && \
	chmod 0644 "$$durations" && \
	mv "$$durations" .lean_test_durations

build: ## Build Python source and wheel distributions.
	uv build

check: lint test-fast ## Run the fast routine local handoff checks.

check-static: lint-full typecheck build ## Run CI-owned static and package checks locally.

validate-full: lint-full typecheck test test-lean build ## Reproduce exhaustive CI validation locally (slow and exceptional).

agent-eval: ## Plan a local agent eval; execution requires explicit EVAL_ARGS.
	$(UV_RUN) python benchmarks/agent_ab.py $(EVAL_ARGS)
