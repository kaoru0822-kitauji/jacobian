from __future__ import annotations

import json
import subprocess
from fnmatch import fnmatchcase
from pathlib import Path

import pytest

PLANNER = Path(__file__).parents[2] / ".github" / "scripts" / "classify-ci-paths"
VALIDATOR = Path(__file__).parents[2] / ".github" / "scripts" / "validate-ci-plan"
OWNERSHIP = Path(__file__).parents[2] / ".github" / "ci-impact.json"

BOOLEAN_KEYS = (
    "run-python",
    "run-core",
    "run-integration",
    "run-coverage",
    "run-compatibility",
    "run-lean",
    "run-npm",
    "run-static",
    "run-build",
    "run-security",
    "run-duplicate",
)
FUNCTIONAL_KEYS = tuple(
    key for key in BOOLEAN_KEYS if key not in {"run-coverage", "run-compatibility"}
)


def _expected_plan(classification: str, *enabled: str) -> dict[str, str]:
    return {
        "classification": classification,
        **{key: str(key in enabled).lower() for key in BOOLEAN_KEYS},
    }


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        ((), _expected_plan("exhaustive", *BOOLEAN_KEYS)),
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
            ("tests/integration/infrastructure/test_kernel.py",),
            _expected_plan(
                "python-integration",
                "run-python",
                "run-integration",
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
            (
                "tests/unit/test_kernel.py",
                "tests/integration/infrastructure/test_kernel.py",
            ),
            _expected_plan(
                "selective",
                "run-python",
                "run-core",
                "run-integration",
                "run-static",
            ),
        ),
        (
            ("src/jacobian/kernel.py",),
            _expected_plan("full", *FUNCTIONAL_KEYS),
        ),
        (
            ("tests/integration/lean/test_lean.py",),
            _expected_plan(
                "selective",
                "run-python",
                "run-integration",
                "run-lean",
                "run-static",
            ),
        ),
        (
            ("tests/integration/lean/test_lean_replayable_state_capability.py",),
            _expected_plan(
                "python-integration",
                "run-python",
                "run-integration",
                "run-static",
            ),
        ),
        (
            ("tests/integration/agent/test_agent_ab_protocol.py",),
            _expected_plan(
                "python-integration",
                "run-python",
                "run-integration",
                "run-static",
            ),
        ),
        (
            ("src/jacobian/graph_capabilities.py",),
            _expected_plan(
                "selective",
                "run-python",
                "run-core",
                "run-integration",
                "run-static",
                "run-build",
            ),
        ),
        (
            ("src/jacobian_checkers/graph_invariants.py",),
            _expected_plan(
                "selective",
                "run-python",
                "run-core",
                "run-integration",
                "run-static",
                "run-build",
            ),
        ),
        (
            ("src/jacobian/lean_proof_edit.py",),
            _expected_plan(
                "selective",
                "run-python",
                "run-core",
                "run-integration",
                "run-lean",
                "run-static",
                "run-build",
            ),
        ),
        (
            ("src/jacobian/adapters/mcp/server.py",),
            _expected_plan(
                "selective",
                "run-python",
                "run-core",
                "run-integration",
                "run-npm",
                "run-static",
                "run-build",
            ),
        ),
        (
            ("docs/index.md", "pyproject.toml"),
            _expected_plan("full", *FUNCTIONAL_KEYS),
        ),
        (
            (".github/workflows/ci.yml",),
            _expected_plan("full", *FUNCTIONAL_KEYS),
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
        timeout=30,
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
        timeout=30,
    )

    plan = dict(line.split("=", 1) for line in completed.stdout.splitlines())
    assert plan["classification"] == "exhaustive"
    assert all(value == "true" for key, value in plan.items() if key.startswith("run-"))


def test_lean_override_only_adds_lean_to_an_isolated_plan() -> None:
    completed = subprocess.run(
        [PLANNER, "--force-lean", "--", "docs/index.md"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
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
        ("tests/integration/infrastructure/test_kernel.py",),
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
        timeout=30,
    ).stdout

    subprocess.run([VALIDATOR], input=plan, check=True, text=True, timeout=30)


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
        timeout=30,
    )

    assert completed.returncode != 0


def test_every_tracked_source_file_has_explicit_suite_ownership() -> None:
    manifest = json.loads(OWNERSHIP.read_text(encoding="utf-8"))
    source_paths = subprocess.run(
        ["git", "ls-files", "src"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.splitlines()

    unowned = []
    for source_path in source_paths:
        if not any(
            fnmatchcase(source_path, pattern)
            for rule in manifest["rules"]
            for pattern in rule["patterns"]
        ):
            unowned.append(source_path)

    assert unowned == []


def test_ownership_manifest_names_only_supported_suites() -> None:
    manifest = json.loads(OWNERSHIP.read_text(encoding="utf-8"))
    suites = set(manifest["suites"])
    rule_names = [rule["name"] for rule in manifest["rules"]]

    assert manifest["version"] == 2
    assert len(suites) == len(manifest["suites"])
    assert len(rule_names) == len(set(rule_names))
    assert all(set(rule["suites"]) <= suites for rule in manifest["rules"])
    assert manifest["fallback"]["name"] == "unclassified-fail-closed"
    assert set(manifest["fallback"]["suites"]) == suites
