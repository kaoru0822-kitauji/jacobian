from __future__ import annotations

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityObligationStatus,
    CapabilityRelationshipStatus,
    CapabilityRequest,
)
from jacobian.kernel import JacobianKernel

pytestmark = pytest.mark.usefixtures("initialized_kernel_store")


def _request(mode: CapabilityMode, *, missing_last: bool = False) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id="case.partition.finite",
        mode=mode,
        input={
            "universe": ["0", "1", "2", "3", "4", "5"],
            "cases": [
                {"case_id": "even", "members": ["0", "2", "4"]},
                {
                    "case_id": "odd",
                    "members": ["1", "3"] if missing_last else ["1", "3", "5"],
                },
            ],
            "require_disjoint": True,
        },
    )


def test_finite_partition_explore_keeps_coverage_obligation_open(tmp_path) -> None:
    kernel = JacobianKernel(tmp_path)

    result = kernel.capabilities.invoke(_request(CapabilityMode.EXPLORE))

    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.output["missing"] == []
    assert result.output["verification_record_uri"] is None
    assert result.relationships[0].status is CapabilityRelationshipStatus.PROPOSED
    assert result.obligations[0].status is CapabilityObligationStatus.OPEN


def test_finite_partition_verify_replays_and_discharges_obligation(tmp_path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(_request(CapabilityMode.VERIFY))

    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert result.assurance.verification_record_uri is not None
    assert result.completeness.verification_record_uri == (
        result.assurance.verification_record_uri
    )
    assert result.relationships[0].status is CapabilityRelationshipStatus.VERIFIED
    assert result.obligations[0].status is CapabilityObligationStatus.DISCHARGED


def test_finite_partition_verify_fails_closed_on_incomplete_cases(tmp_path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        _request(CapabilityMode.VERIFY, missing_last=True)
    )

    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.output["missing"] == ["5"]
    assert result.output["verification_record_uri"] is None
    assert result.obligations[0].status is CapabilityObligationStatus.OPEN


def test_finite_partition_duplicate_case_ids_cannot_report_complete(tmp_path) -> None:
    kernel = JacobianKernel(tmp_path)
    request = _request(CapabilityMode.EXPLORE)
    request.input["cases"][1]["case_id"] = "even"

    result = kernel.capabilities.invoke(request)

    assert result.output["duplicate_case_ids"] == ["even"]
    assert result.completeness.status.value == "PARTIAL"
