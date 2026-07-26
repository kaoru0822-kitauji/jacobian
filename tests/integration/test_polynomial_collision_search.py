from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
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
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(_request(2))

    assert result.output["found"] is True
    assert result.output["grid_point_count"] == 3
    assert result.output["examined_point_count"] == 3
    assert result.output["first_point"] == [{"num": "-1", "den": "1"}]
    assert result.output["second_point"] == [{"num": "1", "den": "1"}]
    assert result.output["common_image"] == [{"num": "1", "den": "1"}]
    assert result.output["witness_uri"] in result.artifact_uris
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED


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
    assert result.output["verification"] == "UNVERIFIED"
