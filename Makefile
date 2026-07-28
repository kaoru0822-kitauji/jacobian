.DEFAULT_GOAL := help

UV_RUN := uv run --locked
PYTEST_ARGS ?=
TESTS ?=
EVAL_ARGS ?=
CORE_TEST_PATHS := tests/unit tests/contract tests/checkers tests/reference
INTEGRATION_TEST_PATHS := tests/integration tests/end_to_end
RUFF_PATHS := src tests benchmarks
PYTEST_XDIST_ARGS := -n auto --maxprocesses=4 --dist=worksteal

.PHONY: help setup hooks fix lint lint-full security-audit typecheck test test-fast test-core test-integration test-contracts test-checkers test-mcp test-storage test-lean test-failed test-stress test-ordering duplicate-code npm-test todo-check coverage build check precommit check-static validate-full agent-eval bench-core clean docs-linkcheck

help: ## Show available developer commands.
	@awk 'BEGIN {FS = ":.*## "; printf "Jacobian developer commands:\n\n"} /^[a-zA-Z_-]+:.*## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Install the locked development environment.
	uv sync --locked --dev

hooks: setup ## Install pre-commit hooks.
	$(UV_RUN) pre-commit install --install-hooks
	$(UV_RUN) pre-commit install --hook-type pre-push

fix: ## Apply Ruff fixes and formatting.
	$(UV_RUN) ruff check --fix $(RUFF_PATHS)
	$(UV_RUN) ruff format $(RUFF_PATHS)

lint: ## Run the fast Ruff lint and format checks.
	$(UV_RUN) ruff check $(RUFF_PATHS)
	$(UV_RUN) ruff format --check $(RUFF_PATHS)

lint-full: lint ## Add dependency and dead-code checks.
	$(UV_RUN) deptry .
	$(UV_RUN) vulture src tests --min-confidence=80

security-audit: ## Audit dependencies for known vulnerabilities.
	$(UV_RUN) pip-audit

typecheck: ## Run strict static type checking.
	$(UV_RUN) mypy

test: ## Run tests; narrow with TESTS=... and PYTEST_ARGS=....
	$(UV_RUN) pytest $(PYTEST_XDIST_ARGS) -m "not lean_runtime" $(TESTS) $(PYTEST_ARGS)

test-fast: ## Sequential core edit loop (unit/contract/checkers/reference, no xdist).
	$(UV_RUN) pytest -n 0 -m "not lean_runtime and not slow" \
		$(if $(TESTS),$(TESTS),$(CORE_TEST_PATHS)) $(PYTEST_ARGS)

test-core: ## Parallel core suites (same paths as test-fast, uses xdist by default).
	$(UV_RUN) pytest $(PYTEST_XDIST_ARGS) -m "not lean_runtime" \
		$(if $(TESTS),$(TESTS),$(CORE_TEST_PATHS)) $(PYTEST_ARGS)

test-integration: ## Run the directory-owned integration suites.
	$(UV_RUN) pytest $(PYTEST_XDIST_ARGS) -m "not lean_runtime" \
		$(if $(TESTS),$(TESTS),$(INTEGRATION_TEST_PATHS)) $(PYTEST_ARGS)

test-contracts: ## Run contract tests.
	$(UV_RUN) pytest -n 0 tests/contract $(PYTEST_ARGS)

test-checkers: ## Run independent checker tests.
	$(UV_RUN) pytest -n 0 tests/checkers $(PYTEST_ARGS)

test-mcp: ## Run focused local and remote MCP integration tests.
	$(UV_RUN) pytest -n 0 tests/integration/infrastructure/test_mcp_adapter.py \
		tests/integration/infrastructure/test_remote_mcp.py $(PYTEST_ARGS)

test-storage: ## Run artifact, registry, and workspace integration tests.
	$(UV_RUN) pytest -n 0 tests/integration/infrastructure/test_artifact_store.py \
		tests/integration/infrastructure/test_checker_registry.py \
		tests/integration/infrastructure/test_plugin_registry_snapshots.py \
		tests/integration/infrastructure/test_workspace_revisions.py \
		tests/integration/infrastructure/test_workspace_lifecycle.py \
		tests/integration/infrastructure/test_workspace_scaling.py \
		tests/integration/infrastructure/test_workspace_invalidation.py \
		$(PYTEST_ARGS)

test-lean: ## Run pinned Lean tests serially; narrow with TESTS=... and PYTEST_ARGS=....
	$(UV_RUN) pytest -n 0 -m lean_runtime $(TESTS) $(PYTEST_ARGS)

test-failed: ## Re-run failures from the previous pytest invocation.
	$(UV_RUN) pytest $(PYTEST_XDIST_ARGS) --lf -m "not lean_runtime" $(PYTEST_ARGS)

test-stress: ## Reproduce scheduled property stress (pytest-repeat --count=3).
	$(UV_RUN) pytest -m "property and not lean_runtime" --count=3 $(PYTEST_ARGS)

test-ordering: ## Reproduce scheduled ordering with PYTEST_ARGS=--randomly-seed=N.
	$(UV_RUN) pytest -m "not lean_runtime" $(PYTEST_ARGS)

duplicate-code: ## Run the CI duplicate-code detector locally.
	npx --yes jscpd@5.0.12 --config .jscpd.json .

npm-test: ## Run the npm package tests and dry-run pack.
	npm test --prefix npm
	npm pack --dry-run --prefix npm

todo-check: ## Fail on TODO comments that do not reference an issue.
	@violations="$$(rg --pcre2 -n 'TODO(?!\(#\d+\))' --type py src/ tests/ || true)"; \
	if [ -n "$$violations" ]; then \
	  printf '%s\n' "$$violations"; \
	  echo "TODO comments must reference an issue, e.g. TODO(#123)." >&2; \
	  exit 1; \
	fi

coverage: ## Combine coverage data files and enforce the repository threshold.
	$(UV_RUN) coverage combine
	$(UV_RUN) coverage report --fail-under=50
	$(UV_RUN) coverage xml

build: ## Build Python source and wheel distributions.
	uv build

check: lint typecheck test-fast ## Run the fast routine local handoff checks.

precommit: ## Fix and run every routine local handoff check.
	$(MAKE) fix
	$(MAKE) check

check-static: lint-full typecheck todo-check build ## Run CI-owned static checks plus a local package build.

validate-full: lint-full typecheck test test-lean build ## Run broad local validation (slow; omits security/duplicate/npm CI lanes).

agent-eval: ## Plan a local agent eval; execution requires explicit EVAL_ARGS.
	$(UV_RUN) python benchmarks/agent_ab.py $(EVAL_ARGS)

bench-core: ## Run the core performance benchmark script.
	$(UV_RUN) python benchmarks/benchmark_core.py

clean: ## Remove local caches, build outputs, and coverage artifacts.
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build htmlcov
	rm -f .coverage .coverage.*
	find src tests benchmarks -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -maxdepth 2 -type d -name '*.egg-info' -prune -exec rm -rf {} +

docs-linkcheck: ## Check relative Markdown links in project docs.
	npx --yes markdown-link-check@3.15.0 \
		--config .markdown-link-check.json -q \
		README.md AGENTS.md CONTRIBUTING.md docs
