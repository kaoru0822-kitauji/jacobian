"""Probe public GitHub repositories for bounded structured data rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .catalog import PACKAGE_ROOT, load_sources
from .handlers.github_data_rows import (
    GitHubStructuredDataHandler,
    NoStructuredDataRowError,
)
from .handlers.registry import HANDLERS


def _probe(source: Any, cache_dir: Path, offline: bool) -> dict[str, object]:
    handler = GitHubStructuredDataHandler(source.source_id)
    try:
        snapshot = handler.acquire(source, cache_dir=cache_dir, offline=offline)
        [spec] = tuple(handler.iter_specs(source, snapshot, full=False))
        return {
            "source_id": source.source_id,
            "status": "supported",
            "handler": "github-structured-data-v1",
            "family": spec.family,
            "source_revision": source.immutable_revision,
            "snapshot_sha256": "sha256:"
            + hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        }
    except NoStructuredDataRowError as error:
        return {
            "source_id": source.source_id,
            "status": "manual-required",
            "handler": "github-structured-data-v1",
            "reason": str(error),
        }
    except Exception as error:
        return {
            "source_id": source.source_id,
            "status": "unavailable",
            "handler": "github-structured-data-v1",
            "reason": f"{type(error).__name__}: {error}",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=PACKAGE_ROOT / ".cache")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--output",
        type=Path,
        default=PACKAGE_ROOT / "catalog" / "handler-probes-github-data.json",
    )
    args = parser.parse_args()
    owned = {
        handler.source_id
        for handler in HANDLERS
        if not isinstance(handler, GitHubStructuredDataHandler)
    }
    sources = tuple(
        source
        for source in load_sources()
        if source.host == "github.com"
        and source.access_state.value in {"public", "archived"}
        and source.immutable_revision
        and source.source_id not in owned
    )
    records: dict[str, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_probe, source, args.cache_dir, args.offline): source.source_id
            for source in sources
        }
        for future in as_completed(futures):
            records[futures[future]] = future.result()
    payload = {
        "probe_version": 1,
        "records": [records[source.source_id] for source in sources],
    }
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
