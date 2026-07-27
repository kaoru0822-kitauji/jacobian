from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.contracts.results import Conclusion, ExecutionStatus
from jacobian.kernel import JacobianKernel
from jacobian_checkers.polynomial_maps import check_map_inverse


def _term(coefficient: int, exponents: list[int]) -> dict[str, Any]:
    return {
        "coefficient": {"num": str(coefficient), "den": "1"},
        "exponents": exponents,
    }


def _triangular_maps() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        {
            "map_schema_version": "1",
            "domain": "QQ",
            "variables": ["x", "y"],
            "coordinates": [
                {"terms": [_term(1, [1, 0]), _term(1, [0, 2])]},
                {"terms": [_term(1, [0, 1])]},
            ],
        },
        {
            "map_schema_version": "1",
            "domain": "QQ",
            "variables": ["u", "v"],
            "coordinates": [
                {"terms": [_term(1, [1, 0]), _term(-1, [0, 2])]},
                {"terms": [_term(1, [0, 1])]},
            ],
        },
    )


def _request(forward: dict[str, Any], inverse: dict[str, Any]) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id="polynomial.map.inverse.verify",
        mode=CapabilityMode.VERIFY,
        input={
            "forward_map": forward,
            "inverse_map": inverse,
            "source_variables": ["x", "y"],
            "target_variables": ["u", "v"],
        },
    )


def _checker_request(kernel: JacobianKernel, output: dict[str, Any]) -> dict[str, Any]:
    def artifact(uri: str) -> dict[str, Any]:
        stored = kernel.store.get(uri)
        return {"artifact_uri": uri, "payload": deepcopy(stored.payload)}

    certificate = artifact(output["certificate_uri"])
    return {
        "request_version": "1",
        "claim": artifact(output["claim_uri"]),
        "candidate": artifact(output["residuals_uri"]),
        "scope": artifact(output["forward_map_uri"]),
        "certificate": certificate,
        "supporting_artifacts": [
            artifact(uri)
            for uri in dict.fromkeys(
                (
                    output["inverse_map_uri"],
                    *output["inverse_after_forward_checker_records"],
                    *output["forward_after_inverse_checker_records"],
                )
            )
        ],
        "expected_bindings": deepcopy(certificate["payload"]["bindings"]),
    }


@pytest.mark.integration
def test_two_sided_triangular_inverse_is_verified(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    forward, inverse = _triangular_maps()

    result = kernel.capabilities.invoke(_request(forward, inverse))

    assert result.output["inverse_verified"] is True
    assert result.output["conclusion"] == Conclusion.TRUE.value
    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert result.output["verification_record_uri"] is not None
    assert len(result.output["inverse_after_forward_checker_records"]) == 2
    assert len(result.output["forward_after_inverse_checker_records"]) == 2
    residuals = kernel.store.get(result.output["residuals_uri"]).payload
    assert residuals["domain"] == "QQ"
    assert residuals["source_variables"] == ["x", "y"]
    assert residuals["target_variables"] == ["u", "v"]
    assert residuals["inverse_after_forward"] == [{"terms": []}, {"terms": []}]
    assert residuals["forward_after_inverse"] == [{"terms": []}, {"terms": []}]


@pytest.mark.integration
def test_overlapping_variable_names_use_simultaneous_composition(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    forward = {
        "map_schema_version": "1",
        "domain": "QQ",
        "variables": ["x", "y"],
        "coordinates": [
            {"terms": [_term(1, [0, 1])]},
            {"terms": [_term(1, [1, 0]), _term(1, [0, 0])]},
        ],
    }
    inverse = {
        "map_schema_version": "1",
        "domain": "QQ",
        "variables": ["x", "y"],
        "coordinates": [
            {"terms": [_term(1, [0, 1]), _term(-1, [0, 0])]},
            {"terms": [_term(1, [1, 0])]},
        ],
    }

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.map.inverse.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "forward_map": forward,
                "inverse_map": inverse,
                "source_variables": ["x", "y"],
                "target_variables": ["x", "y"],
            },
        )
    )

    assert result.output["inverse_verified"] is True
    assert result.output["conclusion"] == Conclusion.TRUE.value
    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED


@pytest.mark.integration
def test_unrepresentable_composition_is_rejected_before_artifacts(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    high_degree = {
        "map_schema_version": "1",
        "domain": "QQ",
        "variables": ["x"],
        "coordinates": [{"terms": [_term(1, [32])]}],
    }
    request = CapabilityRequest(
        capability_id="polynomial.map.inverse.verify",
        mode=CapabilityMode.VERIFY,
        input={
            "forward_map": high_degree,
            "inverse_map": deepcopy(high_degree),
            "source_variables": ["x"],
            "target_variables": ["x"],
        },
    )

    result = kernel.capabilities.invoke(request)

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.output["error"]["code"] == "INVALID_POLYNOMIAL_MAP_INVERSE_REQUEST"
    assert result.artifact_uris == ()


@pytest.mark.integration
def test_perturbed_inverse_coefficient_is_verified_false(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    forward, inverse = _triangular_maps()
    inverse["coordinates"][0]["terms"][1]["coefficient"]["num"] = "-2"

    result = kernel.capabilities.invoke(_request(forward, inverse))

    assert result.output["inverse_verified"] is False
    assert result.output["conclusion"] == Conclusion.FALSE.value
    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED
    residuals = kernel.store.get(result.output["residuals_uri"]).payload
    assert any(item["terms"] for item in residuals["inverse_after_forward"])
    assert any(item["terms"] for item in residuals["forward_after_inverse"])


@pytest.mark.integration
def test_checker_rejects_residual_coefficient_tampering(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    forward, inverse = _triangular_maps()
    result = kernel.capabilities.invoke(_request(forward, inverse))
    checker_request = _checker_request(kernel, result.output)
    checker_request["candidate"]["payload"]["inverse_after_forward"][0] = {
        "terms": [_term(1, [0, 0])]
    }

    decision = check_map_inverse(checker_request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == Conclusion.UNKNOWN.value


@pytest.mark.integration
@pytest.mark.parametrize(
    ("zero_direction", "nonzero_direction"),
    (
        ("inverse_after_forward", "forward_after_inverse"),
        ("forward_after_inverse", "inverse_after_forward"),
    ),
)
def test_one_declared_identity_direction_never_verifies(
    tmp_path: Path, zero_direction: str, nonzero_direction: str
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    forward, inverse = _triangular_maps()
    result = kernel.capabilities.invoke(_request(forward, inverse))
    checker_request = _checker_request(kernel, result.output)
    residuals = checker_request["candidate"]["payload"]
    residuals[zero_direction] = [{"terms": []}, {"terms": []}]
    residuals[nonzero_direction] = [
        {"terms": [_term(1, [0, 0])]},
        {"terms": []},
    ]

    decision = check_map_inverse(checker_request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == Conclusion.UNKNOWN.value


@pytest.mark.integration
@pytest.mark.parametrize("tamper", ("domain", "source_order", "target_order"))
def test_checker_rejects_domain_and_order_substitution(
    tmp_path: Path, tamper: str
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    forward, inverse = _triangular_maps()
    result = kernel.capabilities.invoke(_request(forward, inverse))
    checker_request = _checker_request(kernel, result.output)
    if tamper == "domain":
        checker_request["scope"]["payload"]["domain"] = "ZZ"
    elif tamper == "source_order":
        checker_request["candidate"]["payload"]["source_variables"] = ["y", "x"]
    else:
        checker_request["candidate"]["payload"]["target_variables"] = ["v", "u"]

    decision = check_map_inverse(checker_request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == Conclusion.UNKNOWN.value


@pytest.mark.integration
@pytest.mark.parametrize("source", ("scope", "inverse"))
def test_checker_rejects_source_map_coefficient_tampering(
    tmp_path: Path, source: str
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    forward, inverse = _triangular_maps()
    result = kernel.capabilities.invoke(_request(forward, inverse))
    checker_request = _checker_request(kernel, result.output)
    artifact = (
        checker_request["scope"]
        if source == "scope"
        else checker_request["supporting_artifacts"][0]
    )
    artifact["payload"]["coordinates"][0]["terms"][0]["coefficient"]["num"] = "2"

    decision = check_map_inverse(checker_request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == Conclusion.UNKNOWN.value


@pytest.mark.integration
@pytest.mark.parametrize(
    "family",
    (
        "inverse_after_forward_checker_records",
        "forward_after_inverse_checker_records",
    ),
)
def test_checker_rejects_incomplete_checker_record_family(
    tmp_path: Path, family: str
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    forward, inverse = _triangular_maps()
    result = kernel.capabilities.invoke(_request(forward, inverse))
    checker_request = _checker_request(kernel, result.output)
    checker_request["candidate"]["payload"][family] = checker_request["candidate"][
        "payload"
    ][family][:-1]
    checker_request["certificate"]["payload"]["payload"][family] = checker_request[
        "certificate"
    ]["payload"]["payload"][family][:-1]

    decision = check_map_inverse(checker_request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == Conclusion.UNKNOWN.value
