"""Measure repeated populated-kernel construction with pyperf.

Run with:

    uv run python benchmarks/benchmark_kernel_startup.py

Each pyperf worker constructs one complete reference-enabled kernel outside the
timed region, then measures a second construction over that populated store.
This models the repeated-kernel pattern used by integration tests. It does not
claim to measure a fresh operating-system process or cold filesystem caches.
"""

from __future__ import annotations

import tempfile
from functools import partial
from pathlib import Path

import pyperf

from jacobian.kernel import JacobianKernel


def main() -> None:
    runner = pyperf.Runner(
        processes=3,
        values=2,
        loops=1,
        warmups=0,
    )
    runner.metadata["suite"] = "jacobian-kernel-startup"
    with tempfile.TemporaryDirectory(prefix="jacobian-kernel-startup-") as directory:
        root = Path(directory)
        JacobianKernel(root, install_references=True)
        runner.bench_func(
            "kernel-populated-same-process",
            partial(
                JacobianKernel,
                root,
                install_references=True,
            ),
        )


if __name__ == "__main__":
    main()
