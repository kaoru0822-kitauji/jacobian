from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[3]


def test_parallel_pytest_rejects_selected_lean_runtime_tests() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-n",
            "2",
            "-m",
            "lean_runtime",
            "tests/integration/lean/test_lean.py",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 4
    assert "Lean runtime tests cannot run under pytest-xdist" in completed.stderr
    assert "make test-lean" in completed.stderr


def test_parallel_pytest_rejects_lean_runtime_execution_under_xdist_workers() -> None:
    """xdist workers clear numprocesses; the guard must still fail closed there."""

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-n",
            "2",
            "tests/integration/lean/test_lean.py::test_mathlib_warmup_starts_only_once",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )

    combined = f"{completed.stdout}\n{completed.stderr}"
    assert completed.returncode != 0
    assert "passed" not in completed.stdout
    assert (
        "no tests ran" in combined
        or "Lean runtime tests cannot run under pytest-xdist" in combined
    )
    assert (
        "make test-lean" in combined
        or "lean_runtime" in combined.lower()
        or "test_lean.py" in combined
    )
