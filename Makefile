.DEFAULT_GOAL := help

UV_RUN := uv run --frozen
PYTEST_ARGS ?=
TESTS ?=
EVAL_ARGS ?=

.PHONY: help setup hooks fix lint typecheck test test-fast test-lean test-failed build validate agent-eval

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

typecheck: ## Run strict static type checking.
	$(UV_RUN) mypy

test: ## Run tests; narrow with TESTS=... and PYTEST_ARGS=....
	$(UV_RUN) pytest -m "not lean_runtime" $(TESTS) $(PYTEST_ARGS)

test-fast: ## Run the sequential non-integration feedback loop.
	$(UV_RUN) pytest -n 0 -m "not integration and not end_to_end" $(PYTEST_ARGS)

test-lean: ## Run pinned Lean integration tests serially.
	$(UV_RUN) pytest -n 0 -m lean_runtime $(PYTEST_ARGS)

test-failed: ## Re-run failures from the previous pytest invocation.
	$(UV_RUN) pytest --lf $(PYTEST_ARGS)

build: ## Build Python source and wheel distributions.
	uv build

validate: lint typecheck test test-lean build ## Run complete local validation.

agent-eval: ## Plan a local agent eval; execution requires explicit EVAL_ARGS.
	$(UV_RUN) python benchmarks/agent_ab.py $(EVAL_ARGS)
