from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.linear import (
    LinearRationalSolutionFindRequest,
    LinearRationalSolutionVerificationOutput,
    LinearRationalSystem,
)


def _q(num: int, den: int = 1) -> dict[str, str]:
    return {"num": str(num), "den": str(den)}


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
    with pytest.raises(ValidationError, match="256 decimal digits"):
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
