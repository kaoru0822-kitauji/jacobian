from __future__ import annotations

from tests.support.core_capability_harnesses import FinitePartitionTestServices

from jacobian.contracts.capabilities import CapabilityRequest


def _request(
    *,
    verify: bool = False,
    missing_last: bool = False,
    require_disjoint: bool = True,
) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id=(
            "case.partition.finite.verify" if verify else "case.partition.finite"
        ),
        input={
            "universe": ["0", "1", "2", "3", "4", "5"],
            "cases": [
                {"case_id": "even", "members": ["0", "2", "4"]},
                {
                    "case_id": "odd",
                    "members": ["1", "3"] if missing_last else ["1", "3", "5"],
                },
            ],
            "require_disjoint": require_disjoint,
        },
    )


def test_finite_partition_produces_an_unverified_typed_result(
    unauthorized_finite_partition_services: FinitePartitionTestServices,
) -> None:
    result = unauthorized_finite_partition_services.services.core.capabilities.invoke(
        _request()
    )

    assert result.capability_id == "case.partition.finite"
    assert result.output["missing"] == []
    assert result.output["verification_record_uri"] is None


def test_finite_partition_verify_replays_with_an_authorized_checker(
    finite_partition_services: FinitePartitionTestServices,
) -> None:
    runtime = finite_partition_services.services
    result = runtime.core.capabilities.invoke(_request(verify=True))

    assert result.capability_id == "case.partition.finite.verify"
    assert result.verification_record_uri is not None


def test_finite_partition_contract_preserves_semantic_boundary(
    finite_partition_services: FinitePartitionTestServices,
) -> None:
    runtime = finite_partition_services.services
    producer = next(
        item
        for item in runtime.core.capabilities.catalog().capabilities
        if item.capability_id == "case.partition.finite"
    )

    assert "opaque caller-supplied strings" in producer.description


def test_finite_partition_reports_conditional_disjointness_scope(
    finite_partition_services: FinitePartitionTestServices,
) -> None:
    runtime = finite_partition_services.services
    request = _request(verify=True, require_disjoint=False)
    request.input["cases"][1]["members"].append("0")

    result = runtime.core.capabilities.invoke(request)

    assert result.verification_record_uri is not None
    assert result.output["overlaps"] == ["0"]
    certificate = runtime.core.store.get(result.output["certificate_uri"])
    assert certificate.payload["payload"]["replay"] == (
        "equality-based finite coverage and conditional disjointness"
    )


def test_finite_partition_verify_fails_closed_on_incomplete_cases(
    finite_partition_services: FinitePartitionTestServices,
) -> None:
    runtime = finite_partition_services.services
    result = runtime.core.capabilities.invoke(_request(verify=True, missing_last=True))

    assert result.output["missing"] == ["5"]
    assert result.output["verification_record_uri"] is None


def test_finite_partition_duplicate_case_ids_cannot_report_complete(
    unauthorized_finite_partition_services: FinitePartitionTestServices,
) -> None:
    request = _request()
    request.input["cases"][1]["case_id"] = "even"

    result = unauthorized_finite_partition_services.services.core.capabilities.invoke(
        request
    )

    assert result.output["duplicate_case_ids"] == ["even"]
