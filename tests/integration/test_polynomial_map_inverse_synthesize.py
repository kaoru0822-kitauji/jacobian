"""Acceptance tests for bounded polynomial-map inverse synthesis."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from jacobian.contracts.capabilities import CapabilityMode, CapabilityRequest
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel

pytestmark = pytest.mark.usefixtures("initialized_kernel_store_with_references")


def _term(coefficient: int, exponents: list[int]) -> dict[str, Any]:
    return {
        "coefficient": {"num": str(coefficient), "den": "1"},
        "exponents": exponents,
    }


def _triangular_forward() -> dict[str, Any]:
    return {
        "map_schema_version": "1",
        "domain": "QQ",
        "variables": ["x", "y"],
        "coordinates": [
            {"terms": [_term(1, [1, 0]), _term(1, [0, 2])]},
            {"terms": [_term(1, [0, 1])]},
        ],
    }


def _request(
    *,
    degree: int,
    timeout_ms: int = 10_000,
    max_unknowns: int = 64,
    explicit_support: list[list[list[int]]] | None = None,
) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id="polynomial.map.inverse.candidate_synthesize",
        input={
            "forward_map": _triangular_forward(),
            "source_variables": ["x", "y"],
            "target_variables": ["u", "v"],
            "inverse_degree_bound": degree,
            "support_mode": (
                "EXPLICIT" if explicit_support is not None else "FULL_TOTAL_DEGREE"
            ),
            "explicit_support": explicit_support,
            "solver": "sympy.solve",
            "limits": {
                "timeout_ms": timeout_ms,
                "max_inverse_degree": 4,
                "max_composition_degree": 32,
                "max_unknown_coefficients": max_unknowns,
                "max_coefficient_equations": 512,
                "max_residual_terms": 1024,
            },
        },
    )


@pytest.mark.integration
def test_triangular_automorphism_is_found_and_verified(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    result = kernel.capabilities.invoke(_request(degree=2))

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["status"] == "FOUND"
    assert result.output["candidate_inverse_map"]["coordinates"] == [
        {"terms": [_term(1, [1, 0]), _term(-1, [0, 2])]},
        {"terms": [_term(1, [0, 1])]},
    ]
    assert result.output["verification_output"]["inverse_verified"] is True
    assert result.output["verification_artifact_uri"] is not None
    assert result.output["noninvertibility_proved"] is False
    assert result.output["inverse_after_forward"] == [
        {"terms": []},
        {"terms": []},
    ]
    assert result.output["forward_after_inverse"] == [
        {"terms": []},
        {"terms": []},
    ]


@pytest.mark.integration
def test_degree_below_required_returns_bounded_no_candidate(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    result = kernel.capabilities.invoke(_request(degree=1))

    assert result.output["status"] == "NO_CANDIDATE_WITHIN_ANSATZ"
    assert result.output["candidate_inverse_map"] is None
    assert result.output["noninvertibility_proved"] is False


@pytest.mark.integration
def test_redundant_explicit_ansatz_is_underdetermined(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    identity = {
        "map_schema_version": "1",
        "domain": "QQ",
        "variables": ["x"],
        "coordinates": [{"terms": [_term(1, [1])]}],
    }
    request = CapabilityRequest(
        capability_id="polynomial.map.inverse.candidate_synthesize",
        input={
            "forward_map": identity,
            "source_variables": ["x"],
            "target_variables": ["u"],
            "inverse_degree_bound": 1,
            "support_mode": "EXPLICIT",
            "explicit_support": [[[1], [1]]],
            "solver": "sympy.solve",
            "limits": {
                "timeout_ms": 10_000,
                "max_inverse_degree": 1,
                "max_composition_degree": 8,
                "max_unknown_coefficients": 4,
                "max_coefficient_equations": 16,
                "max_residual_terms": 16,
            },
        },
    )

    result = kernel.capabilities.invoke(request)

    assert result.output["status"] == "UNDERDETERMINED"
    assert result.output["candidate_inverse_map"] is None
    assert "free parameters" in result.output["verification_failure"]


@pytest.mark.integration
def test_zero_timeout_and_unknown_budget_are_explicit(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    timeout = kernel.capabilities.invoke(_request(degree=2, timeout_ms=0))
    exhausted = kernel.capabilities.invoke(_request(degree=2, max_unknowns=1))

    assert timeout.execution.status is ExecutionStatus.TIMEOUT
    assert timeout.output["status"] == "TIMEOUT"
    assert exhausted.output["status"] == "BUDGET_EXHAUSTED"


@pytest.mark.integration
def test_unknown_solver_is_unsupported_without_truth_claim(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    payload = deepcopy(_request(degree=2).input)
    payload["solver"] = "unknown.exact_solver"

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.map.inverse.candidate_synthesize",
            input=payload,
        )
    )

    assert result.output["status"] == "UNSUPPORTED"
    assert result.output["candidate_inverse_map"] is None
    assert result.output["noninvertibility_proved"] is False


@pytest.mark.integration
def test_full_support_and_coefficient_order_are_deterministic(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    first = kernel.capabilities.invoke(_request(degree=2))
    second = kernel.capabilities.invoke(_request(degree=2))

    assert first.output["ansatz"] == second.output["ansatz"]
    assert (
        first.output["coefficient_equations"] == second.output["coefficient_equations"]
    )
    supports = first.output["ansatz"]["coordinate_supports"]
    assert supports[0] == [
        [2, 0],
        [1, 1],
        [1, 0],
        [0, 2],
        [0, 1],
        [0, 0],
    ]
    assert first.output["ansatz"]["coefficient_symbols"][0] == [
        "c_0_0",
        "c_0_1",
        "c_0_2",
        "c_0_3",
        "c_0_4",
        "c_0_5",
    ]


@pytest.mark.integration
@pytest.mark.parametrize(
    "mutation",
    ["variable_order", "coefficient_domain"],
)
def test_ring_mismatches_fail_closed(tmp_path: Path, mutation: str) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    payload = deepcopy(_request(degree=2).input)
    if mutation == "variable_order":
        payload["source_variables"] = ["y", "x"]
    else:
        payload["forward_map"]["domain"] = "RR"

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.map.inverse.candidate_synthesize",
            input=payload,
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.artifact_uris == ()


@pytest.mark.integration
def test_corrupted_found_candidate_does_not_verify(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    synthesized = kernel.capabilities.invoke(_request(degree=2))
    corrupted = deepcopy(synthesized.output["candidate_inverse_map"])
    corrupted["coordinates"][0]["terms"][1]["coefficient"]["num"] = "-2"
    checked = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.map.inverse.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "forward_map": _triangular_forward(),
                "inverse_map": corrupted,
                "source_variables": ["x", "y"],
                "target_variables": ["u", "v"],
            },
        )
    )
    assert checked.output["inverse_verified"] is False
