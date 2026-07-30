"""Load and validate the versioned source catalog."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import SourceRecord, SourceState

PACKAGE_ROOT = Path(__file__).parent
CATALOG_PATH = PACKAGE_ROOT / "catalog" / "sources.json"
LOCK_PATH = PACKAGE_ROOT / "catalog" / "source-lock.json"
EXPECTED_SOURCE_COUNT = 176


def stable_source_id(canonical_url: str) -> str:
    digest = hashlib.sha256(canonical_url.rstrip("/").encode()).hexdigest()[:12]
    return f"src-{digest}"


def _load_lock() -> dict[str, dict[str, Any]]:
    if not LOCK_PATH.exists():
        return {}
    data = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    if data.get("lock_version") != 1:
        raise ValueError("unsupported source lock version")
    return {item["source_id"]: item for item in data["sources"]}


def load_sources() -> tuple[SourceRecord, ...]:
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if raw.get("manifest_version") != "1.0":
        raise ValueError("unsupported source manifest version")
    if raw.get("record_count") != EXPECTED_SOURCE_COUNT:
        raise ValueError("catalog record_count is not 176")
    locks = _load_lock()
    records: list[SourceRecord] = []
    for item in raw["records"]:
        source_id = stable_source_id(item["canonical_url"])
        if item.get("source_id") != source_id:
            raise ValueError(f"catalog source_id mismatch for {item['canonical_url']}")
        locked = locks.get(source_id, {})
        records.append(
            SourceRecord(
                source_id=source_id,
                url=item["url"],
                canonical_url=locked.get("canonical_url", item["canonical_url"]),
                kind=item["kind"],
                host=item["host"],
                source_type=item["source_type"],
                domain=item["domain"],
                claim_type=item["claim_type"],
                verification_level=item["verification_level"],
                artifacts=item["artifacts"],
                conjecture_name=item["conjecture_name"],
                upstream_status=item["status"],
                usefulness=item["usefulness"],
                notes=item["notes"],
                acquisition_hint=item["acquisition_hint"],
                duplicate_urls=tuple(item["duplicate_urls"]),
                access_state=SourceState(locked.get("access_state", "unresolved")),
                immutable_revision=locked.get("immutable_revision"),
                license=locked.get("license"),
                evidence_timestamp=locked.get("evidence_timestamp"),
                snapshot_sha256=locked.get("snapshot_sha256"),
                redirect_from=tuple(locked.get("redirect_from", [])),
                configurations=tuple(locked.get("configurations", [])),
                splits=tuple(locked.get("splits", [])),
                row_count=locked.get("row_count"),
                gated=locked.get("gated"),
                parquet_shards=tuple(locked.get("parquet_shards", [])),
            )
        )
    ids = [record.source_id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("stable source IDs collide")
    return tuple(records)
