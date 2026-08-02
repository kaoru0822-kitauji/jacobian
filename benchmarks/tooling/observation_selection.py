"""Strict Harbor dataset and task selection normalization.

This module owns the selection half of observation evidence.  It deliberately
does not know how evidence, artifacts, or comparisons are built; callers pass
the repository root and suite/digest dependencies so the normalization remains
easy to exercise in isolation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _json_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def selection_known(
    dataset: str,
    heldout_manifest: dict[str, Any] | None,
    *,
    get_suite_fn: Callable[[str], Any],
    task_digest_fn: Callable[[Path], str],
) -> tuple[dict[str, str], dict[str, Path], Path | None, str, str]:
    """Return known task identities and the selected evidence class."""

    if heldout_manifest is not None:
        known = {
            str(item["id"]): str(item["digest"]) for item in heldout_manifest["tasks"]
        }
        dataset_path = None
        evidence_class = "held-out-comparative-evaluation"
        dataset_id = str(heldout_manifest.get("dataset", {}).get("id", dataset))
        return known, {}, dataset_path, evidence_class, dataset_id

    suite = get_suite_fn(dataset)
    known = {
        ref.path.name: "sha256:" + task_digest_fn(ref.path).removeprefix("sha256:")
        for ref in suite.tasks
    }
    task_dirs = {ref.path.name: ref.path for ref in suite.tasks}
    evidence_class = (
        "workflow-observation"
        if suite.claim_class == "workflow-observation"
        else suite.claim_class
    )
    return known, task_dirs, suite.path, evidence_class, suite.id


def _reject_path(value: str, *, label: str, root: Path) -> list[str]:
    """Reject absolute, traversal, and escaping-symlink paths lexically."""

    failures: list[str] = []
    candidate = Path(value)
    if candidate.is_absolute():
        failures.append(f"{label} must be relative: {value!r}")
        return failures
    parts = candidate.parts
    if any(part == ".." for part in parts):
        failures.append(f"{label} must not traverse parent directories: {value!r}")
        return failures
    if any(part in {"", "."} for part in parts) and len(parts) > 1:
        failures.append(f"{label} is malformed: {value!r}")
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            failures.append(f"{label} crosses an escaping symlink: {value!r}")
            return failures
    return failures


def validate_explicit_task_path(
    value: str,
    *,
    dataset_path: Path | None,
    task_dirs: dict[str, Path],
    root: Path,
) -> tuple[str | None, list[str]]:
    failures = _reject_path(value, label="explicit task path", root=root)
    if failures:
        return None, failures
    resolved = (root / value).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        failures.append(f"explicit task path escapes repository: {value!r}")
        return None, failures
    if dataset_path is not None:
        try:
            resolved.relative_to(dataset_path.resolve())
        except ValueError:
            failures.append(f"explicit task path is outside the dataset: {value!r}")
            return None, failures
    short = resolved.name
    expected = task_dirs.get(short)
    if expected is None or expected.resolve() != resolved:
        failures.append(f"explicit task path is not a known task: {value!r}")
        return None, failures
    manifest = resolved / "task.toml"
    if not manifest.is_file() or manifest.is_symlink():
        failures.append(f"explicit task is missing its manifest: {value!r}")
        return None, failures
    return short, failures


def normalize_selection(
    job: dict[str, Any],
    *,
    known: dict[str, str],
    task_dirs: dict[str, Path],
    dataset_path: Path | None,
    root: Path,
) -> tuple[list[str], str, dict[str, Any], list[str]]:
    """Normalize exactly one selection form; reject mixed/unknown/empty/fallback."""

    failures: list[str] = []
    has_datasets = job.get("datasets") is not None
    has_tasks = job.get("tasks") is not None
    if has_datasets and has_tasks:
        failures.append(
            "job must select tasks via datasets or explicit tasks, not both"
        )
        return [], "mixed", make_eval_args("mixed", [], None, None, 0), failures
    if has_datasets:
        return _normalize_dataset_selection(job["datasets"], known=known)
    if has_tasks:
        return _normalize_explicit_selection(
            job["tasks"],
            task_dirs=task_dirs,
            dataset_path=dataset_path,
            root=root,
        )
    failures.append(
        "job must select tasks via datasets or explicit tasks; "
        "implicit fallback to all known tasks is forbidden"
    )
    return (
        [],
        "implicit-fallback",
        make_eval_args("implicit-fallback", [], None, None, 0),
        failures,
    )


def _normalize_dataset_selection(
    datasets: Any, *, known: dict[str, str]
) -> tuple[list[str], str, dict[str, Any], list[str]]:
    failures: list[str] = []
    if not isinstance(datasets, list) or not datasets:
        failures.append("job datasets must be a non-empty array")
        return (
            [],
            "dataset-task-names",
            make_eval_args("dataset-task-names", [], None, None, 0),
            failures,
        )
    selected: set[str] = set()
    norm_datasets: list[dict[str, Any]] = []
    for entry in datasets:
        normalized, names, entry_failures = _normalize_dataset_entry(entry, known)
        failures.extend(entry_failures)
        if normalized is not None:
            norm_datasets.append(normalized)
            selected.update(names)
    selected_sorted = sorted(selected)
    if not selected_sorted and not failures:
        failures.append("dataset selection resolved to no tasks")
    eval_args = make_eval_args(
        "dataset-task-names", selected_sorted, norm_datasets, None, 0
    )
    return selected_sorted, "dataset-task-names", eval_args, failures


def _normalize_dataset_entry(
    entry: Any, known: dict[str, str]
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    if not isinstance(entry, dict):
        return None, [], ["job dataset entry must be an object"]
    path = entry.get("path")
    if not isinstance(path, str) or not path:
        return None, [], ["job dataset entry must have a non-empty path"]
    task_names = entry.get("task_names")
    if task_names is None:
        return {"path": path, "task_names": None}, list(known), []
    if not isinstance(task_names, list) or not task_names:
        return None, [], ["task_names must be a non-empty array when present"]
    names: list[str] = []
    failures: list[str] = []
    for name in task_names:
        if not isinstance(name, str) or not name:
            failures.append("task_names must be non-empty strings")
        elif name not in known:
            failures.append(f"unknown task name in dataset selection: {name}")
        else:
            names.append(name)
    return {"path": path, "task_names": names}, names, failures


def _normalize_explicit_selection(
    tasks: Any,
    *,
    task_dirs: dict[str, Path],
    dataset_path: Path | None,
    root: Path,
) -> tuple[list[str], str, dict[str, Any], list[str]]:
    failures: list[str] = []
    if not isinstance(tasks, list) or not tasks:
        failures.append("job tasks must be a non-empty array")
        return (
            [],
            "explicit-tasks",
            make_eval_args("explicit-tasks", [], None, None, 0),
            failures,
        )
    selected: set[str] = set()
    norm_tasks: list[dict[str, Any]] = []
    for entry in tasks:
        if not isinstance(entry, dict):
            failures.append("job task entry must be an object")
            continue
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            failures.append("job task entry must have a non-empty path")
            continue
        short, path_failures = validate_explicit_task_path(
            path,
            dataset_path=dataset_path,
            task_dirs=task_dirs,
            root=root,
        )
        failures.extend(path_failures)
        if short is not None:
            if short in selected:
                failures.append(f"explicit task path reused: {path!r}")
            selected.add(short)
        norm_tasks.append({"path": path})
    selected_sorted = sorted(selected)
    if not selected_sorted and not failures:
        failures.append("explicit task selection resolved to no tasks")
    eval_args = make_eval_args("explicit-tasks", selected_sorted, None, norm_tasks, 0)
    return selected_sorted, "explicit-tasks", eval_args, failures


def make_eval_args(
    mode: str,
    selection: list[str],
    datasets: list[dict[str, Any]] | None,
    tasks: list[dict[str, Any]] | None,
    n_attempts: int,
) -> dict[str, Any]:
    record = {
        "selection_mode": mode,
        "datasets": datasets,
        "tasks": tasks,
        "selection": selection,
        "n_attempts": n_attempts,
    }
    record["selection_digest"] = _json_digest(
        {
            "selection_mode": mode,
            "datasets": datasets,
            "tasks": tasks,
            "selection": selection,
        }
    )
    return record


__all__ = [
    "make_eval_args",
    "normalize_selection",
    "selection_known",
    "validate_explicit_task_path",
]
