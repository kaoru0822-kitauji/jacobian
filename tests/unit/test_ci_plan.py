from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

PLANNER = Path(__file__).parents[2] / ".github" / "scripts" / "classify-ci-paths"
VALIDATOR = Path(__file__).parents[2] / ".github" / "scripts" / "validate-ci-plan"

BOOLEAN_KEYS = (
    "run-python",
    "run-core",
    "run-integration",
    "run-coverage",
    "run-lean",
    "run-npm",
    "run-static",
    "run-build",
    "run-security",
    "run-duplicate",
)


def _expected_plan(classification: str, *enabled: str) -> dict[str, str]:
    return {
        "classification": classification,
        **{key: str(key in enabled).lower() for key in BOOLEAN_KEYS},
    }


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        ((), _expected_plan("full", *BOOLEAN_KEYS)),
        (
            ("README.md", "docs/how-to/contribute.md", ".github/CODEOWNERS"),
            _expected_plan("docs"),
        ),
        (
            ("npm/package.json", "npm/npm-packaging.test.mjs"),
            _expected_plan("npm", "run-npm"),
        ),
        (
            ("docs/index.md", "npm/package.json"),
            _expected_plan("npm", "run-npm"),
        ),
        (
            ("tests/unit/test_kernel.py",),
            _expected_plan(
                "python-core",
                "run-python",
                "run-core",
                "run-static",
            ),
        ),
        (
            ("tests/integration/test_kernel.py",),
            _expected_plan(
                "selective",
                "run-python",
                "run-integration",
                "run-lean",
                "run-static",
            ),
        ),
        (
            ("lean/JacobianLeanRuntime.lean",),
            _expected_plan("lean", "run-lean"),
        ),
        (
            ("tests/unit/test_kernel.py", "lean/JacobianLeanRuntime.lean"),
            _expected_plan(
                "selective",
                "run-python",
                "run-core",
                "run-lean",
                "run-static",
            ),
        ),
        (
            ("tests/unit/test_kernel.py", "tests/integration/test_kernel.py"),
            _expected_plan(
                "selective",
                "run-python",
                "run-core",
                "run-integration",
                "run-coverage",
                "run-lean",
                "run-static",
            ),
        ),
        (
            ("src/jacobian/kernel.py",),
            _expected_plan("full", *BOOLEAN_KEYS),
        ),
        (
            ("docs/index.md", "pyproject.toml"),
            _expected_plan("full", *BOOLEAN_KEYS),
        ),
        (
            (".github/workflows/ci.yml",),
            _expected_plan("full", *BOOLEAN_KEYS),
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
    assert plan == _expected_plan("lean", "run-lean")


@pytest.mark.parametrize(
    "args",
    [
        ("README.md",),
        ("npm/package.json",),
        ("src/jacobian/kernel.py",),
        ("tests/unit/test_kernel.py",),
        ("tests/integration/test_kernel.py",),
        ("lean/JacobianLeanRuntime.lean",),
        ("tests/unit/test_kernel.py", "lean/JacobianLeanRuntime.lean"),
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
