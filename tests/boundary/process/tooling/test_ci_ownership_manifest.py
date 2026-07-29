from __future__ import annotations

import json
import subprocess
from fnmatch import fnmatchcase
from pathlib import Path

from tests.boundary.process.tooling.ci import run_ci_script

OWNERSHIP = Path(__file__).parents[4] / ".github" / "ci-impact.json"


def test_every_lean_python_test_enables_the_lean_lane() -> None:
    lean_tests = sorted(
        path.as_posix()
        for path in (
            Path(__file__).parents[4] / "tests" / "boundary" / "providers" / "lean"
        ).glob("test_*.py")
    )
    assert lean_tests

    for lean_test in lean_tests:
        completed = run_ci_script("classify-ci-paths", lean_test, check=True)
        plan = dict(line.split("=", 1) for line in completed.stdout.splitlines())
        assert plan["run-lean"] == "true", lean_test


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


def test_every_tracked_support_file_has_explicit_suite_ownership() -> None:
    manifest = json.loads(OWNERSHIP.read_text(encoding="utf-8"))
    support_paths = subprocess.run(
        ["git", "ls-files", "tests/support", "tests/conftest.py"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.splitlines()

    unowned = [
        path
        for path in support_paths
        if not any(
            fnmatchcase(path, pattern)
            for rule in manifest["rules"]
            for pattern in rule["patterns"]
        )
    ]

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
