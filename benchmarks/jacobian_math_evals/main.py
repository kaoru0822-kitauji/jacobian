"""Command-line entry point for jacobian-math-evals."""

from __future__ import annotations

import argparse
from pathlib import Path

from .catalog import PACKAGE_ROOT
from .compiler import compile_tasks
from .models import Split


def _csv(value: str) -> frozenset[str]:
    return frozenset(item.strip() for item in value.split(",") if item.strip())


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="jacobian-math-evals")
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--limit", type=int)
    result.add_argument("--overwrite", action="store_true")
    result.add_argument("--task-ids", type=_csv, default=frozenset())
    result.add_argument("--source-ids", type=_csv, default=frozenset())
    result.add_argument(
        "--split", choices=tuple(Split), type=Split, default=Split.COVERAGE
    )
    result.add_argument("--cache-dir", type=Path, default=PACKAGE_ROOT / ".cache")
    result.add_argument("--offline", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.offline and args.cache_dir is not None and not args.cache_dir.exists():
        parser().error("--offline requires an existing --cache-dir")
    compile_tasks(
        output_dir=args.output_dir,
        split=args.split,
        limit=args.limit,
        overwrite=args.overwrite,
        task_ids=args.task_ids,
        source_ids=args.source_ids,
        cache_dir=args.cache_dir,
        offline=args.offline,
        strict_coverage=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
