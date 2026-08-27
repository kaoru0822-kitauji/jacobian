"""Focused Harbor leaf-selection contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from benchmarks.tooling.harbor_suite import (
    HarborSuiteError,
    Suite,
    TaskRef,
    check_selected_tasks,
    get_suite,
    select_task_refs,
)


def test_selected_task_gate_accepts_multiple_explicit_leaf_tasks() -> None:
    suite = get_suite("mathematical-benchmarks-v1")

    selected = select_task_refs(
        suite,
        ("graph-counterexample", "finite-magma-countermodel"),
    )

    assert tuple(ref.path.name for ref in selected) == (
        "graph-counterexample",
        "finite-magma-countermodel",
    )


@pytest.mark.parametrize(
    ("dataset", "tasks"),
    [
        ("missing-dataset", ("graph-counterexample",)),
        ("mathematical-benchmarks-v1", ("missing-task",)),
        ("mathematical-benchmarks-v1", ()),
    ],
)
def test_selected_task_gate_rejects_missing_or_empty_selection(
    dataset: str,
    tasks: tuple[str, ...],
) -> None:
    with pytest.raises(
        HarborSuiteError, match=r"unknown dataset|unknown task|at least one task"
    ):
        suite = get_suite(dataset)
        select_task_refs(suite, tasks)


def test_selected_task_gate_does_not_fall_back_to_all_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = get_suite("mathematical-benchmarks-v1")
    validated: list[str] = []

    def validate_task_spy(_suite: Suite, path: Path) -> list[str]:
        validated.append(path.name)
        return []

    def task_digest_spy(_path: Path) -> str:
        return "sha256:" + "0" * 64

    def check_verifier_support_spy(
        _suite: Suite,
        refs: tuple[TaskRef, ...] | None = None,
    ) -> list[str]:
        validated.extend(ref.path.name for ref in (refs or ()))
        return []

    monkeypatch.setattr(
        "benchmarks.tooling.harbor_suite.validate_task",
        validate_task_spy,
    )
    monkeypatch.setattr(
        "benchmarks.tooling.harbor_suite.task_digest",
        task_digest_spy,
    )
    monkeypatch.setattr(
        "benchmarks.tooling.harbor_suite.check_verifier_support",
        check_verifier_support_spy,
    )

    assert check_selected_tasks(suite, ("graph-counterexample",)) == []
    assert set(validated) == {"graph-counterexample"}
