from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.graph_shrinking import (
    GraphCounterexampleShrinkRequest,
    GraphLocalMinimalityScope,
    GraphReductionAttempt,
)

_ARTIFACT_URI = "artifact://sha256/" + "1" * 64
_CHECKER_URI = "checker://sha256/" + "2" * 64


@pytest.mark.contract
def test_graph_shrink_request_requires_a_registered_checker_and_reducer() -> None:
    with pytest.raises(ValidationError):
        GraphCounterexampleShrinkRequest(
            graph_uri=_ARTIFACT_URI,
            property_id="graph.property.non_bipartite",
            property_checker_id=_CHECKER_URI,
            reducers=(),
            evaluation_budget=10,
        )


@pytest.mark.contract
def test_graph_shrink_contract_cannot_claim_unchecked_local_minimality() -> None:
    with pytest.raises(ValidationError):
        GraphLocalMinimalityScope(
            requested_reducers=("delete_vertex",),
            untested_vertex_deletions=("v",),
            complete_for_requested_reducers=False,
            one_step_locally_minimal=True,
            basis="invalid fixture",
        )


@pytest.mark.contract
def test_accepted_graph_reduction_requires_verification_record() -> None:
    with pytest.raises(ValidationError):
        GraphReductionAttempt(
            index=0,
            reducer="delete_vertex",
            from_graph_uri=_ARTIFACT_URI,
            proposed_graph_uri="artifact://sha256/" + "3" * 64,
            deleted_vertex="v",
            outcome="ACCEPTED_VERIFIED",
            detail="invalid fixture",
        )
