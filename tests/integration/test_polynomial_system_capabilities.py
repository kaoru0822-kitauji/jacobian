from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityRelationshipStatus,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel
from jacobian.verification import CheckerExecutionError

pytestmark = pytest.mark.usefixtures("initialized_kernel_store_with_references")


def _term(coefficient: int, exponent: int) -> dict[str, Any]:
    return {
        "coefficient": {"num": str(coefficient), "den": "1"},
        "exponents": [exponent],
    }


def _input(value: int) -> dict[str, Any]:
    return {
        "system": {
            "system_schema_version": "1",
            "domain": "QQ",
            "variables": ["x"],
            "equations": [{"terms": [_term(1, 2), _term(-4, 0)]}],
            "inequations": [{"terms": [_term(1, 1)]}],
        },
        "assignment": [{"num": str(value), "den": "1"}],
    }


@pytest.mark.integration
def test_solution_capability_verifies_valid_assignment(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.system.solution.verify",
            mode=CapabilityMode.VERIFY,
            input=_input(2),
        )
    )

    assert result.output["satisfies"] is True
    assert result.output["equation_residuals"] == [{"num": "0", "den": "1"}]
    assert result.output["inequation_values"] == [{"num": "2", "den": "1"}]
    assert result.output["residuals_assurance"] == "VERIFIED"
    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert result.relationships[0].relation_id == (
        "polynomial.relation.satisfies-system"
    )
    assert result.relationships[0].status is CapabilityRelationshipStatus.VERIFIED
    assert (
        result.relationships[0].verification_record_uri
        == result.assurance.verification_record_uri
    )
    certificate = kernel.store.get(result.output["certificate_uri"])
    assert (
        certificate.payload["payload"]["equation_residuals"]
        == (result.output["equation_residuals"])
    )
    record = kernel.store.get(result.output["verification_record_uri"])
    assert result.output["certificate_uri"] in record.manifest.parents
    assert record.payload["relationship_source_artifact_uris"] == [
        result.output["assignment_uri"]
    ]
    assert record.payload["relationship_target_artifact_uris"] == [
        result.output["system_uri"]
    ]
    assert record.payload["obligation_uri"] is None


@pytest.mark.integration
def test_solution_capability_verifies_invalid_assignment(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.system.solution.verify",
            mode=CapabilityMode.VERIFY,
            input=_input(1),
        )
    )

    assert result.output["satisfies"] is False
    assert result.output["conclusion"] == "FALSE"
    assert result.output["residuals_assurance"] == "VERIFIED"
    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert result.relationships == ()
    record = kernel.store.get(result.output["verification_record_uri"])
    assert record.payload["relation_id"] is None
    assert record.payload["relationship_source_artifact_uris"] == []
    assert record.payload["relationship_target_artifact_uris"] == []
    assert record.payload["obligation_uri"] is None


@pytest.mark.integration
def test_solution_capability_keeps_checker_failure_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    def fail(**_kwargs: Any):
        raise CheckerExecutionError("deliberate checker failure")

    monkeypatch.setattr(kernel.verification, "_run_checker", fail)
    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.system.solution.verify",
            mode=CapabilityMode.VERIFY,
            input=_input(1),
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.output["satisfies"] is None
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["residuals_assurance"] == "COMPUTED"
    assert result.output["verification_record_uri"] is None
    assert result.assurance.level is not CapabilityAssuranceLevel.VERIFIED
    assert result.relationships == ()


@pytest.mark.integration
def test_solution_capability_rejects_dimension_mismatch_before_artifact_writes(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    connection = sqlite3.connect(kernel.store.db_path)
    try:
        before = connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
    finally:
        connection.close()
    invalid = _input(2)
    invalid["assignment"].append({"num": "3", "den": "1"})

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.system.solution.verify",
            mode=CapabilityMode.VERIFY,
            input=invalid,
        )
    )

    connection = sqlite3.connect(kernel.store.db_path)
    try:
        after = connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
    finally:
        connection.close()
    assert result.execution.status is ExecutionStatus.ERROR
    assert result.diagnostics[0].code == "INVALID_POLYNOMIAL_SYSTEM_SOLUTION_REQUEST"
    assert result.diagnostics[0].stage == "request_validation"
    assert before == after


@pytest.mark.integration
def test_solution_capability_is_only_available_with_checker(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)

    ids = {
        descriptor.capability_id
        for descriptor in kernel.capabilities.catalog().capabilities
    }

    assert "polynomial.system.solution.verify" not in ids
