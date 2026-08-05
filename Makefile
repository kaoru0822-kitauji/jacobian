.DEFAULT_GOAL := help

UV_RUN := uv run --locked
HARBOR_VERSION ?= 0.20.0
HARBOR_RUNNER ?= uvx --from harbor==$(HARBOR_VERSION) harbor
HARBOR_PYTHON ?= uvx --from harbor==$(HARBOR_VERSION) --with tomli-w==1.2.0 --with jsonschema python
# Validation pytest is process-isolated under xdist; Path monkeypatches stay
# worker-local. Oracle/adapter Make targets remain serial.
HARBOR_VALIDATION_WORKERS ?= 2
PYTEST_ARGS ?=
TESTS ?=
EVAL_ARGS ?=
STRESS_COUNT ?= 3
ORDERING_DEFAULT_SEED := --randomly-seed=17
PYTEST_DIAGNOSTIC_ARGS ?= --durations=10
RUFF_PATHS := src tests benchmarks
TOPOLOGY_RUNNER := $(UV_RUN) python tools/test_topology.py
PUBLIC_COMMANDS := help setup check check-changed ci-plan test-plan test-changed test-unit test-component test-domain test-composition test-storage test-process test-mcp test-provider test-lean test-e2e docs-command-check docs-linkcheck harbor-plan harbor-check-task harbor-oracle-task symbolic-coordination-trajectory-telemetry symbolic-coordination-comparison-report symbolic-coordination-closeout-report npm-test test-all-ci check-static deploy-check

ifneq ($(strip $(PATHS)),)
PATHS_FILE := $(shell mktemp)
$(file >$(PATHS_FILE),$(PATHS))
endif

# A timeout is a lane-level containment policy.  It intentionally does not live
# in pyproject.toml: direct pytest invocations must not silently inherit a
# signal-based deadline that cannot interrupt a native solver.  Process and
# provider lanes run risky work in killable children and set their own deadline.
.PHONY: help help-all uv-version-check setup setup-agent container-image eval-image eval-image-pull eval-image-bind hooks fix lint complexity-check lint-full security-audit typecheck test-architecture architecture ci-plan test-plan test-changed check-changed test-unit test-component test-domain test-composition test-storage test-process test-mcp test-provider test-lean test-e2e test-affected test-all-ci test-compatibility test-stress test-ordering duplicate-code npm-test todo-check coverage build check precommit check-static harbor-plan harbor-sync harbor-contracts harbor-adapter-checks harbor-validation-tests harbor-validate harbor-check harbor-check-task benchmark-inventory benchmark-snapshot benchmark-snapshot-validate benchmark-publish harbor-oracle harbor-oracle-task harbor-oracle-run harbor-oracle-all harbor-adapter-check heldout-validate heldout-render heldout-smoke agent-eval agent-eval-validate agent-eval-compare symbolic-coordination-codex-preflight symbolic-coordination-codex-dry-run symbolic-coordination-codex-eval symbolic-coordination-trajectory-telemetry symbolic-coordination-comparison-plan symbolic-coordination-comparison-run symbolic-coordination-comparison-report symbolic-coordination-closeout-plan symbolic-coordination-closeout-run symbolic-coordination-closeout-report provider-eval clean docs-command-check docs-linkcheck deploy-check

help: ## Show available developer commands.
	@awk -v public="$(PUBLIC_COMMANDS)" 'BEGIN {FS = ":.*## "; n = split(public, names, " "); for (i = 1; i <= n; i++) wanted[names[i]] = 1; printf "Jacobian common developer commands:\n\n"} /^[a-zA-Z_-]+:.*## / && ($$1 in wanted) {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf '\nAdvanced lifecycle and diagnostic commands are hidden from the daily index. Use `make help-all` to list them.\n'

help-all: ## Show every low-level and lifecycle developer command.
	@awk 'BEGIN {FS = ":.*## "; printf "All Jacobian developer commands:\n\n"} /^[a-zA-Z_-]+:.*## / {printf "  %-26s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

uv-version-check: ## Require the repository-pinned uv release.
	@test "$$(uv --version | awk '{print $$2}')" = "$$(tr -d '[:space:]' < .uv-version)" || { \
		echo "install uv $$(tr -d '[:space:]' < .uv-version) before using this checkout" >&2; \
		exit 2; \
	}

setup: uv-version-check ## Install the locked development environment.
	uv sync --locked --dev

setup-agent: ## Configure an agent against this source checkout (ARGS="--client codex --profile full-python").
	./scripts/setup-agent $(ARGS)

JACOBIAN_REGISTRY_IMAGE ?= ghcr.io/morluto/jacobian

container-image: ## Build jacobian:local from the current tree, including dirty changes.
	$(UV_RUN) python tools/manage_jacobian_image.py build --image "$(or $(IMAGE),jacobian:local)"

eval-image: ## Select a published digest for a clean tree or build jacobian:local when dirty.
	$(UV_RUN) python tools/manage_jacobian_image.py select --registry-image "$(JACOBIAN_REGISTRY_IMAGE)"

eval-image-pull: ## Pull the current clean revision and print its digest-pinned image reference.
	$(UV_RUN) python tools/manage_jacobian_image.py pull --registry-image "$(JACOBIAN_REGISTRY_IMAGE)"

eval-image-bind: ## Bind image identity into RUNTIME_SNAPSHOT (JACOBIAN_IMAGE=..., RUNTIME_SNAPSHOT=...).
	@test -n "$(JACOBIAN_IMAGE)" -a -n "$(RUNTIME_SNAPSHOT)" || { echo "JACOBIAN_IMAGE and RUNTIME_SNAPSHOT are required" >&2; exit 2; }
	$(UV_RUN) python tools/manage_jacobian_image.py bind-runtime \
		--image "$(JACOBIAN_IMAGE)" --runtime-snapshot "$(RUNTIME_SNAPSHOT)"

deploy-check: ## Validate the clone-to-systemd deployment entrypoint.
	bash -n deploy/install.sh
	$(UV_RUN) pytest -n 0 tests/boundary/process/tooling/test_deploy_installer.py

hooks: setup ## Install pre-commit hooks.
	$(UV_RUN) pre-commit install --install-hooks
	$(UV_RUN) pre-commit install --hook-type pre-push

fix: ## Apply Ruff fixes and formatting.
	$(UV_RUN) ruff check --fix $(RUFF_PATHS)
	$(UV_RUN) ruff format $(RUFF_PATHS)

lint: ## Run the fast Ruff lint and format checks.
	$(UV_RUN) ruff check $(RUFF_PATHS)
	$(UV_RUN) ruff format --check $(RUFF_PATHS)
	$(MAKE) complexity-check

complexity-check: ## Reject new, increased, or stale C901 baseline entries.
	$(UV_RUN) python tools/check_complexity.py

lint-full: lint ## Add dependency and dead-code checks.
	$(UV_RUN) deptry .
	$(UV_RUN) vulture src tests --min-confidence=80

security-audit: ## Audit dependencies for known vulnerabilities.
	$(UV_RUN) pip-audit

typecheck: ## Run strict static type checking.
	$(UV_RUN) mypy

test-architecture: ## Enforce semantic test-layer and provider-import boundaries.
	$(UV_RUN) python tools/check_test_architecture.py .

architecture: ## Enforce product source boundary invariants (subprocess, shutil.which, environ, contracts, surfaces).
	$(UV_RUN) python tools/check_architecture.py

test-plan: ## Print local validation selected for BASE..HEAD or explicit PATHS.
	@if [ -n "$(PATHS)" ]; then \
		trap 'rm -f "$(PATHS_FILE)"' EXIT; \
		$(UV_RUN) python .github/scripts/plan-local-tests --paths-file "$(PATHS_FILE)"; \
	else \
		test -n "$(BASE)" || { echo "BASE is required unless PATHS is set (for example: make test-plan BASE=origin/main)" >&2; exit 2; }; \
		$(UV_RUN) python .github/scripts/plan-local-tests --base "$(BASE)"; \
	fi

ci-plan: ## Print the hosted CI lane plan for BASE..HEAD and working changes.
	@set -eu; \
	tmp_dir=$$(mktemp -d); \
	trap 'rm -rf "$$tmp_dir"; if [ -n "$(PATHS_FILE)" ]; then rm -f "$(PATHS_FILE)"; fi' EXIT; \
	base_sha=$$(git rev-parse "$(or $(BASE),origin/main)"); \
	head_sha=$$(git rev-parse HEAD); \
	if [ -n "$(PATHS)" ]; then \
		$(UV_RUN) python .github/scripts/normalize-ci-paths --file "$(PATHS_FILE)" > "$$tmp_dir/changed-paths.txt"; \
	else \
		{ \
			git diff --name-only "$(or $(BASE),origin/main)" HEAD; \
			git diff --name-only HEAD; \
			git diff --cached --name-only; \
			git ls-files --others --exclude-standard; \
		} | sort -u > "$$tmp_dir/changed-paths.txt"; \
	fi; \
	if [ -n "$(PATHS)" ]; then \
		$(UV_RUN) python .github/scripts/classify-ci-paths --paths-file "$(PATHS_FILE)" > "$$tmp_dir/plan.txt"; \
	else \
		changed_paths=$$(tr '\n' ' ' < "$$tmp_dir/changed-paths.txt"); \
		$(UV_RUN) python .github/scripts/classify-ci-paths -- $$changed_paths > "$$tmp_dir/plan.txt"; \
	fi; \
	$(UV_RUN) python .github/scripts/validate-ci-plan < "$$tmp_dir/plan.txt"; \
	$(UV_RUN) python .github/scripts/emit-plan-receipt \
		--kind product-ci --event pull_request \
		--base "$$base_sha" --head "$$head_sha" \
		--planner .github/scripts/classify-ci-paths \
		--config .github/ci-impact.json --config tests/topology.toml \
		--config .github/scripts/_ci_paths.py \
		--config .github/scripts/validate-ci-plan \
		--config .github/workflows/ci.yml --config Makefile \
		--plan-file "$$tmp_dir/plan.txt" \
		--paths-file "$$tmp_dir/changed-paths.txt" \
		--output "$$tmp_dir/receipt.json" >/dev/null; \
	echo "Hosted CI lanes:"; \
	cat "$$tmp_dir/plan.txt"; \
	echo "Plan receipt:"; \
	cat "$$tmp_dir/receipt.json"

test-changed: ## Run changed-path tests, defaulting BASE to origin/main.
	@if [ -n "$(PATHS)" ]; then \
		trap 'rm -f "$(PATHS_FILE)"' EXIT; \
		$(UV_RUN) python .github/scripts/plan-local-tests --paths-file "$(PATHS_FILE)" --execute; \
	else \
		$(UV_RUN) python .github/scripts/plan-local-tests --base "$(or $(BASE),origin/main)" --execute; \
	fi

check-changed: ## Run format, types, and exact changed-path tests.
	$(MAKE) lint typecheck
	$(MAKE) test-changed BASE="$(or $(BASE),origin/main)"

define run_topology_lane
	PYTEST_ADDOPTS="$(PYTEST_DIAGNOSTIC_ARGS) $(PYTEST_ARGS)" \
		$(TOPOLOGY_RUNNER) $(1) $(if $(TESTS),$(TESTS))
endef

test-unit: ## Run pure contracts and models (10s lane, sequential).
	$(call run_topology_lane,unit)

test-component: ## Run one-service component tests (30s lane, four workers).
	$(call run_topology_lane,component)

test-domain: ## Run explicitly bundled mathematical domains (120s lane).
	$(call run_topology_lane,domain)

test-composition: ## Run complete-runtime composition tests (120s, two workers).
	$(call run_topology_lane,composition)

test-storage: ## Run SQLite durability and recovery boundaries (serial).
	$(call run_topology_lane,storage)

test-process: ## Run killable child-process boundaries (two workers).
	$(call run_topology_lane,process)

test-mcp: ## Run MCP transport boundaries (two workers).
	$(call run_topology_lane,mcp)

test-provider: ## Run prepared optional-provider boundaries (one worker).
	$(call run_topology_lane,provider)

test-lean: ## Run the pinned Lean/Mathlib boundary serially.
	$(call run_topology_lane,lean)

test-e2e: ## Run complete user-visible CLI/workflow scenarios serially.
	$(call run_topology_lane,e2e)

test-compatibility: ## Run the small supported-version import/API compatibility smoke suite.
	$(UV_RUN) pytest -n 0 --timeout=30 --timeout-method=thread tests/unit/tooling/test_ci_compatibility.py $(PYTEST_DIAGNOSTIC_ARGS) $(PYTEST_ARGS)

test-affected: test-changed ## Compatibility alias for the changed-path planner.

test-all-ci: ## Explicitly run every semantic lane locally (exceptional).
	$(MAKE) test-unit
	$(MAKE) test-component
	$(MAKE) test-domain
	$(MAKE) test-composition
	$(MAKE) test-storage
	$(MAKE) test-process
	$(MAKE) test-mcp
	$(MAKE) test-provider
	$(MAKE) test-lean
	$(MAKE) test-e2e

test-stress: ## Repeat explicitly marked property tests on the scheduled lane.
	$(UV_RUN) pytest -n 0 --timeout=120 --timeout-method=thread -m property --count=$(STRESS_COUNT) \
		$(if $(TESTS),$(TESTS),tests) $(PYTEST_DIAGNOSTIC_ARGS) $(PYTEST_ARGS)

test-ordering: ## Reproduce scheduled ordering (default seed 17; override with PYTEST_ARGS).
	@test -n "$(ORDERING_LANE)" || { echo "ORDERING_LANE is required" >&2; exit 2; }
	$(MAKE) test-$(ORDERING_LANE) \
		PYTEST_ARGS="$(if $(findstring --randomly-seed,$(PYTEST_ARGS)),,$(ORDERING_DEFAULT_SEED)) $(PYTEST_ARGS)"

duplicate-code: ## Run the CI duplicate-code detector locally.
	npx --yes jscpd@5.0.12 --config .jscpd.json .

npm-test: ## Run the npm package tests and dry-run pack.
	npm test --prefix npm
	npm pack --dry-run ./npm

todo-check: ## Fail on TODO comments that do not reference an issue.
	@violations="$$(rg -n 'TODO' --type py src/ tests/ | rg -v 'TODO\(#\d+\)' || true)"; \
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

check: lint typecheck test-unit ## Run the fast routine local handoff checks.

precommit: ## Fix and run every routine local handoff check.
	$(MAKE) fix
	$(MAKE) check

check-static: lint-full typecheck test-architecture architecture todo-check build ## Run CI-owned static checks plus a local package build.

harbor-plan: ## Print the independent Harbor benchmark plan (BASE=... optional).
	@set -eu; \
	tmp_dir=$$(mktemp -d); \
	trap 'rm -rf "$$tmp_dir"; if [ -n "$(PATHS_FILE)" ]; then rm -f "$(PATHS_FILE)"; fi' EXIT; \
	base_sha=""; \
	base_arg=""; \
	if [ -n "$(BASE)" ]; then \
		base_sha=$$(git rev-parse "$(BASE)"); \
		base_arg="--base $$base_sha"; \
	fi; \
	head_sha=$$(git rev-parse HEAD); \
	if [ -n "$(PATHS)" ]; then \
		$(UV_RUN) python .github/scripts/normalize-ci-paths --file "$(PATHS_FILE)" > "$$tmp_dir/changed-paths.txt"; \
	else \
		{ \
			if [ -n "$(BASE)" ]; then git diff --name-only "$(BASE)" HEAD; fi; \
			git diff --name-only HEAD; \
			git ls-files --others --exclude-standard; \
		} | sort -u > "$$tmp_dir/changed-paths.txt"; \
	fi; \
	if [ -n "$(PATHS)" ]; then \
		$(HARBOR_PYTHON) .github/scripts/plan-benchmarks \
			$$base_arg --head "$$head_sha" --paths-file "$(PATHS_FILE)" > "$$tmp_dir/plan.txt"; \
	else \
		changed_paths=$$(tr '\n' ' ' < "$$tmp_dir/changed-paths.txt"); \
		$(HARBOR_PYTHON) .github/scripts/plan-benchmarks \
			$$base_arg --head "$$head_sha" -- $$changed_paths > "$$tmp_dir/plan.txt"; \
	fi; \
	$(UV_RUN) python .github/scripts/validate-benchmark-plan < "$$tmp_dir/plan.txt"; \
	$(UV_RUN) python .github/scripts/emit-plan-receipt \
		--kind benchmark --event pull_request \
		--base "$$base_sha" --head "$$head_sha" \
		--planner .github/scripts/plan-benchmarks \
		--config .github/scripts/_ci_paths.py \
		--config .github/scripts/validate-benchmark-plan \
		--config benchmarks/registry.toml \
		--config benchmarks/environment-profiles.toml \
		--config .github/workflows/benchmarks.yml \
		--config Makefile \
		--config tools/check_benchmark_adapters.py \
		--config tools/check_benchmark_contracts.py \
		--config tools/check_harbor_dataset.py \
		--config tools/sync_harbor_verifier_support.py \
		--plan-file "$$tmp_dir/plan.txt" \
		--paths-file "$$tmp_dir/changed-paths.txt" \
		--output "$$tmp_dir/receipt.json" >/dev/null; \
	echo "Benchmark plan:"; \
	cat "$$tmp_dir/plan.txt"; \
	echo "Plan receipt:"; \
	cat "$$tmp_dir/receipt.json"

harbor-sync: ## Update verifier checksum labels for selected tasks (DATASET=... TASKS="...").
	@test -n "$(DATASET)" || { echo "DATASET is required" >&2; exit 2; }
	@test -n "$(TASKS)" || { echo "TASKS is required; refusing an unscoped checksum update" >&2; exit 2; }
	$(HARBOR_PYTHON) -m benchmarks.tooling.public_contract sync-dataset \
		--dataset-root "benchmarks/datasets/$(DATASET)" --tasks $(TASKS)
	$(HARBOR_PYTHON) tools/sync_harbor_verifier_support.py \
		--dataset "$(DATASET)" --tasks $(TASKS)

harbor-contracts: ## Check Harbor sync, task topology, schemas, and generated records.
	$(HARBOR_PYTHON) tools/check_harbor_dataset.py --check
	$(HARBOR_PYTHON) tools/check_benchmark_contracts.py

harbor-adapter-checks: ## Check every repository-owned Harbor adapter.
	@set -eu; for adapter_dir in benchmarks/adapters/*; do \
		test -d "$$adapter_dir" || continue; \
		$(MAKE) --no-print-directory harbor-adapter-check \
			ADAPTER="$${adapter_dir##*/}"; \
	done

harbor-validation-tests: ## Run Harbor's host-side validation test suite.
	$(UV_RUN) pytest -n $(HARBOR_VALIDATION_WORKERS) \
		$(PYTEST_DIAGNOSTIC_ARGS) benchmarks/validation $(PYTEST_ARGS)

harbor-validate: harbor-contracts harbor-adapter-checks harbor-validation-tests ## Run all repository-owned Harbor checks under the pinned Harbor runtime.

harbor-check: harbor-validate ## Run Harbor topology, digest, provenance, and host-side validation checks.

harbor-check-task: ## Validate selected Harbor leaf tasks (DATASET=..., TASKS="task-a task-b").
	@test -n "$(DATASET)" || { echo "DATASET is required" >&2; exit 2; }
	@test -n "$(TASKS)" || { echo "TASKS is required; refusing an implicit full-dataset check" >&2; exit 2; }
	$(HARBOR_PYTHON) tools/check_harbor_dataset.py \
		--dataset "$(DATASET)" --tasks $(TASKS)

benchmark-inventory: ## Render the content-bound benchmark inventory (OUTPUT=path optional).
	$(HARBOR_PYTHON) -m benchmarks.tooling.benchmark_inventory $(if $(OUTPUT),--output "$(OUTPUT)",)

benchmark-snapshot: ## Create an immutable snapshot lock (DATASET=..., OUTPUT=..., SOURCE_TREE=... optional).
	@test -n "$(DATASET)" || { echo "DATASET is required" >&2; exit 2; }
	$(HARBOR_PYTHON) tools/manage_benchmark_snapshots.py create \
		--dataset "$(DATASET)" $(if $(OUTPUT),--output "$(OUTPUT)",) \
		$(if $(SOURCE_TREE),--source-tree "$(SOURCE_TREE)",)

benchmark-snapshot-validate: ## Validate a committed snapshot lock (LOCK=..., REPRODUCE=1 optional).
	@test -n "$(LOCK)" || { echo "LOCK is required" >&2; exit 2; }
	$(HARBOR_PYTHON) tools/manage_benchmark_snapshots.py validate --lock "$(LOCK)" \
		$(if $(filter 1,$(REPRODUCE)),--reproduce,) \
		$(if $(SOURCE_TREE),--source-tree "$(SOURCE_TREE)",)

benchmark-publish: ## Generate an ignored Harbor dataset.toml from a snapshot (LOCK=..., DEST=... optional).
	@test -n "$(LOCK)" || { echo "LOCK is required" >&2; exit 2; }
	$(HARBOR_PYTHON) tools/manage_benchmark_snapshots.py publish --lock "$(LOCK)" \
		$(if $(DEST),--dest "$(DEST)",)

harbor-oracle: ## Check contracts, then run an explicitly scoped dataset Oracle.
	@test -n "$(DATASET)" || { echo "DATASET is required" >&2; exit 2; }
	@test -n "$(TASKS)" -o "$(FULL)" = "1" || { echo "TASKS is required; use FULL=1 only for an intentional full-dataset Oracle" >&2; exit 2; }
	$(MAKE) harbor-check
	$(MAKE) harbor-oracle-run DATASET="$(DATASET)" TASKS="$(TASKS)" FULL="$(FULL)" EVAL_ARGS="$(EVAL_ARGS)"

harbor-oracle-task: harbor-check-task ## Check selected leaf tasks, then run their exact Oracle.
	@test -f "benchmarks/datasets/$(DATASET)/jobs/oracle.json" || { echo "unknown dataset or missing Oracle job: $(DATASET)" >&2; exit 2; }
	job_name="$$( $(HARBOR_PYTHON) benchmarks/tooling/validate_harbor_results.py \
		--prepare --dataset "$(DATASET)" \
		--jobs-dir "benchmarks/results/$(DATASET)-oracle" \
		--tasks $(TASKS) )" && \
	$(HARBOR_RUNNER) run \
		-c "benchmarks/datasets/$(DATASET)/jobs/oracle.json" \
		-p "benchmarks/datasets/$(DATASET)" \
		$(foreach task,$(TASKS),--include-task-name "$(task)") \
		$(EVAL_ARGS) \
		--job-name "$$job_name" && \
	$(HARBOR_PYTHON) benchmarks/tooling/validate_harbor_results.py \
		--dataset "$(DATASET)" \
		--jobs-dir "benchmarks/results/$(DATASET)-oracle" \
		--result "benchmarks/results/$(DATASET)-oracle/$$job_name/result.json" \
		--tasks $(TASKS)

harbor-oracle-run: ## Run a dataset Oracle after an already-successful contract gate.
	@test -n "$(DATASET)" || { echo "DATASET is required" >&2; exit 2; }
	@test -n "$(TASKS)" -o "$(FULL)" = "1" || { echo "TASKS is required; use FULL=1 only for an intentional full-dataset Oracle" >&2; exit 2; }
	@test -f "benchmarks/datasets/$(DATASET)/jobs/oracle.json" || { echo "unknown dataset or missing Oracle job: $(DATASET)" >&2; exit 2; }
	job_name="$$( $(HARBOR_PYTHON) benchmarks/tooling/validate_harbor_results.py \
		--prepare --dataset "$(DATASET)" \
		--jobs-dir "benchmarks/results/$(DATASET)-oracle" \
		$(if $(TASKS),--tasks $(TASKS),) )" && \
	$(HARBOR_RUNNER) run \
		-c "benchmarks/datasets/$(DATASET)/jobs/oracle.json" \
		-p "benchmarks/datasets/$(DATASET)" \
		$(foreach task,$(TASKS),--include-task-name "$(task)") \
		$(EVAL_ARGS) \
		--job-name "$$job_name" && \
	$(HARBOR_PYTHON) benchmarks/tooling/validate_harbor_results.py \
		--dataset "$(DATASET)" \
		--jobs-dir "benchmarks/results/$(DATASET)-oracle" \
		--result "benchmarks/results/$(DATASET)-oracle/$$job_name/result.json" \
		$(if $(TASKS),--tasks $(TASKS),)

harbor-oracle-all: harbor-check ## Run every registered dataset Oracle with tasks.
	@set -e; for dataset in agent-workflow-v1 symbolic-coordination-v1 public-reproductions-v1 research-diagnostics-v1 provider-feasibility-v1; do \
		$(MAKE) --no-print-directory harbor-oracle-run DATASET=$$dataset FULL=1 EVAL_ARGS="$(EVAL_ARGS)"; \
	done

harbor-adapter-check: ## Check deterministic regeneration for ADAPTER=<id>.
	@test -n "$(ADAPTER)" || { echo "ADAPTER is required" >&2; exit 2; }
	$(HARBOR_PYTHON) tools/check_benchmark_adapters.py --adapter "$(ADAPTER)"
	@test -x "benchmarks/adapters/$(ADAPTER)/check.sh" || { echo "adapter check.sh is missing: $(ADAPTER)" >&2; exit 2; }
	HARBOR_PYTHON="$(HARBOR_PYTHON)" "benchmarks/adapters/$(ADAPTER)/check.sh"

heldout-validate: ## Validate a private held-out manifest (MANIFEST=path).
	@test -n "$(MANIFEST)" || { echo "MANIFEST is required" >&2; exit 2; }
	$(UV_RUN) python -m benchmarks.tooling.heldout_bundle validate --manifest "$(MANIFEST)"

heldout-render: ## Verify a private bundle and render matched jobs (MANIFEST=..., BUNDLE_ROOT=..., OUTPUT=..., STAGE=...).
	@test -n "$(MANIFEST)" -a -n "$(BUNDLE_ROOT)" -a -n "$(OUTPUT)" -a -n "$(STAGE)" -a -n "$(MAX_TOKENS)" -a -n "$(MAX_COST_USD)" || { echo "MANIFEST, BUNDLE_ROOT, OUTPUT, STAGE, MAX_TOKENS, and MAX_COST_USD are required" >&2; exit 2; }
	$(HARBOR_PYTHON) -m benchmarks.tooling.heldout_bundle render \
		--manifest "$(MANIFEST)" --bundle-root "$(BUNDLE_ROOT)" --output "$(OUTPUT)" \
		--stage "$(STAGE)" --max-tokens "$(MAX_TOKENS)" --max-cost-usd "$(MAX_COST_USD)"

heldout-smoke: ## Render a synthetic private bundle and run Harbor nop/Oracle without model cost.
	$(HARBOR_PYTHON) -m benchmarks.tooling.heldout_smoke --run-harbor

JACOBIAN_ENABLED ?= 1
ifneq ($(filter 0 1,$(JACOBIAN_ENABLED)),$(JACOBIAN_ENABLED))
$(error JACOBIAN_ENABLED must be exactly 0 or 1 (got '$(JACOBIAN_ENABLED)'))
endif

CODEX_WEB_SEARCH ?= disabled
JACOBIAN_EVAL_PROXY ?= 0
define _jacobian_eval_container_proxy
$(subst localhost,host.docker.internal,$(subst 127.0.0.1,host.docker.internal,$1))
endef
JACOBIAN_EVAL_HTTP_PROXY ?= $(call _jacobian_eval_container_proxy,$(HTTP_PROXY))
JACOBIAN_EVAL_HTTPS_PROXY ?= $(call _jacobian_eval_container_proxy,$(HTTPS_PROXY))
JACOBIAN_EVAL_ALL_PROXY ?= $(call _jacobian_eval_container_proxy,$(ALL_PROXY))
JACOBIAN_EVAL_NO_PROXY ?= localhost,127.0.0.1,jacobian
ifneq ($(filter 0 1,$(JACOBIAN_EVAL_PROXY)),$(JACOBIAN_EVAL_PROXY))
$(error JACOBIAN_EVAL_PROXY must be exactly 0 or 1 (got '$(JACOBIAN_EVAL_PROXY)'))
endif

ifeq ($(JACOBIAN_EVAL_PROXY),1)
ifneq ($(strip $(JACOBIAN_EVAL_HTTP_PROXY)$(JACOBIAN_EVAL_HTTPS_PROXY)$(JACOBIAN_EVAL_ALL_PROXY)),)
else
$(error JACOBIAN_EVAL_PROXY=1 requires JACOBIAN_EVAL_HTTP_PROXY, JACOBIAN_EVAL_HTTPS_PROXY, or JACOBIAN_EVAL_ALL_PROXY)
endif
endif

ifeq ($(JACOBIAN_ENABLED),0)
ifeq ($(JACOBIAN_EVAL_PROXY),1)
EVAL_CONFIG ?= benchmarks/config/agent-workflow-v1-control-proxy.json
else
EVAL_CONFIG ?= benchmarks/config/agent-workflow-v1-control.json
endif
override MCP_CONFIG :=
else
ifeq ($(JACOBIAN_EVAL_PROXY),1)
EVAL_CONFIG ?= benchmarks/datasets/$(or $(DATASET),agent-workflow-v1)/jobs/jacobian-observation-proxy.json
else
EVAL_CONFIG ?= benchmarks/datasets/$(or $(DATASET),agent-workflow-v1)/jobs/jacobian-observation.json
endif
MCP_CONFIG ?= benchmarks/config/jacobian.mcp.json
endif

agent-eval: ## Run a Harbor evaluation (JACOBIAN_ENABLED=0|1, JACOBIAN_EVAL_PROXY=0|1, DATASET=agent-workflow-v1, EVAL_EXECUTE=1).
	@if [ "$(EVAL_EXECUTE)" != "1" ]; then \
		echo "Model execution is opt-in. Review the job, then run: make agent-eval DATASET=agent-workflow-v1 EVAL_EXECUTE=1"; \
		exit 0; \
	fi; \
	if [ -z "$${JACOBIAN_MODEL:-}" ]; then \
		echo "JACOBIAN_MODEL must be exported" >&2; \
		exit 2; \
	fi; \
	if [ "$(JACOBIAN_ENABLED)" = "1" ]; then \
		test -n "$${JACOBIAN_IMAGE:-}" || { echo "JACOBIAN_IMAGE must be exported" >&2; exit 2; }; \
		test -n "$(RUNTIME_SNAPSHOT)" || { echo "RUNTIME_SNAPSHOT is required for a Jacobian-enabled run" >&2; exit 2; }; \
		$(UV_RUN) python tools/manage_jacobian_image.py bind-runtime \
			--image "$${JACOBIAN_IMAGE}" --runtime-snapshot "$(RUNTIME_SNAPSHOT)"; \
	fi; \
	JACOBIAN_EVAL_HTTP_PROXY="$(JACOBIAN_EVAL_HTTP_PROXY)" \
	JACOBIAN_EVAL_HTTPS_PROXY="$(JACOBIAN_EVAL_HTTPS_PROXY)" \
	JACOBIAN_EVAL_ALL_PROXY="$(JACOBIAN_EVAL_ALL_PROXY)" \
	JACOBIAN_EVAL_NO_PROXY="$(JACOBIAN_EVAL_NO_PROXY)" \
	$(HARBOR_RUNNER) run \
		-c "$(EVAL_CONFIG)" \
		-a codex \
		-m "$${JACOBIAN_MODEL}" \
		--ak "web_search=$(CODEX_WEB_SEARCH)" \
		$(if $(MCP_CONFIG),--mcp-config "$(MCP_CONFIG)",) \
		$(if $(TASKS),-p "benchmarks/datasets/$(or $(DATASET),agent-workflow-v1)" $(foreach task,$(TASKS),--include-task-name "$(task)"),) \
		$(EVAL_ARGS)

agent-eval-validate: ## Normalize one observation (RESULTS=..., JOB=..., CONDITION=..., OUTPUT=...).
	@test -n "$(RESULTS)" -a -n "$(JOB)" -a -n "$(CONDITION)" -a -n "$(OUTPUT)" || { echo "RESULTS, JOB, CONDITION, and OUTPUT are required" >&2; exit 2; }
	$(UV_RUN) python -m benchmarks.tooling.observation_results validate \
		--dataset "$(or $(DATASET),agent-workflow-v1)" --condition "$(CONDITION)" \
		--job "$(JOB)" --jobs-dir "$(RESULTS)" --output "$(OUTPUT)" \
		$(if $(RESULT),--result "$(RESULT)",) \
		$(if $(RUNTIME_SNAPSHOT),--runtime-snapshot "$(RUNTIME_SNAPSHOT)",) \
		$(if $(HELDOUT_MANIFEST),--heldout-manifest "$(HELDOUT_MANIFEST)",)

agent-eval-compare: ## Compare normalized observations (CONTROL=..., TREATMENT=..., OUTPUT=...).
	@test -n "$(CONTROL)" -a -n "$(TREATMENT)" -a -n "$(OUTPUT)" || { echo "CONTROL, TREATMENT, and OUTPUT are required" >&2; exit 2; }
	$(UV_RUN) python -m benchmarks.tooling.observation_results compare \
		--control "$(CONTROL)" --treatment "$(TREATMENT)" --output "$(OUTPUT)"

SC_CODEX_TASK ?= symbolic-coordination-near-miss-01
SC_CODEX_CONDITIONS ?= A B C

symbolic-coordination-codex-preflight: ## Check host Codex auth/model/isolation for the symbolic pilot (SC_CODEX_TASK=...).
	$(UV_RUN) python -m benchmarks.tooling.symbolic_coordination_codex preflight \
		--task "$(SC_CODEX_TASK)"

symbolic-coordination-codex-dry-run: ## Freeze a host-local symbolic A/B/C plan without model execution (SC_CODEX_OUTPUT=/outside/repo).
	@test -n "$(SC_CODEX_OUTPUT)" || { echo "SC_CODEX_OUTPUT outside the repository is required" >&2; exit 2; }
	$(UV_RUN) python -m benchmarks.tooling.symbolic_coordination_codex run \
		--task "$(SC_CODEX_TASK)" --output "$(SC_CODEX_OUTPUT)" \
		--conditions $(SC_CODEX_CONDITIONS) --dry-run

symbolic-coordination-codex-eval: ## Run host-local symbolic Codex observations (EVAL_EXECUTE=1, SC_CODEX_OUTPUT=/outside/repo).
	@if [ "$(EVAL_EXECUTE)" != "1" ]; then \
		echo "Model execution is opt-in. Set EVAL_EXECUTE=1 after reviewing the dry run."; \
		exit 0; \
	fi; \
	test -n "$(SC_CODEX_OUTPUT)" || { echo "SC_CODEX_OUTPUT outside the repository is required" >&2; exit 2; }; \
	$(UV_RUN) python -m benchmarks.tooling.symbolic_coordination_codex run \
		--task "$(SC_CODEX_TASK)" --output "$(SC_CODEX_OUTPUT)" \
		--conditions $(SC_CODEX_CONDITIONS)

symbolic-coordination-trajectory-telemetry: ## Verify raw symbolic runs and emit typed trajectory JSON/Markdown (SC_TRAJECTORY_RUNS="...").
	@test -n "$(SC_TRAJECTORY_RUNS)" -a -n "$(SC_TRAJECTORY_OUTPUT)" || { echo "SC_TRAJECTORY_RUNS and SC_TRAJECTORY_OUTPUT are required" >&2; exit 2; }
	$(UV_RUN) python -m benchmarks.tooling.symbolic_coordination_trajectory emit \
		--output "$(SC_TRAJECTORY_OUTPUT)" \
		$(if $(SC_TRAJECTORY_MARKDOWN),--markdown-output "$(SC_TRAJECTORY_MARKDOWN)",) \
		$(SC_TRAJECTORY_RUNS)

SC_COMPARISON_TASKS ?= symbolic-coordination-near-miss-01 symbolic-coordination-grid-exhausted-01
SC_COMPARISON_REPETITIONS ?= 2

symbolic-coordination-comparison-plan: ## Freeze a repeated symbolic A/B/C experiment (SC_COMPARISON_ROOT=/outside/repo, SC_COMPARISON_STACK_REVISIONS="name=sha ...").
	@test -n "$(SC_COMPARISON_ROOT)" -a -n "$(SC_COMPARISON_STACK_REVISIONS)" || { echo "SC_COMPARISON_ROOT and SC_COMPARISON_STACK_REVISIONS are required" >&2; exit 2; }
	$(UV_RUN) python -m benchmarks.tooling.symbolic_coordination_comparison plan \
		--output "$(SC_COMPARISON_ROOT)" --tasks $(SC_COMPARISON_TASKS) \
		--repetitions "$(SC_COMPARISON_REPETITIONS)" \
		$(foreach revision,$(SC_COMPARISON_STACK_REVISIONS),--stack-revision "$(revision)")

symbolic-coordination-comparison-run: ## Resume a frozen repeated experiment (EVAL_EXECUTE=1, SC_COMPARISON_ROOT=...).
	@if [ "$(EVAL_EXECUTE)" != "1" ]; then \
		echo "Model execution is opt-in. Set EVAL_EXECUTE=1 after reviewing the manifest."; \
		exit 0; \
	fi; \
	test -n "$(SC_COMPARISON_ROOT)" || { echo "SC_COMPARISON_ROOT is required" >&2; exit 2; }; \
	$(UV_RUN) python -m benchmarks.tooling.symbolic_coordination_comparison run \
		--root "$(SC_COMPARISON_ROOT)" \
		$(if $(SC_COMPARISON_MAX_EXECUTIONS),--max-model-executions "$(SC_COMPARISON_MAX_EXECUTIONS)",) \
		$(if $(filter 1,$(SC_COMPARISON_RETRY_INFRA)),--retry-infrastructure,)

symbolic-coordination-comparison-report: ## Verify repeated artifacts and emit paired JSON/Markdown (SC_COMPARISON_ROOT=..., SC_COMPARISON_OUTPUT=...).
	@test -n "$(SC_COMPARISON_ROOT)" -a -n "$(SC_COMPARISON_OUTPUT)" || { echo "SC_COMPARISON_ROOT and SC_COMPARISON_OUTPUT are required" >&2; exit 2; }
	$(UV_RUN) python -m benchmarks.tooling.symbolic_coordination_comparison report \
		--root "$(SC_COMPARISON_ROOT)" --output "$(SC_COMPARISON_OUTPUT)" \
		$(if $(SC_COMPARISON_MARKDOWN),--markdown-output "$(SC_COMPARISON_MARKDOWN)",)

SC_CLOSEOUT_TASKS ?= symbolic-coordination-valid-inverse-01 symbolic-coordination-near-miss-01 symbolic-coordination-one-direction-01 symbolic-coordination-keller-only-01 symbolic-coordination-grid-exhausted-01 symbolic-coordination-semantic-equivalence-01

symbolic-coordination-closeout-plan: ## Freeze the six-family A/B/C/D closeout (SC_CLOSEOUT_ROOT=/outside/repo, SC_CLOSEOUT_STACK_REVISIONS="name=sha ...").
	@test -n "$(SC_CLOSEOUT_ROOT)" -a -n "$(SC_CLOSEOUT_STACK_REVISIONS)" || { echo "SC_CLOSEOUT_ROOT and SC_CLOSEOUT_STACK_REVISIONS are required" >&2; exit 2; }
	$(UV_RUN) python -m benchmarks.tooling.symbolic_coordination_closeout plan \
		--root "$(SC_CLOSEOUT_ROOT)" --tasks $(SC_CLOSEOUT_TASKS) \
		--stack-revisions "$(SC_CLOSEOUT_STACK_REVISIONS)"

symbolic-coordination-closeout-run: ## Resume the frozen closeout, capped at 24 conditions (EVAL_EXECUTE=1, SC_CLOSEOUT_ROOT=...).
	@if [ "$(EVAL_EXECUTE)" != "1" ]; then \
		echo "Model execution is opt-in. Set EVAL_EXECUTE=1 after reviewing the manifest."; \
		exit 0; \
	fi; \
	test -n "$(SC_CLOSEOUT_ROOT)" || { echo "SC_CLOSEOUT_ROOT is required" >&2; exit 2; }; \
	$(UV_RUN) python -m benchmarks.tooling.symbolic_coordination_closeout run \
		--execute --root "$(SC_CLOSEOUT_ROOT)" \
		$(if $(SC_CLOSEOUT_MAX_EXECUTIONS),--max-model-executions "$(SC_CLOSEOUT_MAX_EXECUTIONS)",) \
		$(if $(filter 1,$(SC_CLOSEOUT_RETRY_INFRA)),--retry-infrastructure,)

symbolic-coordination-closeout-report: ## Verify closeout artifacts and emit typed JSON/Markdown (SC_CLOSEOUT_ROOT=..., SC_CLOSEOUT_OUTPUT=...).
	@test -n "$(SC_CLOSEOUT_ROOT)" -a -n "$(SC_CLOSEOUT_OUTPUT)" || { echo "SC_CLOSEOUT_ROOT and SC_CLOSEOUT_OUTPUT are required" >&2; exit 2; }
	$(UV_RUN) python -m benchmarks.tooling.symbolic_coordination_closeout report \
		--root "$(SC_CLOSEOUT_ROOT)" --output "$(SC_CLOSEOUT_OUTPUT)"

provider-eval: ## Run pinned provider feasibility jobs (PROVIDER=cddlib|cgal|gudhi|lean-repl|nauty|regina).
	@test -n "$(PROVIDER)" || { echo "PROVIDER is required" >&2; exit 2; }
	@case "$(PROVIDER)" in cddlib|cgal|gudhi|lean-repl|nauty|regina) ;; *) echo "unknown provider: $(PROVIDER)" >&2; exit 2;; esac
	@$(MAKE) harbor-check && \
	$(HARBOR_RUNNER) run \
		-c benchmarks/datasets/provider-feasibility-v1/jobs/oracle.json \
		-p benchmarks/datasets/provider-feasibility-v1 \
		--include-task-name "$(PROVIDER)" \
		$(EVAL_ARGS)

clean: ## Remove local caches, build outputs, and coverage artifacts.
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build htmlcov
	rm -f .coverage .coverage.*
	find src tests benchmarks -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -maxdepth 2 -type d -name '*.egg-info' -prune -exec rm -rf {} +

docs-command-check: ## Validate Make targets and TESTS paths in command examples.
	$(UV_RUN) python tools/check_doc_commands.py

docs-linkcheck: docs-command-check ## Check relative Markdown links in project docs.
	npx --yes markdown-link-check@3.15.0 \
		--config .markdown-link-check.json -q \
		README.md README.zh-CN.md AGENTS.md CONTRIBUTING.md docs
