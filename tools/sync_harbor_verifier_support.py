"""Check or update the self-contained Harbor verifier support copies."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
DATASET = ROOT / "benchmarks" / "regression-v1"
SOURCE = DATASET / "verifier_support.py"
TASKS = DATASET / "tasks"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _targets() -> tuple[Path, ...]:
    return tuple(
        task / "tests" / "verifier_support.py"
        for task in sorted(TASKS.iterdir())
        if task.is_dir()
    )


def check() -> int:
    expected = _digest(SOURCE)
    stale = [
        target
        for target in _targets()
        if not target.is_file() or _digest(target) != expected
    ]
    if stale:
        print("Harbor verifier support drift:", file=sys.stderr)
        for target in stale:
            print(target.relative_to(ROOT), file=sys.stderr)
        return 1
    print(f"Harbor verifier support matches for {len(_targets())} tasks.")
    return 0


def write() -> int:
    for target in _targets():
        shutil.copyfile(SOURCE, target)
    print(f"Updated Harbor verifier support for {len(_targets())} tasks.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    return check() if args.check else write()


if __name__ == "__main__":
    raise SystemExit(main())
