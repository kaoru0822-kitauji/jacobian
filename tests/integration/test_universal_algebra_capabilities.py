from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.contracts.results import Conclusion
from jacobian.contracts.universal_algebra import (
    UniversalAlgebraCountermodelSearchRequest,
)
from jacobian.kernel import JacobianKernel

pytestmark = pytest.mark.usefixtures("initialized_kernel_store_with_references")


def _variable(name: str) -> dict[str, object]:
    return {"kind": "VARIABLE", "variable": name, "left": None, "right": None}


def _product(
    left: dict[str, object],
    right: dict[str, object],
) -> dict[str, object]:
    return {"kind": "PRODUCT", "variable": None, "left": left, "right": right}


def _left_projection_problem() -> dict[str, object]:
    x = _variable("x")
    y = _variable("y")
    z = _variable("z")
    return {
        "problem_schema_version": "1",
        "structure": {
            "structure_schema_version": "1",
            "operation": "binary",
            "order": 2,
            "table": [[0, 0], [1, 1]],
        },
        "laws": [
            {
                "law_id": "associative",
                "variables": ["x", "y", "z"],
                "left": _product(_product(x, y), z),
                "right": _product(x, _product(y, z)),
            },
            {
                "law_id": "commutative",
                "variables": ["x", "y"],
                "left": _product(x, y),
                "right": _product(y, x),
            },
        ],
    }


@pytest.mark.integration
def test_countermodel_descriptor_publishes_a_model_valid_invocation_example(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    descriptors = {
        descriptor.capability_id: descriptor
        for descriptor in kernel.capabilities.catalog().capabilities
    }
    descriptor = descriptors["universal_algebra.search.countermodel"]

    assert len(descriptor.invocation_examples) == 1
    example = descriptor.invocation_examples[0]
    assert example.mode is CapabilityMode.EXPLORE
    validated = UniversalAlgebraCountermodelSearchRequest.model_validate(example.input)
    assert validated.order == 2
    assert validated.target_law.law_id == "associative"


@pytest.mark.integration
def test_evaluate_laws_returns_exact_truth_and_counterexample(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="universal_algebra.evaluate_laws",
            input={"problem": _left_projection_problem()},
        )
    )

    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    records = {record["law_id"]: record for record in result.output["records"]}
    assert records["associative"] == {
        "law_id": "associative",
        "holds": True,
        "coverage": "EXHAUSTIVE",
        "checked_valuations": 8,
        "counterexample": None,
    }
    assert records["commutative"] == {
        "law_id": "commutative",
        "holds": False,
        "coverage": "COUNTEREXAMPLE_FOUND",
        "checked_valuations": 2,
        "counterexample": {
            "assignment": [
                {"variable": "x", "value": 0},
                {"variable": "y", "value": 1},
            ],
            "left_value": 0,
            "right_value": 1,
        },
    }
    assert result.output["certificate_uri"] in result.artifact_uris
    assert result.output["checker_id"] == (
        kernel.universal_algebra.evaluation_checker_id
    )
    assert result.output["verification_handoff"] == {
        "capability_id": "certificate.verify",
        "mode": "VERIFY",
        "payload": {
            "certificate_uri": result.output["certificate_uri"],
            "checker_id": result.output["checker_id"],
            "timeout_seconds": 150,
        },
    }
    assert "conclusion" not in result.output

    handoff = result.output["verification_handoff"]
    verified = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id=handoff["capability_id"],
            mode=CapabilityMode(handoff["mode"]),
            input=handoff["payload"],
        )
    )

    assert verified.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert verified.output["conclusion"] == Conclusion.TRUE.value
    assert verified.output["verification_record_uri"]


@pytest.mark.integration
def test_complete_request_validation_precedes_artifact_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path)
    problem = _left_projection_problem()
    problem["structure"]["table"] = [[0, 0]]
    artifact_put_calls = 0
    original_put = kernel.artifacts.put

    def recording_put(*args: Any, **kwargs: Any) -> Any:
        nonlocal artifact_put_calls
        artifact_put_calls += 1
        return original_put(*args, **kwargs)

    monkeypatch.setattr(kernel.artifacts, "put", recording_put)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="universal_algebra.evaluate_laws",
            input={"problem": problem},
        )
    )

    assert result.execution.status.value == "ERROR"
    assert result.diagnostics[0].code == "INVALID_FINITE_MAGMA_LAW_REQUEST"
    assert artifact_put_calls == 0


@pytest.mark.integration
def test_countermodel_search_composes_with_independent_law_replay(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    laws = _left_projection_problem()["laws"]

    search = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="universal_algebra.search.countermodel",
            input={
                "order": 2,
                "source_laws": [laws[0]],
                "target_law": laws[1],
            },
        )
    )

    assert search.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert search.output["status"] == "WITNESS_FOUND"
    assert search.output["verification"] == "UNVERIFIED"
    assert search.output["target_record"]["holds"] is False
    assert all(record["holds"] for record in search.output["source_records"])

    evaluation = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="universal_algebra.evaluate_laws",
            input={
                "problem": {
                    "problem_schema_version": "1",
                    "structure": search.output["structure"],
                    "laws": laws,
                }
            },
        )
    )
    verified = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="certificate.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "certificate_uri": evaluation.output["certificate_uri"],
                "checker_id": evaluation.output["checker_id"],
            },
        )
    )

    assert verified.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert verified.output["conclusion"] == Conclusion.TRUE.value


@pytest.mark.integration
def test_countermodel_search_reports_fixed_order_no_witness_without_conclusion(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    laws = _left_projection_problem()["laws"]

    search = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="universal_algebra.search.countermodel",
            input={
                "order": 1,
                "source_laws": [laws[0]],
                "target_law": laws[1],
            },
        )
    )

    assert search.execution.status.value == "COMPLETED"
    assert search.output["status"] == "NO_WITNESS_FOUND"
    assert search.output["structure"] is None
    assert search.scope.parameters["order"] == 1
    assert "conclusion" not in search.output


@pytest.mark.integration
def test_countermodel_request_validation_precedes_artifact_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path)
    laws = _left_projection_problem()["laws"]
    duplicate_target = dict(laws[1])
    duplicate_target["law_id"] = laws[0]["law_id"]
    artifact_put_calls = 0
    original_put = kernel.artifacts.put

    def recording_put(*args: Any, **kwargs: Any) -> Any:
        nonlocal artifact_put_calls
        artifact_put_calls += 1
        return original_put(*args, **kwargs)

    monkeypatch.setattr(kernel.artifacts, "put", recording_put)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="universal_algebra.search.countermodel",
            input={
                "order": 2,
                "source_laws": [laws[0]],
                "target_law": duplicate_target,
            },
        )
    )

    assert result.execution.status.value == "ERROR"
    assert result.diagnostics[0].code == "INVALID_FINITE_MAGMA_COUNTERMODEL_REQUEST"
    assert artifact_put_calls == 0


@pytest.mark.integration
def test_finite_magma_table_enumeration_is_exact_and_canonical(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="finite_magma.table.enumerate",
            input={"order": 2},
        )
    )

    assert result.output["enumerated_count"] == 16
    assert result.output["total_count"] == 16
    assert result.output["ordering"] == "LEXICOGRAPHIC_ROW_MAJOR"
    assert result.output["completeness"] == "COMPLETE"
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE
    table_payloads = [
        kernel.store.get(uri).payload for uri in result.output["table_uris"]
    ]
    assert table_payloads[0]["table"] == [[0, 0], [0, 0]]
    assert table_payloads[-1]["table"] == [[1, 1], [1, 1]]
    assert len({str(payload["table"]) for payload in table_payloads}) == 16
    enumeration = kernel.store.get(result.output["enumeration_uri"])
    assert enumeration.payload["table_uris"] == result.output["table_uris"]
    assert set(enumeration.manifest.parents) == set(result.output["table_uris"])


@pytest.mark.integration
def test_finite_magma_table_enumeration_handles_order_one(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="finite_magma.table.enumerate",
            input={"order": 1},
        )
    )

    assert result.output["enumerated_count"] == 1
    table = kernel.store.get(result.output["table_uris"][0])
    assert table.payload["table"] == [[0]]


@pytest.mark.integration
def test_finite_magma_table_enumeration_rejects_unsupported_order_before_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
        CapabilityRequest(
            capability_id="finite_magma.table.enumerate",
            input={"order": 3},
        )
    )

    assert result.execution.status.value == "ERROR"
    assert result.diagnostics[0].code == "INVALID_REQUEST"
    assert artifact_put_calls == 0
