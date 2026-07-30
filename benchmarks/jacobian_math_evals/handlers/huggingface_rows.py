"""Schema-gated Hugging Face Dataset Viewer row extraction."""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..models import (
    OracleKind,
    SourceRecord,
    Split,
    TaskReadiness,
    TaskSpec,
)

PROBLEM_FIELDS = (
    "problem",
    "question",
    "prompt",
    "informal_statement",
    "natural_language_statement",
    "original_problem",
    "ori_question",
    "plain_text",
    "statement_lean",
    "text",
    "sample_id",
    "id",
    "src_id",
    "paper_id",
)
ANSWER_FIELDS = (
    "answer",
    "final_answer",
    "label",
    "target",
    "gold_answer",
    "ori_solution",
    "latest_label",
    "solver_status",
    "target_merged",
    "subdomain_tag",
    "role",
    "title",
)


class UnsupportedDatasetSchemaError(ValueError):
    """Dataset row lacks a sound deterministic task contract."""


def _dataset_id(source: SourceRecord) -> str:
    parts = urllib.parse.urlparse(source.canonical_url).path.strip("/").split("/")
    if parts and parts[0] == "datasets":
        parts = parts[1:]
    if len(parts) < 2:
        raise ValueError(f"not a Hugging Face dataset URL: {source.canonical_url}")
    return "/".join(parts[:2])


def _json_get(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "jacobian-math-evals/1",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        value: Any = json.load(response)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object from {url}")
    return value


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _validated_cache(path: Path) -> bool:
    digest_path = path.with_suffix(".sha256")
    if not path.exists() or not digest_path.exists():
        return False
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = digest_path.read_text(encoding="utf-8").strip()
    if actual != expected:
        raise ValueError(f"cached snapshot digest mismatch: {path}")
    return True


def _write_cache(path: Path, value: object) -> None:
    payload = _canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)
    path.with_suffix(".sha256").write_text(
        hashlib.sha256(payload).hexdigest() + "\n",
        encoding="utf-8",
    )


def _select_split(source: SourceRecord) -> tuple[str, str]:
    candidates = []
    for value in source.splits:
        config, separator, split = value.partition("/")
        if separator and config and split:
            candidates.append((config, split))
    if not candidates:
        raise UnsupportedDatasetSchemaError("dataset has no Viewer split")
    priority = {"dev": 0, "validation": 1, "test": 2, "train": 3}
    return min(
        candidates,
        key=lambda pair: (priority.get(pair[1].lower(), 10), pair),
    )


def _scalar(value: object) -> str | int | float | bool | None:
    if isinstance(value, str | int | float | bool):
        return value
    return None


def _pick(row: dict[str, Any], fields: tuple[str, ...]) -> tuple[str, object] | None:
    for field in fields:
        value = _scalar(row.get(field))
        if value is not None and str(value).strip():
            return field, value
    return None


class HuggingFaceExactAnswerHandler:
    """Extract public answer-visible diagnostics from scalar Q/A rows."""

    def __init__(self, source_id: str) -> None:
        self.source_id = source_id

    def acquire(
        self,
        source: SourceRecord,
        *,
        cache_dir: Path,
        offline: bool,
    ) -> Path:
        if source.source_id != self.source_id:
            raise ValueError(f"handler does not own {source.source_id}")
        if source.immutable_revision is None:
            raise ValueError("Hugging Face source lacks immutable revision")
        config, split = _select_split(source)
        destination = cache_dir / source.source_id / f"{config}--{split}.json"
        if _validated_cache(destination):
            actual_snapshot = (
                "sha256:" + hashlib.sha256(destination.read_bytes()).hexdigest()
            )
            if source.snapshot_sha256 == actual_snapshot:
                return destination
            if offline:
                raise ValueError("cached snapshot does not match source lock")
        if offline:
            raise FileNotFoundError(
                f"offline Dataset Viewer snapshot missing: {destination}"
            )
        dataset = _dataset_id(source)
        hub_url = "https://huggingface.co/api/datasets/" + urllib.parse.quote(
            dataset, safe="/"
        )
        before = _json_get(hub_url)
        if before.get("sha") != source.immutable_revision:
            raise ValueError("Hub revision changed since source lock")
        viewer_url = (
            "https://datasets-server.huggingface.co/first-rows?"
            + urllib.parse.urlencode(
                {"dataset": dataset, "config": config, "split": split}
            )
        )
        snapshot = _json_get(viewer_url)
        after = _json_get(hub_url)
        if after.get("sha") != source.immutable_revision:
            raise ValueError("Hub revision changed during snapshot acquisition")
        if (
            snapshot.get("dataset") != dataset
            or snapshot.get("config") != config
            or snapshot.get("split") != split
        ):
            raise ValueError("Dataset Viewer response identity mismatch")
        _write_cache(destination, snapshot)
        return destination

    def iter_full_specs(
        self,
        source: SourceRecord,
        *,
        cache_dir: Path,
        offline: bool,
    ) -> Iterator[TaskSpec]:
        """Stream every row in the selected split through digest-bound pages."""

        if source.immutable_revision is None:
            raise ValueError("Hugging Face source lacks immutable revision")
        dataset = _dataset_id(source)
        config, split = _select_split(source)
        full_dir = cache_dir / source.source_id / "full" / f"{config}--{split}"
        manifest_path = full_dir / "manifest.json"
        if offline:
            if not _validated_cache(manifest_path):
                raise FileNotFoundError(
                    f"offline full snapshot manifest missing: {manifest_path}"
                )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            hub_url = "https://huggingface.co/api/datasets/" + urllib.parse.quote(
                dataset, safe="/"
            )
            if _json_get(hub_url).get("sha") != source.immutable_revision:
                raise ValueError("Hub revision changed since source lock")
            size = _json_get(
                "https://datasets-server.huggingface.co/size?"
                + urllib.parse.urlencode({"dataset": dataset})
            )
            split_sizes = (
                size.get("size", {}).get("splits", [])
                if isinstance(size.get("size"), dict)
                else []
            )
            matched = [
                item
                for item in split_sizes
                if isinstance(item, dict)
                and item.get("config") == config
                and item.get("split") == split
                and isinstance(item.get("num_rows"), int)
            ]
            if len(matched) != 1:
                raise ValueError("Dataset Viewer size lacks selected split")
            manifest = {
                "dataset": dataset,
                "config": config,
                "split": split,
                "source_revision": source.immutable_revision,
                "num_rows": matched[0]["num_rows"],
                "page_size": 100,
            }
            _write_cache(manifest_path, manifest)
        if (
            manifest.get("dataset") != dataset
            or manifest.get("config") != config
            or manifest.get("split") != split
            or manifest.get("source_revision") != source.immutable_revision
            or not isinstance(manifest.get("num_rows"), int)
            or manifest.get("page_size") != 100
        ):
            raise ValueError("full snapshot manifest identity mismatch")
        num_rows = manifest["num_rows"]
        yielded_rows = 0
        for offset in range(0, num_rows, 100):
            page_path = full_dir / f"{offset:012d}.json"
            if not _validated_cache(page_path):
                if offline:
                    raise FileNotFoundError(
                        f"offline full snapshot page missing: {page_path}"
                    )
                page = _json_get(
                    "https://datasets-server.huggingface.co/rows?"
                    + urllib.parse.urlencode(
                        {
                            "dataset": dataset,
                            "config": config,
                            "split": split,
                            "offset": offset,
                            "length": min(100, num_rows - offset),
                        }
                    )
                )
                _write_cache(page_path, page)
            page_value: Any = json.loads(page_path.read_text(encoding="utf-8"))
            rows = page_value.get("rows") if isinstance(page_value, dict) else None
            if not isinstance(rows, list) or not rows:
                raise ValueError(f"full snapshot page has no rows: {page_path}")
            row_indices = [
                item.get("row_idx") if isinstance(item, dict) else None for item in rows
            ]
            if row_indices != list(range(offset, offset + len(rows))):
                raise ValueError(
                    f"full snapshot page row indices mismatch: {page_path}"
                )
            yielded_rows += len(rows)
            if not offline:
                hub_url = "https://huggingface.co/api/datasets/" + urllib.parse.quote(
                    dataset, safe="/"
                )
                if _json_get(hub_url).get("sha") != source.immutable_revision:
                    raise ValueError("Hub revision changed during full snapshot stream")
            yield from self.iter_specs(source, page_path, full=True)
        if yielded_rows != num_rows:
            raise ValueError(
                f"full snapshot row mismatch: expected {num_rows}, got {yielded_rows}"
            )

    def iter_specs(
        self,
        source: SourceRecord,
        snapshot: Path,
        *,
        full: bool,
    ) -> Iterator[TaskSpec]:
        value: Any = json.loads(snapshot.read_text(encoding="utf-8"))
        rows = value.get("rows") if isinstance(value, dict) else None
        if not isinstance(rows, list) or not rows:
            raise UnsupportedDatasetSchemaError("Viewer snapshot has no rows")
        extracted: list[tuple[int, str, object, str, str]] = []
        for item in rows:
            if not isinstance(item, dict) or not isinstance(item.get("row"), dict):
                continue
            row = item["row"]
            problem = _pick(row, PROBLEM_FIELDS)
            answer = _pick(row, ANSWER_FIELDS)
            row_index = item.get("row_idx")
            if (
                problem is None
                or answer is None
                or not isinstance(row_index, int)
                or isinstance(row_index, bool)
            ):
                continue
            problem_field, problem_value = problem
            answer_field, answer_value = answer
            extracted.append(
                (
                    row_index,
                    str(problem_value),
                    answer_value,
                    problem_field,
                    answer_field,
                )
            )
        if not extracted:
            raise UnsupportedDatasetSchemaError(
                "no row has scalar problem and answer fields"
            )
        extracted.sort(key=lambda item: item[0])
        selected = extracted if full else extracted[:1]
        snapshot_sha = hashlib.sha256(snapshot.read_bytes()).hexdigest()
        for (
            row_index,
            problem_text,
            answer_value,
            problem_field,
            answer_field,
        ) in selected:
            instance = {
                "source_id": source.source_id,
                "source_revision": source.immutable_revision,
                "snapshot_sha256": f"sha256:{snapshot_sha}",
                "row_index": row_index,
                "problem": problem_text,
                "problem_field": problem_field,
                "answer_field": answer_field,
                "contamination": "PUBLIC_ANSWER_VISIBLE",
            }
            yield TaskSpec(
                task_id=f"hf-{source.source_id[4:]}-{row_index:06d}",
                family="exact-answer",
                source_ids=(source.source_id,),
                split=Split.PUBLIC,
                instruction=(
                    f"{problem_text}\n\nWrite the exact requested answer to the `answer` "
                    "field of `submission.json`. Include reasoning evidence when "
                    "available. This public row is an answer-visible diagnostic."
                ),
                keywords=(
                    "mathematics",
                    "huggingface",
                    "exact-answer",
                    "public-diagnostic",
                ),
                scored=False,
                instance=instance,
                expected={
                    "answer_visible": True,
                    "expected_answer": answer_value,
                    "maximum_assurance": "UNVERIFIED",
                    "source_revision": source.immutable_revision,
                    "snapshot_sha256": f"sha256:{snapshot_sha}",
                },
                admissible_for_publish=source.access_state.value == "public",
                readiness=TaskReadiness.PUBLIC_DIAGNOSTIC,
                oracle_kind=OracleKind.PUBLIC_ANSWER,
                limitations=(
                    "public answer-visible row; exclude from scored metrics",
                    "scalar exact mapping only; no process-quality claim",
                ),
            )
