from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


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
            "tests/integration/test_lean.py",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 4
    assert "Lean runtime tests cannot run under pytest-xdist" in completed.stderr
    assert "make test-lean" in completed.stderr
