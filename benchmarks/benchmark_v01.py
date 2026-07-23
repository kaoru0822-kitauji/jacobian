"""Reproducible local performance baselines for v0.1.

Run with:

    uv run python benchmarks/benchmark_v01.py

The benchmark records timing only. Contract and conformance tests remain the
correctness gate.
"""

from __future__ import annotations

import tempfile
from functools import partial
from pathlib import Path

import pyperf

from jacobian.canonical import canonicalize_json
from jacobian.store import ArtifactStore


def _canonicalize_rational() -> None:
    canonicalize_json(
        {
            "weights": [
                {"num": str(index * 7919), "den": str(index * 104729)}
                for index in range(1, 65)
            ]
        }
    )


def main() -> None:
    runner = pyperf.Runner()
    runner.metadata["suite"] = "jacobian-v0.1"
    runner.bench_func("canonicalize-64-rationals", _canonicalize_rational)

    with tempfile.TemporaryDirectory(prefix="jacobian-benchmark-") as directory:
        store = ArtifactStore(Path(directory))
        schema_uri = store.register_descriptor(
            kind="schema",
            name="benchmark.payload",
            version="1",
            definition={"type": "object"},
        )
        semantics_uri = store.register_descriptor(
            kind="semantics",
            name="benchmark.payload",
            version="1",
            definition={"description": "performance fixture"},
        )
        stored = store.put(
            schema_uri=schema_uri,
            semantics_uri=semantics_uri,
            payload={"values": list(range(256))},
        )
        runner.bench_func(
            "artifact-read-256-integers",
            store.get,
            stored.artifact_uri,
        )
        runner.bench_func(
            "artifact-deduplicated-put-256-integers",
            partial(
                store.put,
                schema_uri=schema_uri,
                semantics_uri=semantics_uri,
                payload={"values": list(range(256))},
            ),
        )


if __name__ == "__main__":
    main()
