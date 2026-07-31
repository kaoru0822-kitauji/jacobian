from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.plugin_inputs import (
    ErdosStrausCapabilityRequest,
    GraphPathCapabilityRequest,
    GraphPathReductionRequest,
    GraphShrinkRequest,
    MatrixCapabilityRequest,
    MatrixReductionRequest,
    MatrixTransformRequest,
)


def _matrix_candidate() -> dict[str, object]:
    return {"rows": 1, "cols": 1, "entries": [["1"]]}


def test_plugin_contracts_reject_non_object_nested_payloads() -> None:
    with pytest.raises(ValidationError):
        GraphPathReductionRequest.model_validate(
            {
                "target": "a",
                "claim": {"predicate": "is_bipartite"},
            }
        )
    with pytest.raises(ValidationError):
        MatrixReductionRequest.model_validate(
            {
                "target": _matrix_candidate(),
                "claim": "is_nonsingular",
            }
        )


def test_plugin_contracts_reject_scalar_collections_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        GraphShrinkRequest.model_validate(
            {
                "target": {"vertices": ["a"], "edges": []},
                "reducers": "delete_vertex",
                "objectives": [],
            }
        )
    with pytest.raises(ValidationError):
        MatrixReductionRequest.model_validate(
            {
                "target": _matrix_candidate(),
                "claim": {"predicate": "is_nonsingular"},
                "reducers": [],
                "objectives": [],
                "unexpected": True,
            }
        )


def test_plugin_contracts_accept_known_worker_metadata_without_opening_the_boundary() -> (
    None
):
    request = GraphPathCapabilityRequest.model_validate(
        {
            "request_version": "1",
            "profile": "FAST",
            "seed": 0,
            "bindings": {"claim_digest": "sha256:" + "a" * 64},
            "claim": {"predicate": "is_bipartite"},
            "candidate": {
                "vertices": ["a", "b"],
                "arcs": [["a", "b"]],
            },
        }
    )
    assert request.request_version == "1"
    assert request.profile == "FAST"
    assert request.seed == 0

    with pytest.raises(ValidationError):
        MatrixTransformRequest.model_validate(
            {
                "request_version": "1",
                "source": _matrix_candidate(),
                "unexpected": True,
            }
        )


def test_erdos_straus_contract_enforces_range_and_role_domain() -> None:
    with pytest.raises(ValidationError):
        ErdosStrausCapabilityRequest.model_validate(
            {
                "claim": {
                    "predicate": "erdos_straus_range",
                    "lower_bound": 100,
                    "upper_bound": 2,
                },
                "candidate": {"lower_bound": 100, "upper_bound": 2},
            }
        )


def test_nested_matrix_scope_is_typed_and_bounded() -> None:
    with pytest.raises(ValidationError):
        MatrixCapabilityRequest.model_validate(
            {
                "claim": {
                    "predicate": "maximize_absolute_determinant",
                    "scope": {
                        "rows": 2,
                        "cols": 3,
                        "entries": [-1, 1],
                        "unexpected": True,
                    },
                }
            }
        )
    with pytest.raises(ValidationError):
        MatrixCapabilityRequest.model_validate(
            {
                "claim": {
                    "predicate": "maximize_absolute_determinant",
                    "scope": {"rows": 2, "cols": 3, "entries": [-1, 1]},
                }
            }
        )
    with pytest.raises(ValidationError):
        ErdosStrausCapabilityRequest.model_validate(
            {
                "claim": {
                    "predicate": "erdos_straus_range",
                    "lower_bound": 2,
                    "upper_bound": 3,
                },
                "candidate": {"lower_bound": 2, "upper_bound": 3},
                "witness_role": "unsupported",
            }
        )
