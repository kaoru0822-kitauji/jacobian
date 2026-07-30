"""Pinned public diagnostics from repository data rows."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..models import OracleKind, SourceRecord, Split, TaskReadiness, TaskSpec
from .github_declarations import _gh_bytes, _gh_json, _repo_name
from .huggingface_structured import RowRecipe, choose_recipe

MAX_DATA_BYTES = 1_048_576
MAX_DATA_CANDIDATES = 80
DATA_SUFFIXES = {".json", ".jsonl"}

EXACT_RECIPE = RowRecipe(
    "exact-answer",
    ("problem", "question", "prompt", "original_problem", "ori_question"),
    ("answer", "final_answer", "gold_answer", "solution", "ori_solution"),
    "Solve the supplied mathematical problem. Return the frozen reference answer",
)


class NoStructuredDataRowError(ValueError):
    """Repository has no bounded row with a supported input/target contract."""


def _choose(row: dict[str, Any]) -> tuple[RowRecipe, str, str] | None:
    for input_field in EXACT_RECIPE.input_fields:
        for target_field in EXACT_RECIPE.target_fields:
            if row.get(input_field) not in (None, "", [], {}) and row.get(
                target_field
            ) not in (None, "", [], {}):
                return EXACT_RECIPE, input_field, target_field
    return choose_recipe(row)


def _rows(value: object) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if _choose(value) is not None:
            yield value
        for child in value.values():
            if isinstance(child, list):
                yield from _rows(child)
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, dict):
                if _choose(child) is not None:
                    yield child
                else:
                    yield from _rows(child)


def _parse_rows(payload: bytes, suffix: str) -> Iterator[dict[str, Any]]:
    text = payload.decode("utf-8")
    if suffix == ".jsonl":
        for line in text.splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            yield from _rows(value)
    else:
        yield from _rows(json.loads(text))


def _candidate_paths(tree: dict[str, Any]) -> tuple[str, ...]:
    items = tree.get("tree")
    if not isinstance(items, list):
        raise ValueError("GitHub tree response lacks tree")
    candidates: list[tuple[int, str]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "blob":
            continue
        path = item.get("path")
        size = item.get("size")
        if (
            not isinstance(path, str)
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size <= 0
            or size > MAX_DATA_BYTES
            or Path(path).suffix.lower() not in DATA_SUFFIXES
        ):
            continue
        lower = path.lower()
        priority = (
            0 if any(word in lower for word in ("data", "test", "example")) else 1
        )
        candidates.append((priority, path))
    return tuple(path for _, path in sorted(candidates)[:MAX_DATA_CANDIDATES])


def _compact(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class GitHubStructuredDataHandler:
    """Create a bounded exact reproduction from repository data."""

    def __init__(self, source_id: str) -> None:
        self.source_id = source_id

    def acquire(
        self,
        source: SourceRecord,
        *,
        cache_dir: Path,
        offline: bool,
    ) -> Path:
        if source.immutable_revision is None:
            raise ValueError("GitHub source lacks immutable revision")
        destination = cache_dir / source.source_id / "structured-data-row.json"
        digest_path = destination.with_suffix(".sha256")
        if destination.exists() and digest_path.exists():
            actual = hashlib.sha256(destination.read_bytes()).hexdigest()
            if actual != digest_path.read_text(encoding="utf-8").strip():
                raise ValueError("cached GitHub data snapshot digest mismatch")
            return destination
        if offline:
            raise FileNotFoundError(
                f"offline GitHub data snapshot missing: {destination}"
            )
        repo = _repo_name(source)
        tree = _gh_json(
            [
                "--method",
                "GET",
                f"repos/{repo}/git/trees/{source.immutable_revision}",
                "-f",
                "recursive=1",
            ]
        )
        selected: dict[str, Any] | None = None
        for path in _candidate_paths(tree):
            payload = _gh_bytes(
                [
                    "--method",
                    "GET",
                    f"repos/{repo}/contents/{path}",
                    "-f",
                    f"ref={source.immutable_revision}",
                ]
            )
            try:
                row = next(_parse_rows(payload, Path(path).suffix.lower()))
            except (UnicodeDecodeError, json.JSONDecodeError, StopIteration):
                continue
            choice = _choose(row)
            if choice is None:
                continue
            recipe, input_field, target_field = choice
            selected = {
                "source_id": source.source_id,
                "repository": repo,
                "revision": source.immutable_revision,
                "path": path,
                "family": recipe.family,
                "instruction": recipe.instruction,
                "input_field": input_field,
                "input": row[input_field],
                "target_field": target_field,
                "target": row[target_field],
                "content_sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
            }
            break
        if selected is None:
            raise NoStructuredDataRowError(
                "no bounded JSON row matches a supported input/target contract"
            )
        payload = (
            json.dumps(selected, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        digest_path.write_text(
            hashlib.sha256(payload).hexdigest() + "\n", encoding="utf-8"
        )
        return destination

    def iter_specs(
        self,
        source: SourceRecord,
        snapshot: Path,
        *,
        full: bool,
    ) -> Iterator[TaskSpec]:
        del full
        value: Any = json.loads(snapshot.read_text(encoding="utf-8"))
        snapshot_sha = hashlib.sha256(snapshot.read_bytes()).hexdigest()
        yield TaskSpec(
            task_id=f"github-data-{source.source_id[4:]}",
            family=value["family"],
            source_ids=(source.source_id,),
            split=Split.PUBLIC,
            instruction=(
                f"{value['instruction']} in the `answer` field of "
                "`submission.json`.\n\nFrozen input:\n"
                f"{_compact(value['input'])}\n\n"
                "This is a public answer-visible reproduction diagnostic."
            ),
            keywords=(
                "mathematics",
                "github",
                value["family"],
                "public-diagnostic",
            ),
            scored=False,
            instance={
                key: value[key]
                for key in (
                    "source_id",
                    "repository",
                    "revision",
                    "path",
                    "input_field",
                    "input",
                    "target_field",
                    "content_sha256",
                )
            }
            | {
                "snapshot_sha256": f"sha256:{snapshot_sha}",
                "contamination": "PUBLIC_ANSWER_VISIBLE",
            },
            expected={
                "answer_visible": True,
                "expected_answer": _compact(value["target"]),
                "maximum_assurance": "UNVERIFIED",
                "source_revision": source.immutable_revision,
                "snapshot_sha256": f"sha256:{snapshot_sha}",
            },
            admissible_for_publish=source.access_state.value == "public",
            readiness=TaskReadiness.PUBLIC_DIAGNOSTIC,
            oracle_kind=OracleKind.PUBLIC_ANSWER,
            limitations=(
                "public answer-visible row; exclude from scored metrics",
                "exact reproduction only; no theorem-validity claim",
            ),
        )
