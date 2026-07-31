"""Check or update vendored Harbor verifier support copies.

Iterates every dataset registered in ``benchmarks/registry.toml``. For each
dataset, verifies that all task ``tests/verifier_support.py`` copies match the
repository-owned canonical support module. ``--write`` regenerates the vendored
copies.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.tooling.harbor_suite import (  # noqa: E402
    HarborSuiteError,
    check_verifier_support,
    load_registry,
    report_failures,
    report_ok,
    sync_verifier_support,
)


def check() -> int:
    failures: list[str] = []
    checked = 0
    for suite in load_registry():
        checked += 1
        failures.extend(check_verifier_support(suite))
    if report_failures(failures, header="Harbor verifier support drift"):
        return 1
    report_ok(f"Harbor verifier support matches for {checked} dataset(s).")
    return 0


def write() -> int:
    for suite in load_registry():
        sync_verifier_support(suite)
        print(f"Updated Harbor verifier support for {suite.id}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="verify vendored copies")
    mode.add_argument("--write", action="store_true", help="regenerate vendored copies")
    args = parser.parse_args()
    try:
        return check() if args.check else write()
    except HarborSuiteError as exc:
        print(f"harbor verifier support error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
