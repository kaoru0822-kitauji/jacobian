from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

PLANNER = Path(__file__).parents[2] / ".github" / "scripts" / "classify-ci-paths"


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        ((), {"run-lean": "true", "classification": "full"}),
        (
            ("README.md", "docs/how-to/contribute.md", ".github/CODEOWNERS"),
            {"run-lean": "false", "classification": "isolated"},
        ),
        (
            ("npm/package.json", "npm/npm-packaging.test.mjs"),
            {"run-lean": "false", "classification": "isolated"},
        ),
        (
            ("src/jacobian/kernel.py",),
            {"run-lean": "true", "classification": "full"},
        ),
        (
            ("docs/index.md", "pyproject.toml"),
            {"run-lean": "true", "classification": "full"},
        ),
        (
            (".github/workflows/ci.yml",),
            {"run-lean": "true", "classification": "full"},
        ),
    ],
)
def test_ci_plan_fails_closed_outside_isolated_paths(
    paths: tuple[str, ...],
    expected: dict[str, str],
) -> None:
    completed = subprocess.run(
        [PLANNER, *paths],
        check=True,
        capture_output=True,
        text=True,
    )

    assert (
        dict(line.split("=", 1) for line in completed.stdout.splitlines()) == expected
    )
