"""Measure repeated populated-runtime construction with pyperf.

Run with:

    uv run python benchmarks/performance/benchmark_runtime_startup.py

Each pyperf worker constructs one complete reference-enabled runtime outside the
timed region, then measures a second construction over that populated store.
This models the repeated-runtime pattern used by integration tests. It does not
claim to measure a fresh operating-system process or cold filesystem caches.
"""

from __future__ import annotations

import tempfile
from functools import partial
from pathlib import Path

import pyperf

from jacobian.runtime import CheckerAuthorityMode, create_runtime


def main() -> None:
    runner = pyperf.Runner(
        processes=3,
        values=2,
        loops=1,
        warmups=0,
    )
    runner.metadata["suite"] = "jacobian-runtime-startup"
    with tempfile.TemporaryDirectory(prefix="jacobian-runtime-startup-") as directory:
        root = Path(directory)
        initial = create_runtime(
            root,
            checker_authority=CheckerAuthorityMode.INSTALL_BUNDLED,
        )
        initial.close()
        runner.bench_func(
            "runtime-populated-same-process",
            partial(
                create_runtime,
                root,
                checker_authority=CheckerAuthorityMode.INSTALL_BUNDLED,
            ),
        )


if __name__ == "__main__":
    main()
