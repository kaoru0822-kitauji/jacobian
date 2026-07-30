"""Check or deterministically write the local Harbor dataset manifest."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

import tomli_w
from harbor.models.task.task import Task

ROOT = Path(__file__).parents[1]
DATASET = ROOT / "benchmarks" / "regression-v1"
TASKS = DATASET / "tasks"


def _actual_digests() -> dict[str, str]:
    return {
        path.name: Task(path, disable_verification=True).checksum
        for path in sorted(TASKS.iterdir())
        if path.is_dir()
    }


def check() -> int:
    manifest = tomllib.loads((DATASET / "dataset.toml").read_text())
    expected = {
        entry["name"].rsplit("/", 1)[-1].removeprefix("regression-v1-"): entry[
            "digest"
        ].removeprefix("sha256:")
        for entry in manifest["tasks"]
    }
    actual = _actual_digests()
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


def write() -> int:
    path = DATASET / "dataset.toml"
    manifest = tomllib.loads(path.read_text())
    digests = _actual_digests()
    manifest["tasks"] = [
        {
            "name": f"jacobian/regression-v1-{name}",
            "digest": f"sha256:{digest}",
        }
        for name, digest in digests.items()
    ]
    path.write_text(tomli_w.dumps(manifest))
    print(f"Updated Harbor task digests for {len(digests)} tasks.")
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
