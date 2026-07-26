from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.polynomials import (
    PolynomialCollisionOutput,
    PolynomialCollisionPayload,
    PolynomialCollisionRequest,
    PolynomialEvaluationRequest,
    PolynomialJacobianRequest,
    PolynomialMapEvaluation,
    RationalPolynomialMap,
)


def _rational(value: int = 0) -> dict[str, str]:
    return {"num": str(value), "den": "1"}


def _identity_map(dimension: int = 1) -> dict[str, object]:
    return {
        "map_schema_version": "1",
        "domain": "QQ",
        "variables": [f"x{index}" for index in range(dimension)],
        "coordinates": [
            {
                "terms": [
                    {
                        "coefficient": _rational(1),
                        "exponents": [
                            int(coordinate == exponent) for exponent in range(dimension)
                        ],
                    }
                ]
            }
            for coordinate in range(dimension)
        ],
    }


def test_evaluation_request_enforces_map_point_dimension() -> None:
    with pytest.raises(ValidationError, match="point dimension"):
        PolynomialEvaluationRequest.model_validate(
            {"map": _identity_map(), "point": [_rational(), _rational()]}
        )


def test_evaluation_artifact_enforces_point_image_dimension() -> None:
    with pytest.raises(ValidationError, match="point and image dimensions"):
        PolynomialMapEvaluation.model_validate(
            {
                "map_uri": "artifact://sha256/" + "a" * 64,
                "point": {"values": [_rational()]},
                "image": [_rational(), _rational()],
                "backend": "sympy",
                "backend_version": "1.14.0",
            }
        )


def test_collision_payload_enforces_all_dimensions() -> None:
    with pytest.raises(ValidationError, match="dimensions must agree"):
        PolynomialCollisionPayload.model_validate(
            {
                "first_point": [_rational()],
                "second_point": [_rational(), _rational()],
                "image": [_rational()],
            }
        )


def test_collision_request_requires_two_distinct_evaluation_artifacts() -> None:
    artifact_uri = "artifact://sha256/" + "a" * 64

    with pytest.raises(ValidationError, match="distinct evaluation artifacts"):
        PolynomialCollisionRequest.model_validate(
            {
                "first_evaluation_uri": artifact_uri,
                "second_evaluation_uri": artifact_uri,
            }
        )


def test_collision_output_enforces_distinct_points_and_equal_images() -> None:
    artifact_uri = "artifact://sha256/" + "a" * 64
    second_artifact_uri = "artifact://sha256/" + "c" * 64
    checker_id = "checker://sha256/" + "b" * 64

    with pytest.raises(ValidationError, match="collision status"):
        PolynomialCollisionOutput.model_validate(
            {
                "claim_uri": artifact_uri,
                "candidate_uri": artifact_uri,
                "first_evaluation_uri": artifact_uri,
                "second_evaluation_uri": second_artifact_uri,
                "first_point": [_rational(0)],
                "second_point": [_rational(0)],
                "first_image": [_rational(1)],
                "second_image": [_rational(1)],
                "candidate_collision": True,
                "witness_uri": artifact_uri,
                "checker_id": checker_id,
                "certificate_available": True,
            }
        )


def test_jacobian_request_rejects_excessive_symbolic_expansion() -> None:
    dimension = 4
    exponents = [[degree, 1, 1, 1] for degree in range(32, 12, -1)]
    polynomial = {
        "terms": [
            {"coefficient": _rational(1), "exponents": monomial}
            for monomial in exponents
        ]
    }
    polynomial_map = {
        "map_schema_version": "1",
        "domain": "QQ",
        "variables": ["w", "x", "y", "z"],
        "coordinates": [polynomial] * dimension,
    }

    with pytest.raises(ValidationError, match="operation budget"):
        PolynomialJacobianRequest.model_validate({"map": polynomial_map})


def test_source_map_rejects_exponents_reserved_for_derived_artifacts() -> None:
    polynomial_map = _identity_map()
    polynomial_map["coordinates"][0]["terms"][0]["exponents"] = [33]

    with pytest.raises(ValidationError, match="source polynomial exponents"):
        RationalPolynomialMap.model_validate(polynomial_map)
