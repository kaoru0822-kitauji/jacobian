from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

PLANNER = Path(__file__).parents[2] / ".github" / "scripts" / "classify-ci-paths"


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (
            (),
            {
                "classification": "full",
                "run-python": "true",
                "run-lean": "true",
                "run-npm": "true",
                "run-static": "true",
                "run-build": "true",
                "run-security": "true",
                "run-duplicate": "true",
            },
        ),
        (
            ("README.md", "docs/how-to/contribute.md", ".github/CODEOWNERS"),
            {
                "classification": "docs",
                "run-python": "false",
                "run-lean": "false",
                "run-npm": "false",
                "run-static": "false",
                "run-build": "false",
                "run-security": "false",
                "run-duplicate": "false",
            },
        ),
        (
            ("npm/package.json", "npm/npm-packaging.test.mjs"),
            {
                "classification": "npm",
                "run-python": "false",
                "run-lean": "false",
                "run-npm": "true",
                "run-static": "false",
                "run-build": "false",
                "run-security": "false",
                "run-duplicate": "false",
            },
        ),
        (
            ("docs/index.md", "npm/package.json"),
            {
                "classification": "npm",
                "run-python": "false",
                "run-lean": "false",
                "run-npm": "true",
                "run-static": "false",
                "run-build": "false",
                "run-security": "false",
                "run-duplicate": "false",
            },
        ),
        (
            ("src/jacobian/kernel.py",),
            {
                "classification": "full",
                "run-python": "true",
                "run-lean": "true",
                "run-npm": "true",
                "run-static": "true",
                "run-build": "true",
                "run-security": "true",
                "run-duplicate": "true",
            },
        ),
        (
            ("docs/index.md", "pyproject.toml"),
            {
                "classification": "full",
                "run-python": "true",
                "run-lean": "true",
                "run-npm": "true",
                "run-static": "true",
                "run-build": "true",
                "run-security": "true",
                "run-duplicate": "true",
            },
        ),
        (
            (".github/workflows/ci.yml",),
            {
                "classification": "full",
                "run-python": "true",
                "run-lean": "true",
                "run-npm": "true",
                "run-static": "true",
                "run-build": "true",
                "run-security": "true",
                "run-duplicate": "true",
            },
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


def test_full_override_expands_an_isolated_plan() -> None:
    completed = subprocess.run(
        [PLANNER, "--force-full", "--", "docs/index.md"],
        check=True,
        capture_output=True,
        text=True,
    )

    plan = dict(line.split("=", 1) for line in completed.stdout.splitlines())
    assert plan["classification"] == "full"
    assert all(value == "true" for key, value in plan.items() if key.startswith("run-"))


def test_lean_override_only_adds_lean_to_an_isolated_plan() -> None:
    completed = subprocess.run(
        [PLANNER, "--force-lean", "--", "docs/index.md"],
        check=True,
        capture_output=True,
        text=True,
    )

    plan = dict(line.split("=", 1) for line in completed.stdout.splitlines())
    assert plan == {
        "classification": "docs",
        "run-python": "false",
        "run-lean": "true",
        "run-npm": "false",
        "run-static": "false",
        "run-build": "false",
        "run-security": "false",
        "run-duplicate": "false",
    }
