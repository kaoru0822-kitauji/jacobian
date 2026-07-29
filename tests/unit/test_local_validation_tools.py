from __future__ import annotations

import importlib.util
import subprocess
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

ROOT = Path(__file__).parents[2]
SCRIPTS = ROOT / ".github" / "scripts"


def _load(name: str, filename: str) -> ModuleType:
    loader = SourceFileLoader(name, str(SCRIPTS / filename))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_plan_combines_commit_worktree_staged_and_untracked_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    planner = _load("plan_local_tests", "plan-local-tests")
    responses = {
        ("diff", "--name-only", "base..HEAD"): ["committed.py", "same.py"],
        ("diff", "--name-only"): ["unstaged.py", "same.py"],
        ("diff", "--cached", "--name-only"): ["staged.py"],
        ("ls-files", "--others", "--exclude-standard"): ["untracked.py"],
    }
    monkeypatch.setattr(planner, "ROOT", tmp_path)
    monkeypatch.setattr(planner, "git_paths", lambda *args: responses[args])
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: None)

    assert planner.changed_paths("base") == [
        "committed.py",
        "same.py",
        "staged.py",
        "unstaged.py",
        "untracked.py",
    ]


def test_clean_test_plan_selects_no_lanes() -> None:
    planner = _load("plan_local_tests_clean", "plan-local-tests")

    assert planner.classify([]) == {"classification": "clean"}


def test_validation_receipt_distinguishes_dirty_tree_from_exact_head() -> None:
    receipts = _load("validation_receipt_dirty", "validation-receipt")
    state = {"head": "abc123", "dirty": True, "digest": "sha256:tree"}
    receipt = receipts.make_receipt(
        ["make", "check"],
        0,
        state,
        state,
        started_at="2026-07-29T00:00:00+00:00",
        finished_at="2026-07-29T00:00:01+00:00",
        duration_seconds=1.0,
    )

    assert receipt["command"] == ["make", "check"]
    assert receipt["exit_code"] == 0
    assert receipt["duration_seconds"] == 1.0
    assert receipt["tree_digest"] == "sha256:tree"
    assert receipt["tree_unchanged_during_validation"] is True
    assert receipt["dirty"] is True
    assert receipt["head_matches_validated_tree"] is False


def test_tree_digest_binds_staged_unstaged_and_untracked_content(
    tmp_path: Path,
) -> None:
    receipts = _load("validation_receipt", "validation-receipt")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
    )
    tracked = tmp_path / "tracked"
    tracked.write_text("tracked", encoding="utf-8")
    subprocess.run(["git", "add", "tracked"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=tmp_path, check=True)
    receipts.ROOT = tmp_path

    path = tmp_path / "untracked"
    path.write_text("first", encoding="utf-8")
    first = receipts.tree_state()["digest"]
    path.write_text("second", encoding="utf-8")
    second = receipts.tree_state()["digest"]

    assert first != second

    subprocess.run(["git", "add", "untracked"], cwd=tmp_path, check=True)
    staged_first = receipts.tree_state()["digest"]
    path.write_text("third", encoding="utf-8")
    subprocess.run(["git", "add", "untracked"], cwd=tmp_path, check=True)
    staged_second = receipts.tree_state()["digest"]

    assert staged_first != staged_second

    tracked.write_text("unstaged-first", encoding="utf-8")
    unstaged_first = receipts.tree_state()["digest"]
    tracked.write_text("unstaged-second", encoding="utf-8")
    unstaged_second = receipts.tree_state()["digest"]

    assert unstaged_first != unstaged_second


def test_receipt_rejects_non_ignored_repository_output(tmp_path: Path) -> None:
    receipts = _load("validation_receipt_output", "validation-receipt")
    receipts.ROOT = tmp_path
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    parser = Mock()
    parser.error.side_effect = ValueError

    try:
        receipts.output_path(tmp_path / "receipt.json", parser)
    except ValueError:
        pass
    else:
        raise AssertionError("non-ignored receipt path was accepted")
