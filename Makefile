.DEFAULT_GOAL := help

UV_RUN := uv run --frozen
PYTEST_ARGS ?=
TESTS ?=
EVAL_ARGS ?=

.PHONY: help setup hooks fix lint typecheck test test-fast test-lean test-failed refresh-test-durations refresh-lean-test-durations build check validate agent-eval

help: ## Show available developer commands.
	@awk 'BEGIN {FS = ":.*## "; printf "Jacobian developer commands:\n\n"} /^[a-zA-Z_-]+:.*## / {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Install the locked development environment.
	uv sync --locked --dev

hooks: setup ## Install pre-commit hooks.
	$(UV_RUN) pre-commit install --install-hooks

fix: ## Apply Ruff fixes and formatting.
	$(UV_RUN) ruff check --fix .
	$(UV_RUN) ruff format .

lint: ## Check lint, formatting, and dependency declarations.
	$(UV_RUN) ruff check .
	$(UV_RUN) ruff format --check .
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

test-lean: ## Run pinned Lean integration tests serially.
	$(UV_RUN) pytest -n 0 -m lean_runtime $(PYTEST_ARGS)

test-failed: ## Re-run failures from the previous pytest invocation.
	$(UV_RUN) pytest --lf -m "not lean_runtime" $(PYTEST_ARGS)

refresh-test-durations: ## Refresh CI shard timings after major suite changes.
	@test "$$(uname -s)" = "Linux" || { \
		echo "refresh-test-durations requires Linux"; exit 2; \
	}
	@$(UV_RUN) python -c 'import sys; expected = (3, 12); actual = sys.version_info[:2]; sys.exit(f"refresh-test-durations requires Python {expected[0]}.{expected[1]}, got {actual[0]}.{actual[1]}") if actual != expected else None'
	@durations=$$(mktemp .test_durations.XXXXXX); \
	trap 'rm -f "$$durations"' EXIT; \
	printf '{}\n' > "$$durations"; \
	$(UV_RUN) pytest -m "not lean_runtime" --store-durations \
		--clean-durations --durations-path "$$durations" && \
	chmod 0644 "$$durations" && \
	mv "$$durations" .test_durations

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

check: lint typecheck test-fast build ## Run the routine local pre-push checks.

validate: lint typecheck test test-lean build ## Run complete local validation.

agent-eval: ## Plan a local agent eval; execution requires explicit EVAL_ARGS.
	$(UV_RUN) python benchmarks/agent_ab.py $(EVAL_ARGS)
