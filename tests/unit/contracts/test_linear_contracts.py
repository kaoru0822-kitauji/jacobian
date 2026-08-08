from __future__ import annotations

import pytest
from pydantic import ValidationError
from tests.support.rationals import rational_payload as _q

from jacobian.contracts.linear import (
    LinearRationalInconsistencyArtifact,
    LinearRationalInconsistencyVerificationOutput,
    LinearRationalSolutionFindRequest,
    LinearRationalSolutionVerificationOutput,
    LinearRationalSystem,
)
from jacobian.provider_runtime import known_provider_runtime


def _system() -> dict[str, object]:
    return {
        "variables": ["x", "y"],
        "coefficients": {
            "entries": [
                [_q(2), _q(1)],
                [_q(1), _q(-1)],
            ]
        },
        "rhs": [_q(5), _q(1)],
    }


def test_linear_system_requires_exact_matching_dimensions() -> None:
    system = LinearRationalSystem.model_validate(_system())
    assert system.variables == ("x", "y")
    assert len(system.coefficients.entries) == len(system.rhs) == 2

    malformed = _system()
    malformed["rhs"] = [_q(5)]
    with pytest.raises(ValidationError, match="right-hand side"):
        LinearRationalSystem.model_validate(malformed)

    malformed = _system()
    malformed["variables"] = ["x"]
    with pytest.raises(ValidationError, match="variable"):
        LinearRationalSystem.model_validate(malformed)


def test_linear_find_request_rejects_ambiguous_or_oversized_rationals() -> None:
    noncanonical = _system()
    noncanonical["rhs"] = [{"num": "2", "den": "2"}, _q(1)]
    with pytest.raises(ValidationError, match="reduced"):
        LinearRationalSolutionFindRequest.model_validate(
            {"system": noncanonical, "resource_budget": {"wall_seconds": 5}}
        )

    oversized = _system()
    oversized["rhs"] = [
        {"num": "1" * 257, "den": "1"},
        _q(1),
    ]
    with pytest.raises(ValidationError, match="256-digit bound"):
        LinearRationalSolutionFindRequest.model_validate(
            {"system": oversized, "resource_budget": {"wall_seconds": 5}}
        )


def test_only_verified_solution_output_can_carry_true_and_record() -> None:
    common = {
        "system_uri": "artifact://sha256/" + "1" * 64,
        "solution_uri": "artifact://sha256/" + "2" * 64,
        "witness_uri": "artifact://sha256/" + "3" * 64,
        "checker_id": "checker://sha256/" + "4" * 64,
        "detail": "checked",
    }
    verified = LinearRationalSolutionVerificationOutput.model_validate(
        {
            **common,
            "status": "VERIFIED_SOLUTION",
            "conclusion": "TRUE",
            "verification_record_uri": "artifact://sha256/" + "5" * 64,
        }
    )
    assert verified.conclusion == "TRUE"

    with pytest.raises(ValidationError):
        LinearRationalSolutionVerificationOutput.model_validate(
            {
                **common,
                "status": "REJECTED",
                "conclusion": "TRUE",
                "verification_record_uri": "artifact://sha256/" + "5" * 64,
            }
        )


def test_inconsistency_artifact_requires_normalized_row_witness() -> None:
    binding = {
        "system_artifact_uri": "artifact://sha256/" + "1" * 64,
        "system_object_digest": "sha256:" + "2" * 64,
        "system_payload_digest": "sha256:" + "3" * 64,
        "variable_order_digest": "sha256:" + "4" * 64,
        "row_count": 2,
        "column_count": 2,
    }
    producer = known_provider_runtime("python-flint").model_copy(
        update={"version": "0.9.0"}
    )
    accepted = LinearRationalInconsistencyArtifact.model_validate(
        {
            "system": binding,
            "left_witness": [_q(-2), _q(1)],
            "rhs_pairing": _q(1),
            "producer": producer,
            "resource_budget": {"wall_seconds": 5},
        }
    )
    assert accepted.rhs_pairing.as_fraction() == 1

    with pytest.raises(ValidationError, match="one value per system row"):
        LinearRationalInconsistencyArtifact.model_validate(
            {
                **accepted.model_dump(mode="json"),
                "left_witness": [_q(1)],
            }
        )
    with pytest.raises(ValidationError, match="normalized"):
        LinearRationalInconsistencyArtifact.model_validate(
            {
                **accepted.model_dump(mode="json"),
                "rhs_pairing": _q(2),
            }
        )


def test_only_verified_inconsistency_can_carry_true_and_record() -> None:
    common = {
        "system_uri": "artifact://sha256/" + "1" * 64,
        "certificate_uri": "artifact://sha256/" + "2" * 64,
        "witness_uri": "artifact://sha256/" + "3" * 64,
        "checker_id": "checker://sha256/" + "4" * 64,
        "detail": "checked",
    }
    verified = LinearRationalInconsistencyVerificationOutput.model_validate(
        {
            **common,
            "status": "VERIFIED_INCONSISTENT",
            "conclusion": "TRUE",
            "verification_record_uri": "artifact://sha256/" + "5" * 64,
        }
    )
    assert verified.conclusion == "TRUE"

    with pytest.raises(ValidationError):
        LinearRationalInconsistencyVerificationOutput.model_validate(
            {
                **common,
                "status": "REJECTED",
                "conclusion": "TRUE",
                "verification_record_uri": "artifact://sha256/" + "5" * 64,
            }
        )
