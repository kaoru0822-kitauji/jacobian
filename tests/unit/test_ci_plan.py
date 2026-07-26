from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

PLANNER = Path(__file__).parents[2] / ".github" / "scripts" / "classify-ci-paths"
VALIDATOR = Path(__file__).parents[2] / ".github" / "scripts" / "validate-ci-plan"


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


@pytest.mark.parametrize(
    "args",
    [
        ("README.md",),
        ("npm/package.json",),
        ("src/jacobian/kernel.py",),
        ("--force-lean", "--", "README.md"),
        ("--force-lean", "--", "npm/package.json"),
    ],
)
def test_ci_plan_output_is_internally_consistent(args: tuple[str, ...]) -> None:
    plan = subprocess.run(
        [PLANNER, *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    subprocess.run([VALIDATOR], input=plan, check=True, text=True)


@pytest.mark.parametrize(
    "plan",
    [
        "",
        "classification=docs\nrun-python=flase\n",
        "classification=full\n"
        "run-python=false\n"
        "run-lean=false\n"
        "run-npm=false\n"
        "run-static=false\n"
        "run-build=false\n"
        "run-security=false\n"
        "run-duplicate=false\n",
        "classification=docs\n"
        "classification=docs\n"
        "run-python=false\n"
        "run-lean=false\n"
        "run-npm=false\n"
        "run-static=false\n"
        "run-build=false\n"
        "run-security=false\n"
        "run-duplicate=false\n",
        "classification=docs\n"
        "run-python=false\n"
        "run-lean=false\n"
        "run-npm=true\n"
        "run-static=false\n"
        "run-build=false\n"
        "run-security=false\n"
        "run-duplicate=false\n",
    ],
)
def test_ci_plan_validator_rejects_malformed_or_incoherent_plans(plan: str) -> None:
    completed = subprocess.run(
        [VALIDATOR],
        input=plan,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
