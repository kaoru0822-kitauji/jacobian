"""Executable checks for task-owned Harbor verifier support copies."""

from __future__ import annotations

from pathlib import Path

from benchmarks.tooling.harbor_suite import check_verifier_support, load_registry

ROOT = Path(__file__).parents[2]


def test_harbor_verifier_support_is_local_and_valid() -> None:
    for suite in load_registry():
        assert check_verifier_support(suite) == []
