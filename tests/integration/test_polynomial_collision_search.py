from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityRequest,
)
from jacobian.kernel import JacobianKernel


def _map(exponent: int) -> dict[str, object]:
    return {
        "variables": ["x"],
        "coordinates": [
            {
                "terms": [
                    {
                        "coefficient": {"num": "1", "den": "1"},
                        "exponents": [exponent],
                    }
                ]
            }
        ],
    }


def _request(exponent: int) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id="polynomial.map.collision.search",
        input={
            "map": _map(exponent),
            "max_abs_numerator": 1,
            "max_denominator": 1,
        },
    )


@pytest.mark.integration
def test_collision_search_returns_first_deterministic_candidate(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)

    result = kernel.capabilities.invoke(_request(2))

    assert result.output["found"] is True
    assert result.output["grid_point_count"] == 3
    assert result.output["examined_point_count"] == 3
    assert result.output["first_point"] == [{"num": "-1", "den": "1"}]
    assert result.output["second_point"] == [{"num": "1", "den": "1"}]
    assert result.output["common_image"] == [{"num": "1", "den": "1"}]
    assert result.output["witness_uri"] in result.artifact_uris
    assert result.output["stop_reason"] == "FIRST_COLLISION"
    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED


@pytest.mark.integration
def test_collision_search_reports_partial_grid_after_early_collision(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)

    result = kernel.capabilities.invoke(_request(0))

    assert result.output["found"] is True
    assert result.output["grid_point_count"] == 3
    assert result.output["examined_point_count"] == 2
    assert result.output["first_point"] == [{"num": "-1", "den": "1"}]
    assert result.output["second_point"] == [{"num": "0", "den": "1"}]
    assert result.output["stop_reason"] == "FIRST_COLLISION"
    assert result.completeness.status is CapabilityCompletenessStatus.PARTIAL

    relationships = {
        relationship.relation_id: relationship for relationship in result.relationships
    }
    evaluation_relationship = relationships["polynomial.relation.evaluation-of"]
    assert evaluation_relationship.source_artifact_uris == (result.output["map_uri"],)
    assert len(evaluation_relationship.target_artifact_uris) == 2
    assert set(evaluation_relationship.target_artifact_uris) == {
        result.output["first_evaluation_uri"],
        result.output["second_evaluation_uri"],
    }
    assert relationships[
        "polynomial.relation.collision-derived-from"
    ].source_artifact_uris == (
        result.output["first_evaluation_uri"],
        result.output["second_evaluation_uri"],
    )
    assert relationships[
        "polynomial.relation.collision-refutes-injectivity"
    ].target_artifact_uris == (result.output["claim_uri"],)
    relationship_artifacts = {
        uri
        for relationship in result.relationships
        for uri in (
            *relationship.source_artifact_uris,
            *relationship.target_artifact_uris,
        )
    }
    assert relationship_artifacts <= set(result.artifact_uris)


@pytest.mark.integration
def test_collision_search_reports_exact_completed_not_found_scope(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)

    result = kernel.capabilities.invoke(_request(1))

    assert result.output["found"] is False
    assert result.output["examined_point_count"] == 3
    assert result.output["grid_point_count"] == 3
    assert result.output["witness_uri"] is None
    assert result.output["stop_reason"] == "GRID_EXHAUSTED"
    assert result.output["verification"] == "UNVERIFIED"
    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE
    assert len(result.relationships) == 1
    assert result.relationships[0].relation_id == "polynomial.relation.evaluation-of"
    assert len(result.relationships[0].target_artifact_uris) == 3
    assert set(result.relationships[0].target_artifact_uris) <= set(
        result.artifact_uris
    )


@pytest.mark.integration
def test_collision_search_validates_grid_bound_before_artifact_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path)
    artifact_put_calls = 0
    original_put = kernel.artifacts.put

    def recording_put(*args: Any, **kwargs: Any) -> Any:
        nonlocal artifact_put_calls
        artifact_put_calls += 1
        return original_put(*args, **kwargs)

    monkeypatch.setattr(kernel.artifacts, "put", recording_put)
    variables = ["w", "x", "y", "z"]
    polynomial_map = {
        "variables": variables,
        "coordinates": [
            {
                "terms": [
                    {
                        "coefficient": {"num": "1", "den": "1"},
                        "exponents": [
                            int(variable == coordinate) for variable in variables
                        ],
                    }
                ]
            }
            for coordinate in variables
        ],
    }

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.map.collision.search",
            input={
                "map": polynomial_map,
                "max_abs_numerator": 8,
                "max_denominator": 8,
            },
        )
    )

    assert result.execution.status.value == "ERROR"
    assert result.diagnostics[0].code == "INVALID_POLYNOMIAL_COLLISION_SEARCH_REQUEST"
    assert artifact_put_calls == 0
