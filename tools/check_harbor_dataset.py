"""Verify local Harbor task digests match the committed dataset manifest."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from harbor.models.task.task import Task

ROOT = Path(__file__).parents[1]
DATASET = ROOT / "benchmarks" / "regression-v1"
TASKS = DATASET / "tasks"


def main() -> int:
    manifest = tomllib.loads((DATASET / "dataset.toml").read_text())
    expected = {
        entry["name"].rsplit("/", 1)[-1].removeprefix("regression-v1-"): entry[
            "digest"
        ].removeprefix("sha256:")
        for entry in manifest["tasks"]
    }
    actual = {
        path.name: Task(path, disable_verification=True).checksum
        for path in TASKS.iterdir()
        if path.is_dir()
    }
    failures = []
    for name in sorted(expected.keys() | actual.keys()):
        if expected.get(name) != actual.get(name):
            failures.append(
                f"{name}: manifest={expected.get(name)!r} actual={actual.get(name)!r}"
            )
    if failures:
        print("Harbor task digest mismatch:", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Harbor task digests match for {len(actual)} tasks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
