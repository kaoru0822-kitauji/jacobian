"""Contract tests for the bounded structured logical-claim AST."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.claim_decomposition import (
    LogicalClaimNode,
    LogicalConnective,
    StructuredClaimArtifact,
)


def _atom(node_id: str) -> LogicalClaimNode:
    return LogicalClaimNode(
        node_id=node_id,
        connective=LogicalConnective.ATOM,
        atom={"symbol": node_id},
    )


def test_nested_grouping_and_duplicate_occurrences_are_valid() -> None:
    nested = LogicalClaimNode(
        node_id="nested",
        connective=LogicalConnective.CONJUNCTION,
        children=(_atom("b"), _atom("c")),
    )
    claim = StructuredClaimArtifact(
        root=LogicalClaimNode(
            node_id="root",
            connective=LogicalConnective.CONJUNCTION,
            children=(_atom("a"), nested),
        )
    )
    assert claim.root.children[1] == nested


@pytest.mark.parametrize(
    "payload",
    [
        {"node_id": "bad", "connective": "CONJUNCTION", "children": []},
        {"node_id": "bad", "connective": "IMPLICATION", "children": []},
        {"node_id": "bad", "connective": "ATOM"},
        {
            "node_id": "bad",
            "connective": "ATOM",
            "atom": {"symbol": "A"},
            "unknown": True,
        },
        {"node_id": "bad", "connective": "UNKNOWN"},
    ],
)
def test_malformed_nodes_are_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        LogicalClaimNode.model_validate(payload)


def test_duplicate_node_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="node_id values must be unique"):
        StructuredClaimArtifact(
            root=LogicalClaimNode(
                node_id="root",
                connective=LogicalConnective.CONJUNCTION,
                children=(_atom("same"), _atom("same")),
            )
        )
