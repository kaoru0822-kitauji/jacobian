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
    result = planner.plan(["src/jacobian/math.py"])

    assert result["run-benchmark-check"] == "false"
    assert result["run-benchmark-oracle"] == "false"
    assert result["benchmark-oracle-scope"] == "none"
    assert _matrix(result) == []


def test_task_readme_change_runs_contract_checks_without_oracle() -> None:
    result = planner.plan(
        ["benchmarks/tasks/parameterized-sharp-bound-audit/README.md"]
    )

    assert result["run-benchmark-check"] == "true"
    assert result["run-benchmark-oracle"] == "false"
    assert result["benchmark-oracle-scope"] == "none"
    assert _matrix(result) == []


def test_executable_task_change_selects_exact_task_and_all_memberships() -> None:
    result = planner.plan(
        ["benchmarks/tasks/parameterized-sharp-bound-audit/tests/verifier.py"]
    )

    assert result["run-benchmark-oracle"] == "true"
    assert result["benchmark-oracle-scope"] == "changed-tasks"
    matrix = _matrix(result)
    assert len(matrix) == 1
    assert matrix[0]["dataset"] == "agent-workflow-v1"
    assert matrix[0]["task"] == "parameterized-sharp-bound-audit"
    assert len(matrix[0]["digest"]) == 71
    assert matrix[0]["digest"].startswith("sha256:")


def test_membership_change_runs_the_affected_dataset() -> None:
    result = planner.plan(
        ["benchmarks/datasets/agent-workflow-v1/members/new-task.toml"]
    )

    assert result["run-benchmark-oracle"] == "true"
    assert result["benchmark-oracle-scope"] == "affected-datasets"
    assert {item["dataset"] for item in _matrix(result)} == {"agent-workflow-v1"}
    assert _matrix(result)
    assert all(item["dataset"] == "agent-workflow-v1" for item in _matrix(result))


def test_unknown_benchmark_path_fails_closed_to_full_portfolio() -> None:
    result = planner.plan(["benchmarks/new-control-plane.py"])

    assert result["run-benchmark-oracle"] == "true"
    assert result["benchmark-oracle-scope"] == "all"
    assert _matrix(result)
    assert len({item["dataset"] for item in _matrix(result)}) > 1


def test_force_full_includes_each_dataset_task_pair() -> None:
    result = planner.plan([], force_full=True)

    assert result["benchmark-oracle-scope"] == "all"
    assert result["run-benchmark-check"] == "true"
    assert result["run-benchmark-oracle"] == "true"
    assert _matrix(result)


def test_canonical_task_ids_have_no_dataset_local_bundle_copies() -> None:
    local_bundles = list(
        (ROOT / "benchmarks" / "datasets").glob("*/tasks/**/task.toml")
    )

    assert local_bundles == []
