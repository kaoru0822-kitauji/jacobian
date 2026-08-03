#!/usr/bin/env python3
"""Run non-executing static checks for repository-owned benchmark code.

The benchmark tree contains verifier and validation Python alongside ordinary
benchmark tooling.  Ruff scans the complete tree, including those boundary
directories.  Mypy checks the benchmark control scripts with the repository's
strict configuration while skipping imported implementation bodies; importing
or executing a task, verifier, Oracle, or model is not part of this gate.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUFF_TARGETS = ("benchmarks", "tools/check_benchmark_static.py")
MYPY_TARGETS = (
    "tools/check_benchmark_adapters.py",
    "tools/check_benchmark_contracts.py",
    "tools/check_benchmark_static.py",
)


def _commands() -> tuple[tuple[str, tuple[str, ...]], ...]:
    python = sys.executable
    return (
        (
            "Ruff lint",
            (python, "-m", "ruff", "check", *RUFF_TARGETS),
        ),
        (
            "Ruff format",
            (python, "-m", "ruff", "format", "--check", *RUFF_TARGETS),
        ),
        (
            "mypy",
            (
                python,
                "-m",
                "mypy",
                "--follow-imports=skip",
                *MYPY_TARGETS,
            ),
        ),
    )


def main() -> int:
    """Run every static check and stop at the first failed gate."""
    for label, command in _commands():
        try:
            result = subprocess.run(command, cwd=ROOT, check=False)
        except OSError as exc:
            print(f"{label} could not start: {exc}", file=sys.stderr)
            return 1
        if result.returncode:
            print(f"{label} failed with exit code {result.returncode}", file=sys.stderr)
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
