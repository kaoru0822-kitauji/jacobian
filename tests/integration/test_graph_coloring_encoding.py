"""Graph-owned coloring encodings and independent replay tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.contracts.capabilities import (
    CapabilityMode,
    CapabilityRequest,
    CapabilityResult,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel

pytestmark = [
    pytest.mark.usefixtures("initialized_kernel_store_with_references"),
]


def _encode(kernel: JacobianKernel) -> CapabilityResult:
    return kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.coloring.encode_k_cnf",
            input={
                "graph": {
                    "vertices": ["c", "a", "b"],
                    "edges": [["b", "a"], ["c", "b"], ["a", "c"]],
                },
                "colors": 3,
            },
        )
    )


def test_graph_coloring_encoding_is_canonical_and_inspectable(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)

    result = _encode(kernel)

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["graph"] == {
        "graph_schema_version": "1",
        "vertices": ["a", "b", "c"],
        "edges": [["a", "b"], ["a", "c"], ["b", "c"]],
    }
    assert result.output["variable_count"] == 9
    assert result.output["clause_count"] == 21
    assert result.output["checker_id"] is None
    assert len(result.artifact_uris) == 5


def test_graph_coloring_encoding_replays_through_generic_certificate_verifier(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    encoded = _encode(kernel)

    assert encoded.output["checker_id"] is not None
    verified = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="certificate.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "certificate_uri": encoded.output["certificate_uri"],
                "checker_id": encoded.output["checker_id"],
            },
        )
    )

    assert verified.execution.status is ExecutionStatus.COMPLETED
    assert verified.output["conclusion"] == "TRUE"
    assert verified.output["assurance"]["verification"] == "VERIFIED"
    assert verified.output["verification_record_uri"] is not None
