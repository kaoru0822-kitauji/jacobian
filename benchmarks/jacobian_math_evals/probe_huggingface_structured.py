"""Probe cached Viewer snapshots for structured diagnostic recipes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .catalog import PACKAGE_ROOT, load_sources
from .handlers.huggingface_structured import (
    HuggingFaceStructuredDiagnosticHandler,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=PACKAGE_ROOT / ".cache")
    parser.add_argument(
        "--output",
        type=Path,
        default=PACKAGE_ROOT / "catalog" / "handler-probes-structured.json",
    )
    args = parser.parse_args()
    sources = {source.source_id: source for source in load_sources()}
    records: list[dict[str, object]] = []
    for snapshot in sorted(args.cache_dir.glob("src-*/*--*.json")):
        source = sources.get(snapshot.parent.name)
        if source is None:
            continue
        try:
            [spec] = tuple(
                HuggingFaceStructuredDiagnosticHandler(source.source_id).iter_specs(
                    source, snapshot, full=False
                )
            )
        except ValueError:
            continue
        else:
            records.append(
                {
                    "source_id": snapshot.parent.name,
                    "status": "supported",
                    "handler": "huggingface-structured-diagnostic-v1",
                    "family": spec.family,
                    "input_field": spec.instance["input_field"],
                    "target_field": spec.instance["target_field"],
                    "source_revision": source.immutable_revision,
                    "snapshot_sha256": "sha256:"
                    + hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                }
            )
    payload = {"probe_version": 1, "records": records}
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
