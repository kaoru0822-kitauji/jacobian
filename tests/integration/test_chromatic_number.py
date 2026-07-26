"""Bounded exact chromatic-number capability tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import z3  # type: ignore[import-untyped]

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityRequest,
    CapabilityResult,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel

pytestmark = pytest.mark.integration


def _invoke(
    kernel: JacobianKernel,
    graph: dict[str, object],
) -> CapabilityResult:
    return kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.invariant.chromatic_number.compute",
            input={"graph": graph, "resource_budget": {"wall_seconds": 5}},
        )
    )


def test_chromatic_number_returns_first_satisfying_k_with_witness(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    result = _invoke(
        kernel,
        {
            "vertices": ["a", "b", "c"],
            "edges": [["a", "b"], ["b", "c"], ["c", "a"]],
        },
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE
    assert result.output["status"] == "EXACT"
    assert result.output["chromatic_number"] == 3
    assert result.output["lower_bound"] == 3
    assert result.output["upper_bound"] == 3
    assert [step["status"] for step in result.output["tested"]] == [
        "UNSATISFIABLE",
        "SATISFIABLE",
    ]
    assert len(result.artifact_uris) == 3
    input_uri, output_uri, obligation_uri = result.artifact_uris
    assert kernel.store.get(output_uri).manifest.parents == (input_uri,)
    assert kernel.store.get(output_uri).payload == result.output
    assert frozenset(kernel.store.get(obligation_uri).manifest.parents) == frozenset(
        (input_uri, output_uri)
    )
    assert result.obligations[0].obligation_uri == obligation_uri
    assert result.relationships[0].obligation_uris == (obligation_uri,)

    coloring = result.output["coloring"]
    assert set(coloring) == {"a", "b", "c"}
    assert all(
        coloring[left] != coloring[right]
        for left, right in (
            ("a", "b"),
            ("b", "c"),
            ("c", "a"),
        )
    )


def test_chromatic_number_timeout_is_unknown_and_preserves_bounds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path)
    monkeypatch.setattr(z3.Solver, "check", lambda _solver: z3.unknown)

    result = _invoke(
        kernel,
        {
            "vertices": ["a", "b", "c", "d", "e"],
            "edges": [
                ["a", "b"],
                ["b", "c"],
                ["c", "d"],
                ["d", "e"],
                ["e", "a"],
            ],
        },
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.completeness.status is CapabilityCompletenessStatus.UNKNOWN
    assert result.output["status"] == "UNKNOWN"
    assert result.output["chromatic_number"] is None
    assert result.output["lower_bound"] <= result.output["upper_bound"]
    assert result.output["tested"][-1]["status"] == "UNKNOWN"
    assert len(result.artifact_uris) == 3
    assert kernel.store.get(result.artifact_uris[1]).payload["status"] == "UNKNOWN"
    obligation = kernel.store.get(result.artifact_uris[2])
    assert obligation.payload["claimed_value"] is None
    assert obligation.payload["status"] == "UNKNOWN"


def test_chromatic_number_rejects_repeated_undirected_edges(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    result = _invoke(
        kernel,
        {
            "vertices": ["a", "b"],
            "edges": [["a", "b"], ["b", "a"]],
        },
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.assurance.level is CapabilityAssuranceLevel.HEURISTIC
    assert result.diagnostics[0].code == "INVALID_CHROMATIC_NUMBER_REQUEST"
    assert result.artifact_uris == ()
