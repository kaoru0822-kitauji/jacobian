"""Reproducible local performance baselines for v0.2.

Run with:

    uv run python benchmarks/benchmark_v02.py

The benchmark records timing only. Contract and conformance tests remain the
correctness gate.
"""

from __future__ import annotations

import tempfile
from functools import partial
from pathlib import Path

import pyperf

from jacobian.contracts.polytope import PolytopeSeparateRequest
from jacobian.kernel import JacobianKernel


def _q(numerator: int, denominator: int = 1) -> dict[str, str]:
    return {"num": str(numerator), "den": str(denominator)}


def main() -> None:
    runner = pyperf.Runner()
    runner.metadata["suite"] = "jacobian-v0.2"

    with tempfile.TemporaryDirectory(prefix="jacobian-v02-benchmark-") as directory:
        kernel = JacobianKernel(Path(directory), install_references=True)
        graph = kernel.references["graph_paths"]
        candidate = kernel.artifacts.put(
            schema_uri=graph.candidate_schema_uri,
            semantics_uri=graph.semantics_uri,
            payload={
                "vertices": ["a", "b", "c", "d", "e"],
                "arcs": [
                    ["a", "b"],
                    ["a", "c"],
                    ["b", "d"],
                    ["c", "d"],
                    ["d", "e"],
                ],
            },
        )
        runner.bench_func(
            "canonicalize-five-vertex-digraph",
            partial(
                kernel.structures.canonicalize,
                structure_uri=candidate.artifact_uri,
                plugin_id=graph.plugin_id,
                wall_seconds=30,
            ),
        )

        point = kernel.artifacts.put(
            schema_uri=kernel.polytope.point_schema_uri,
            semantics_uri=kernel.polytope.semantics_uri,
            payload={
                "point_schema_version": "1",
                "coordinates": [_q(1, 2), _q(1, 2), _q(1, 2)],
            },
        )
        generators = kernel.artifacts.put(
            schema_uri=kernel.polytope.generator_set_schema_uri,
            semantics_uri=kernel.polytope.semantics_uri,
            payload={
                "generator_set_schema_version": "1",
                "dimension": 3,
                "generators": [
                    {"values": [_q(0), _q(0), _q(0)]},
                    {"values": [_q(1), _q(0), _q(0)]},
                    {"values": [_q(0), _q(1), _q(0)]},
                    {"values": [_q(0), _q(0), _q(1)]},
                ],
            },
        )
        runner.bench_func(
            "separate-triangle-stable-set-point",
            kernel.polytope.separate,
            PolytopeSeparateRequest(
                point_uri=point.artifact_uri,
                generator_set_uri=generators.artifact_uri,
            ),
        )


if __name__ == "__main__":
    main()
