"""Contract tests for the independent Harbor benchmark planner."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLANNER_PATH = ROOT / ".github" / "scripts" / "plan-benchmarks"
_SPEC = importlib.util.spec_from_loader(
    "benchmark_planner", SourceFileLoader("benchmark_planner", str(PLANNER_PATH))
)
assert _SPEC is not None and _SPEC.loader is not None
planner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(planner)


@pytest.fixture(autouse=True)
def stable_digests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep planner tests independent of Harbor's optional runtime package."""

    monkeypatch.setattr(
        planner,
        "_digest",
        lambda path: f"sha256:{hashlib.sha256(path.name.encode()).hexdigest()}",
    )


def _matrix(result: dict[str, str]) -> list[dict[str, str]]:
    return json.loads(result["benchmark-oracle-matrix"])


def test_product_only_changes_skip_benchmark_work() -> None:
    result = planner.plan(["src/jacobian/math.py"], event="pull_request")

    assert result["run-benchmark-check"] == "false"
    assert result["run-benchmark-oracle"] == "false"
    assert result["benchmark-oracle-scope"] == "none"
    assert _matrix(result) == []


def test_task_readme_change_runs_contract_checks_without_oracle() -> None:
    result = planner.plan(
        ["benchmarks/tasks/parameterized-sharp-bound-audit/README.md"],
        event="pull_request",
    )

    assert result["run-benchmark-check"] == "true"
    assert result["run-benchmark-oracle"] == "false"
    assert result["benchmark-oracle-scope"] == "none"
    assert _matrix(result) == []


def test_executable_task_change_selects_exact_task_and_all_memberships() -> None:
    result = planner.plan(
        ["benchmarks/tasks/parameterized-sharp-bound-audit/tests/verifier.py"],
        event="pull_request",
    )

    assert result["run-benchmark-oracle"] == "true"
    assert result["benchmark-oracle-scope"] == "changed-tasks"
    matrix = _matrix(result)
    assert len(matrix) == 1
    assert matrix[0]["dataset"] == "agent-workflow-v1"
    assert matrix[0]["task"] == "parameterized-sharp-bound-audit"
    assert len(matrix[0]["digest"]) == 71
    assert matrix[0]["digest"].startswith("sha256:")


def test_membership_change_defers_dataset_oracle_until_merge_queue() -> None:
    result = planner.plan(
        ["benchmarks/datasets/agent-workflow-v1/members/new-task.toml"],
        event="pull_request",
    )

    assert result["run-benchmark-check"] == "true"
    assert result["run-benchmark-oracle"] == "false"
    assert result["benchmark-oracle-scope"] == "none"
    assert _matrix(result) == []


def test_membership_change_runs_affected_dataset_in_merge_queue() -> None:
    result = planner.plan(
        ["benchmarks/datasets/agent-workflow-v1/members/new-task.toml"],
        event="merge_group",
    )

    assert result["run-benchmark-oracle"] == "true"
    assert result["benchmark-oracle-scope"] == "affected-datasets"
    assert _matrix(result)
    assert {item["dataset"] for item in _matrix(result)} == {"agent-workflow-v1"}


def test_shared_tooling_change_is_contract_only_on_pull_request() -> None:
    result = planner.plan(
        ["benchmarks/tooling/verifier_support.py"], event="pull_request"
    )

    assert result["run-benchmark-check"] == "true"
    assert result["run-benchmark-oracle"] == "false"
    assert result["benchmark-oracle-scope"] == "none"
    assert _matrix(result) == []


def test_shared_tooling_change_runs_full_portfolio_in_merge_queue() -> None:
    result = planner.plan(
        ["benchmarks/tooling/verifier_support.py"], event="merge_group"
    )

    assert result["run-benchmark-oracle"] == "true"
    assert result["benchmark-oracle-scope"] == "all"
    assert len(_matrix(result)) > 1


def test_large_task_set_is_deferred_from_pull_request_to_merge_queue() -> None:
    task_ids = sorted(planner._membership()[0])[:9]
    paths = [f"benchmarks/tasks/{task_id}/tests/verifier.py" for task_id in task_ids]

    pull_request = planner.plan(paths, event="pull_request")
    merge_group = planner.plan(paths, event="merge_group")

    assert pull_request["run-benchmark-oracle"] == "false"
    assert pull_request["benchmark-oracle-scope"] == "none"
    assert _matrix(pull_request) == []
    assert merge_group["run-benchmark-oracle"] == "true"
    assert len(_matrix(merge_group)) == 9


def test_main_push_does_not_repeat_merge_queue_oracles() -> None:
    result = planner.plan(["benchmarks/tooling/verifier_support.py"], event="push")

    assert result["run-benchmark-check"] == "true"
    assert result["run-benchmark-oracle"] == "false"
    assert result["benchmark-oracle-scope"] == "none"
    assert _matrix(result) == []


def test_adapter_documentation_change_never_runs_oracle() -> None:
    result = planner.plan(["benchmarks/adapters/README.md"], event="merge_group")

    assert result["run-benchmark-check"] == "true"
    assert result["run-benchmark-oracle"] == "false"
    assert result["benchmark-oracle-scope"] == "none"


def test_unknown_benchmark_path_fails_closed_to_full_portfolio() -> None:
    result = planner.plan(["benchmarks/new-control-plane.py"], event="pull_request")

    assert result["run-benchmark-oracle"] == "true"
    assert result["benchmark-oracle-scope"] == "all"
    assert _matrix(result)
    assert len({item["dataset"] for item in _matrix(result)}) > 1


def test_force_full_includes_each_dataset_task_pair() -> None:
    result = planner.plan([], event="workflow_dispatch", force_full=True)

    assert result["benchmark-oracle-scope"] == "all"
    assert result["run-benchmark-check"] == "true"
    assert result["run-benchmark-oracle"] == "true"
    assert _matrix(result)


def test_canonical_task_ids_have_no_dataset_local_bundle_copies() -> None:
    local_bundles = list(
        (ROOT / "benchmarks" / "datasets").glob("*/tasks/**/task.toml")
    )

    assert local_bundles == []
