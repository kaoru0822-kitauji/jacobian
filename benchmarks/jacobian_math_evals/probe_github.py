"""Probe immutable GitHub trees for formal-declaration task support."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .catalog import PACKAGE_ROOT, load_sources
from .handlers.github_declarations import (
    GitHubFormalDeclarationHandler,
    NoFormalDeclarationsError,
)
from .probe_reporting import probe_error_message

DEFAULT_OUTPUT = PACKAGE_ROOT / "catalog" / "handler-probes-github.json"


def _probe(source: Any, cache_dir: Path, offline: bool) -> dict[str, Any]:
    handler = GitHubFormalDeclarationHandler(source.source_id)
    try:
        snapshot = handler.acquire(
            source,
            cache_dir=cache_dir,
            offline=offline,
        )
        [spec] = tuple(handler.iter_specs(source, snapshot, full=False))
        value = json.loads(snapshot.read_text(encoding="utf-8"))
        return {
            "source_id": source.source_id,
            "handler": "github-formal-declarations-v1",
            "status": "supported",
            "source_revision": source.immutable_revision,
            "snapshot_sha256": "sha256:"
            + hashlib.sha256(snapshot.read_bytes()).hexdigest(),
            "path": value["path"],
            "language": value["language"],
            "declaration_count": len(value["declarations"]),
            "task_id": spec.task_id,
        }
    except NoFormalDeclarationsError as error:
        return {
            "source_id": source.source_id,
            "handler": "github-formal-declarations-v1",
            "status": "manual-required",
            "source_revision": source.immutable_revision,
            "reason": probe_error_message(error, cache_dir=cache_dir),
        }
    except (
        FileNotFoundError,
        KeyError,
        OSError,
        ValueError,
        subprocess.SubprocessError,
        urllib.error.URLError,
    ) as error:
        return {
            "source_id": source.source_id,
            "handler": "github-formal-declarations-v1",
            "status": "unavailable",
            "source_revision": source.immutable_revision,
            "reason": (
                f"{type(error).__name__}: "
                f"{probe_error_message(error, cache_dir=cache_dir)}"
            ),
        }


def probe(
    *,
    cache_dir: Path,
    offline: bool,
    workers: int,
) -> dict[str, Any]:
    sources = tuple(
        source
        for source in load_sources()
        if source.host == "github.com"
        and source.immutable_revision is not None
        and source.access_state.value in {"public", "archived"}
    )
    records: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_probe, source, cache_dir, offline): source.source_id
            for source in sources
        }
        for future in as_completed(futures):
            records[futures[future]] = future.result()
    return {
        "probe_version": 1,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "handler": "github-formal-declarations-v1",
        "records": [records[source.source_id] for source in sources],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jacobian-evals-probe-github")
    parser.add_argument("--cache-dir", type=Path, default=PACKAGE_ROOT / ".cache")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be positive")
    report = probe(
        cache_dir=args.cache_dir,
        offline=args.offline,
        workers=args.workers,
    )
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
