from __future__ import annotations

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.contracts.results import Conclusion

_LEFT = tuple(range(6))
_RIGHT = tuple(range(6, 14))
_MISSING = {
    (0, 6),
    (0, 8),
    (1, 8),
    (1, 11),
    (2, 7),
    (2, 12),
    (3, 6),
    (3, 11),
    (4, 7),
    (4, 13),
    (5, 12),
    (5, 13),
}


def _wowii_200_graph() -> dict[str, object]:
    vertices = [str(vertex) for vertex in _LEFT + _RIGHT]
    edges = sorted(
        sorted((str(left), str(right)))
        for left in _LEFT
        for right in _RIGHT
        if (left, right) not in _MISSING
    )
    return {
        "graph_schema_version": "1",
        "vertices": sorted(vertices),
        "edges": edges,
    }


def test_neighborhood_independence_reproduces_wowii_200_invariant(
    kernel,
) -> None:
    graph = kernel.artifacts.put(
        schema_uri=kernel.graph.graph_schema_uri,
        semantics_uri=kernel.graph.semantics_uri,
        payload=_wowii_200_graph(),
        summary="WOWII Conjecture 200 public counterexample graph",
    )

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.compute.neighborhood_independence",
            input={"graph_uri": graph.artifact_uri},
        )
    )

    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.output["total"] == 72
    assert result.output["average"] == {"num": "36", "den": "7"}
    assert len(result.output["records"]) == 14
    assert all(
        record["independence_number"] == len(record["neighborhood"])
        for record in result.output["records"]
    )
    assert result.output["certificate_uri"] in result.artifact_uris
    assert result.output["checker_id"] == kernel.graph.neighborhood_checker_id
    assert "conclusion" not in result.output

    verified = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="certificate.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "certificate_uri": result.output["certificate_uri"],
                "checker_id": result.output["checker_id"],
            },
        )
    )

    assert verified.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert verified.output["conclusion"] == Conclusion.TRUE.value
    assert verified.output["verification_record_uri"]
