from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from sympy import Poly, expand, symbols

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.contracts.evidence import (
    EvidenceBindings,
    WitnessEnvelope,
    WitnessRole,
)
from jacobian.contracts.results import Conclusion, InputStatus, Verification
from jacobian.kernel import JacobianKernel


def _wire_fraction(value: Fraction | int) -> dict[str, str]:
    rational = Fraction(value)
    return {"num": str(rational.numerator), "den": str(rational.denominator)}


def _poly_payload(poly: Poly) -> dict[str, Any]:
    return {
        "terms": [
            {
                "coefficient": _wire_fraction(Fraction(coefficient)),
                "exponents": list(exponents),
            }
            for exponents, coefficient in poly.terms()
        ]
    }


def _jacobian_counterexample_map() -> dict[str, Any]:
    x, y, z = symbols("x y z")
    coordinates = (
        (1 + x * y) ** 3 * z + y**2 * (1 + x * y) * (4 + 3 * x * y),
        y + 3 * x * (1 + x * y) ** 2 * z + 3 * x * y**2 * (4 + 3 * x * y),
        2 * x - 3 * x**2 * y - x**3 * z,
    )
    return {
        "map_schema_version": "1",
        "domain": "QQ",
        "variables": ["x", "y", "z"],
        "coordinates": [
            _poly_payload(Poly(expand(coordinate), x, y, z, domain="QQ"))
            for coordinate in coordinates
        ],
    }


def _point(*values: Fraction | int) -> list[dict[str, str]]:
    return [_wire_fraction(value) for value in values]


@pytest.mark.integration
def test_jacobian_canonically_omits_zero_partial_derivatives(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    x, y = symbols("x y")
    polynomial_map = {
        "map_schema_version": "1",
        "domain": "QQ",
        "variables": ["x", "y"],
        "coordinates": [
            _poly_payload(Poly(x + y**2, x, y, domain="QQ")),
            _poly_payload(Poly(y, x, y, domain="QQ")),
        ],
    }

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.map.compute_jacobian",
            input={"map": polynomial_map},
        )
    )

    assert result.execution.status.value == "COMPLETED"
    assert result.output["matrix"][1][0] == {"terms": []}
    assert result.output["determinant"] == {
        "terms": [
            {
                "coefficient": {"num": "1", "den": "1"},
                "exponents": [0, 0],
            }
        ]
    }


@pytest.mark.integration
def test_jacobian_represents_derived_exponents_above_the_source_limit(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    x, y = symbols("x y")
    polynomial_map = {
        "map_schema_version": "1",
        "domain": "QQ",
        "variables": ["x", "y"],
        "coordinates": [
            _poly_payload(Poly(x**32, x, y, domain="QQ")),
            _poly_payload(Poly(x**32 * y, x, y, domain="QQ")),
        ],
    }

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.map.compute_jacobian",
            input={"map": polynomial_map},
        )
    )

    assert result.execution.status.value == "COMPLETED"
    assert result.output["determinant"] == {
        "terms": [
            {
                "coefficient": {"num": "32", "den": "1"},
                "exponents": [63, 0],
            }
        ]
    }
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


@pytest.mark.integration
def test_polynomial_jacobian_and_collision_reproduce_public_counterexample(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    polynomial_map = _jacobian_counterexample_map()

    jacobian = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.map.compute_jacobian",
            input={"map": polynomial_map},
        )
    )

    assert jacobian.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert jacobian.completeness.status is CapabilityCompletenessStatus.COMPLETE
    assert jacobian.output["determinant"] == {
        "terms": [
            {
                "coefficient": {"num": "-2", "den": "1"},
                "exponents": [0, 0, 0],
            }
        ]
    }
    assert jacobian.output["backend"] == "sympy"
    assert jacobian.output["backend_version"]
    assert jacobian.output["certificate_uri"] in jacobian.artifact_uris
    assert jacobian.output["checker_id"] == kernel.polynomial.jacobian_checker_id
    assert "conclusion" not in jacobian.output

    verified_jacobian = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="certificate.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "certificate_uri": jacobian.output["certificate_uri"],
                "checker_id": jacobian.output["checker_id"],
            },
        )
    )

    assert verified_jacobian.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert verified_jacobian.output["conclusion"] == Conclusion.TRUE.value
    assert verified_jacobian.output["verification_record_uri"]

    collision = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.map.collision_witness",
            input={
                "map": polynomial_map,
                "first_point": _point(0, 0, Fraction(-1, 4)),
                "second_point": _point(1, Fraction(-3, 2), Fraction(13, 2)),
            },
        )
    )

    assert collision.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert collision.output["is_collision"] is True
    assert (
        collision.output["first_image"]
        == collision.output["second_image"]
        == [
            {"num": "-1", "den": "4"},
            {"num": "0", "den": "1"},
            {"num": "0", "den": "1"},
        ]
    )
    assert collision.output["witness_uri"] in collision.artifact_uris
    assert collision.output["checker_id"] == kernel.polynomial.collision_checker_id
    assert "conclusion" not in collision.output

    verified = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="witness.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "claim_uri": collision.output["claim_uri"],
                "candidate_uri": collision.output["candidate_uri"],
                "witness_uri": collision.output["witness_uri"],
                "checker_id": collision.output["checker_id"],
            },
        )
    )

    assert verified.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert verified.output["conclusion"] == Conclusion.FALSE.value
    assert verified.output["assurance"]["verification"] == Verification.VERIFIED.value
    assert verified.output["verification_record_uri"]


@pytest.mark.integration
def test_collision_checker_rejects_a_forged_image(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    collision = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.map.collision_witness",
            input={
                "map": _jacobian_counterexample_map(),
                "first_point": _point(0, 0, Fraction(-1, 4)),
                "second_point": _point(1, Fraction(-3, 2), Fraction(13, 2)),
            },
        )
    )
    claim_uri = collision.output["claim_uri"]
    candidate_uri = collision.output["candidate_uri"]
    witness_uri = collision.output["witness_uri"]
    assert witness_uri is not None
    witness_artifact = kernel.store.get(witness_uri)
    original = WitnessEnvelope.model_validate(witness_artifact.payload)
    forged_payload = deepcopy(original.payload)
    forged_payload["image"][0] = {"num": "0", "den": "1"}
    forged = WitnessEnvelope(
        witness_format=original.witness_format,
        format_version=original.format_version,
        role=WitnessRole.REFUTES_CLAIM,
        bindings=EvidenceBindings.model_validate(
            original.bindings.model_dump(mode="json")
        ),
        payload=forged_payload,
    )
    forged_artifact = kernel.store.put(
        schema_uri=kernel.polynomial.witness_schema_uri,
        semantics_uri=kernel.polynomial.semantics_uri,
        payload=forged.model_dump(mode="json"),
        parents=(claim_uri, candidate_uri),
        summary="forged collision witness",
    )

    rejected = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="witness.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "claim_uri": claim_uri,
                "candidate_uri": candidate_uri,
                "witness_uri": forged_artifact.artifact_uri,
                "checker_id": kernel.polynomial.collision_checker_id,
            },
        )
    )

    assert rejected.output["input"]["status"] == InputStatus.REJECTED.value
    assert rejected.output["conclusion"] == Conclusion.UNKNOWN.value
    assert rejected.assurance.level is CapabilityAssuranceLevel.HEURISTIC
    assert rejected.output["verification_record_uri"] is None


@pytest.mark.integration
def test_noncollision_is_computed_evidence_without_witness_or_conclusion(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    x = symbols("x")
    identity_map = {
        "map_schema_version": "1",
        "domain": "QQ",
        "variables": ["x"],
        "coordinates": [_poly_payload(Poly(x, x, domain="QQ"))],
    }

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.map.collision_witness",
            input={
                "map": identity_map,
                "first_point": _point(0),
                "second_point": _point(1),
            },
        )
    )

    assert result.output["is_collision"] is False
    assert result.output["witness_uri"] is None
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE
    assert "conclusion" not in result.output


@pytest.mark.integration
def test_polynomial_map_evaluation_is_exact_and_materialized(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    polynomial_map = _jacobian_counterexample_map()

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.map.evaluate",
            input={
                "map": polynomial_map,
                "point": _point(-1, Fraction(3, 2), Fraction(13, 2)),
            },
        )
    )

    assert result.output["image"] == [
        {"num": "-1", "den": "4"},
        {"num": "0", "den": "1"},
        {"num": "0", "den": "1"},
    ]
    assert result.output["map_uri"] in result.artifact_uris
    assert result.output["evaluation_uri"] in result.artifact_uris
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE


@pytest.mark.integration
@pytest.mark.parametrize(
    ("capability_id", "payload", "diagnostic_code"),
    [
        (
            "polynomial.map.evaluate",
            {
                "map": {
                    "map_schema_version": "1",
                    "domain": "QQ",
                    "variables": ["x"],
                    "coordinates": [
                        {
                            "terms": [
                                {
                                    "coefficient": {"num": "1", "den": "1"},
                                    "exponents": [1],
                                }
                            ]
                        }
                    ],
                },
                "point": [
                    {"num": "0", "den": "1"},
                    {"num": "1", "den": "1"},
                ],
            },
            "INVALID_POLYNOMIAL_EVALUATION_REQUEST",
        ),
        (
            "polynomial.map.compute_jacobian",
            {
                "map": {
                    "map_schema_version": "1",
                    "domain": "QQ",
                    "variables": ["x", "y"],
                    "coordinates": [{"terms": []}],
                }
            },
            "INVALID_POLYNOMIAL_JACOBIAN_REQUEST",
        ),
        (
            "polynomial.map.collision_witness",
            {
                "map": {
                    "map_schema_version": "1",
                    "domain": "QQ",
                    "variables": ["x"],
                    "coordinates": [
                        {
                            "terms": [
                                {
                                    "coefficient": {"num": "1", "den": "1"},
                                    "exponents": [1],
                                }
                            ]
                        }
                    ],
                },
                "first_point": [
                    {"num": "0", "den": "1"},
                    {"num": "1", "den": "1"},
                ],
                "second_point": [{"num": "0", "den": "1"}],
            },
            "INVALID_POLYNOMIAL_COLLISION_REQUEST",
        ),
    ],
)
def test_complete_request_validation_precedes_artifact_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capability_id: str,
    payload: dict[str, Any],
    diagnostic_code: str,
) -> None:
    kernel = JacobianKernel(tmp_path)
    artifact_put_calls = 0
    original_put = kernel.artifacts.put

    def recording_put(*args: Any, **kwargs: Any) -> Any:
        nonlocal artifact_put_calls
        artifact_put_calls += 1
        return original_put(*args, **kwargs)

    monkeypatch.setattr(kernel.artifacts, "put", recording_put)

    result = kernel.capabilities.invoke(
        CapabilityRequest(capability_id=capability_id, input=payload)
    )

    assert result.execution.status.value == "ERROR"
    assert result.diagnostics[0].code == diagnostic_code
    assert artifact_put_calls == 0
