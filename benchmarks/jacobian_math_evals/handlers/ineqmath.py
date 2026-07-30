"""Pinned wrapper around Harbor's accepted IneqMath adapter semantics."""

from __future__ import annotations

import hashlib
import json
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

SOURCE_ID = "src-0de4dff1ce92"
UPSTREAM_ADAPTER_COMMIT = "e76f7e32f5644fb9f648cd23151aac5c67492ea0"
UPSTREAM_ADAPTER_TREE_SHA256 = (
    "e25ccdb4edf589d6b7a4f20e3f41247f959f11f8113d3a524b787980a2ffd6e5"
)
DEV_SNAPSHOT_SHA256 = "625296f60c6847dbad77c60b518588c0d5e1722cd8822ee5e35d9d0dcaabfe9b"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validated_rows(snapshot: Path) -> list[dict[str, str]]:
    value: Any = json.loads(snapshot.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("IneqMath dev snapshot must be a JSON array")
    rows: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"IneqMath row {index} is not an object")
        required = ("data_id", "problem", "answer", "type", "data_split")
        if any(not isinstance(item.get(field), str) for field in required):
            raise ValueError(f"IneqMath row {index} has invalid required fields")
        if item["type"] not in {"bound", "relation"}:
            raise ValueError(f"IneqMath row {index} has unsupported type")
        if item["data_split"] != "dev":
            raise ValueError(f"IneqMath row {index} is not from dev")
        rows.append({field: item[field] for field in required})
    ids = [row["data_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("IneqMath data_id values are not unique")
    return sorted(rows, key=lambda row: (int(row["data_id"]), row["data_id"]))


class IneqMathHandler:
    """Freeze public dev rows; preserve accepted result-level semantics."""

    source_id = SOURCE_ID

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
            raise ValueError("IneqMath source lacks immutable revision")
        destination = cache_dir / source.source_id / "dev.json"
        metadata_path = destination.with_suffix(".metadata.json")
        expected_metadata = {
            "source_id": source.source_id,
            "source_revision": source.immutable_revision,
            "snapshot_sha256": source.snapshot_sha256,
            "payload_sha256": f"sha256:{DEV_SNAPSHOT_SHA256}",
        }
        if destination.exists():
            if (
                not metadata_path.exists()
                or json.loads(metadata_path.read_text(encoding="utf-8"))
                != expected_metadata
            ):
                raise ValueError("cached IneqMath snapshot provenance mismatch")
            digest = _sha256(destination.read_bytes())
            if digest != DEV_SNAPSHOT_SHA256:
                raise ValueError("cached IneqMath snapshot digest mismatch")
            return destination
        if offline:
            raise FileNotFoundError(f"offline IneqMath snapshot missing: {destination}")
        url = (
            "https://huggingface.co/datasets/AI4Math/IneqMath/resolve/"
            f"{source.immutable_revision}/json/dev.json"
        )
        request = urllib.request.Request(
            url, headers={"User-Agent": "jacobian-math-evals/1"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
        if _sha256(payload) != DEV_SNAPSHOT_SHA256:
            raise ValueError("downloaded IneqMath snapshot digest mismatch")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".tmp")
        temporary.write_bytes(payload)
        temporary.replace(destination)
        metadata_path.write_text(
            json.dumps(expected_metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return destination

    def iter_specs(
        self,
        source: SourceRecord,
        snapshot: Path,
        *,
        full: bool,
    ) -> Iterator[TaskSpec]:
        rows = _validated_rows(snapshot)
        selected = rows if full else rows[:1]
        for row in selected:
            instance = {
                "source_id": source.source_id,
                "source_revision": source.immutable_revision,
                "snapshot_sha256": f"sha256:{DEV_SNAPSHOT_SHA256}",
                "upstream_adapter_commit": UPSTREAM_ADAPTER_COMMIT,
                "upstream_adapter_tree_sha256": (
                    f"sha256:{UPSTREAM_ADAPTER_TREE_SHA256}"
                ),
                "data_id": row["data_id"],
                "problem": row["problem"],
                "answer_type": row["type"],
                "contamination": "PUBLIC_ANSWER_VISIBLE",
            }
            yield TaskSpec(
                task_id=f"ineqmath-dev-{int(row['data_id']):03d}",
                family="exact-answer",
                source_ids=(source.source_id,),
                split=Split.PUBLIC,
                instruction=(
                    f"{row['problem']}\n\nGive rigorous reasoning, then write the "
                    "final result in `submission.json`. Set `answer` to the exact "
                    "bound or relation requested. This public dev case is an "
                    "answer-visible diagnostic, not a held-out scored case."
                ),
                keywords=(
                    "mathematics",
                    "inequality",
                    "exact-answer",
                    "ineqmath",
                    "public-diagnostic",
                ),
                scored=False,
                instance=instance,
                expected={
                    "answer_visible": True,
                    "expected_answer": row["answer"],
                    "maximum_assurance": "UNVERIFIED",
                    "source_revision": source.immutable_revision,
                    "snapshot_sha256": f"sha256:{DEV_SNAPSHOT_SHA256}",
                },
                admissible_for_publish=True,
                readiness=TaskReadiness.PUBLIC_DIAGNOSTIC,
                oracle_kind=OracleKind.PUBLIC_ANSWER,
                manual=False,
                limitations=(
                    "public answer-visible dev row; exclude from scored metrics",
                    "result-level exact mapping only; no released process oracle",
                ),
            )
