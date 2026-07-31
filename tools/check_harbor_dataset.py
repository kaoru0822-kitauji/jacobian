"""Check or deterministically write Harbor dataset manifests.

Iterates every dataset registered in ``benchmarks/registry.toml``. For each
dataset, verifies that the committed ``dataset.toml`` matches the suite header
plus Harbor-native task digests and that task topology is sound
(``--check``) or regenerates the manifest (``--write``). Dataset manifests are
generated artifacts; do not hand-edit the ``[[tasks]]`` list.
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
    check_suite,
    load_registry,
    report_failures,
    report_ok,
    write_dataset_manifest,
)


def check() -> int:
    failures: list[str] = []
    checked = 0
    for suite in load_registry():
        checked += 1
        failures.extend(check_suite(suite))
    if report_failures(failures, header="Harbor dataset manifest drift"):
        return 1
    report_ok(f"Harbor datasets match for {checked} dataset(s).")
    return 0


def write() -> int:
    for suite in load_registry():
        write_dataset_manifest(suite)
        print(f"Updated Harbor dataset manifest for {suite.id}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="verify committed manifests")
    mode.add_argument("--write", action="store_true", help="regenerate manifests")
    args = parser.parse_args()
    try:
        return check() if args.check else write()
    except HarborSuiteError as exc:
        print(f"harbor dataset check error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
