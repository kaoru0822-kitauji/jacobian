from __future__ import annotations

from copy import deepcopy
from typing import Any

from tests.support.rationals import rational_payload as _q

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityRequest,
    CapabilityResult,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.runtime.model import JacobianRuntime


def _qq(entries: list[list[int]]) -> dict[str, object]:
    return {
        "domain": "QQ",
        "entries": [[_q(value) for value in row] for row in entries],
    }


def _square_input() -> dict[str, object]:
    matrix = _qq([[0, 1], [0, 0]])
    return {"left": matrix, "right": matrix}


def _derived_square_input() -> dict[str, Any]:
    return {
        "left": _qq([[0, 1], [0, 0]]),
        "derived_operand": {
            "operand_derivation_version": "1",
            "source": "LEFT",
            "target": "RIGHT",
            "transform": "IDENTITY",
        },
    }


def _compute_square(
    runtime: JacobianRuntime,
) -> CapabilityResult:
    return runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.multiply.compute",
            input=_square_input(),
        )
    )


def test_square_zero_product_is_computed_then_independently_verified(
    authorized_complete_runtime: JacobianRuntime,
) -> None:
    computed = _compute_square(authorized_complete_runtime)

    assert computed.execution.status is ExecutionStatus.COMPLETED
    assert computed.assurance.level is CapabilityAssuranceLevel.COMPUTED

    verified = authorized_complete_runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.multiply.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "input": _square_input(),
                "candidate": computed.output["result"],
            },
        )
    )

    assert verified.execution.status is ExecutionStatus.COMPLETED
    assert verified.output["status"] == "VERIFIED"
    assert verified.output["operation_id"] == "matrix.multiply.compute"
    assert verified.output["verification_record_uri"] is not None
    assert verified.output["verification_record_uri"] in verified.artifact_uris
    assert verified.assurance.level is CapabilityAssuranceLevel.VERIFIED


def test_derived_square_is_bound_and_independently_verified(
    authorized_complete_runtime: JacobianRuntime,
) -> None:
    computed = authorized_complete_runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.multiply.compute",
            input=_derived_square_input(),
        )
    )

    verified = authorized_complete_runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.multiply.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "input": _derived_square_input(),
                "candidate": computed.output["result"],
            },
        )
    )

    assert computed.execution.status is ExecutionStatus.COMPLETED
    assert computed.scope is not None
    assert computed.scope.parameters["right"] is None
    assert verified.execution.status is ExecutionStatus.COMPLETED
    assert verified.output["status"] == "VERIFIED"
    assert verified.output["verification_record_uri"] in verified.artifact_uris


def test_derived_square_verifier_rejects_an_altered_transform(
    authorized_complete_runtime: JacobianRuntime,
) -> None:
    computed = authorized_complete_runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.multiply.compute",
            input=_derived_square_input(),
        )
    )
    altered_input = deepcopy(_derived_square_input())
    altered_input["derived_operand"]["transform"] = "TRANSPOSE"

    rejected = authorized_complete_runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.multiply.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "input": altered_input,
                "candidate": computed.output["result"],
            },
        )
    )

    assert rejected.execution.status is ExecutionStatus.COMPLETED
    assert rejected.output["status"] == "REJECTED"
    assert rejected.output["conclusion"] == "UNKNOWN"
    assert rejected.output["verification_record_uri"] is None


def test_matrix_product_verifier_rejects_a_false_product_without_a_record(
    authorized_complete_runtime: JacobianRuntime,
) -> None:
    computed = _compute_square(authorized_complete_runtime)
    false_candidate = deepcopy(computed.output["result"])
    false_candidate["product"] = _qq([[1, 0], [0, 0]])

    rejected = authorized_complete_runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.multiply.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "input": _square_input(),
                "candidate": false_candidate,
            },
        )
    )

    assert rejected.execution.status is ExecutionStatus.COMPLETED
    assert rejected.output["status"] == "REJECTED"
    assert rejected.output["conclusion"] == "UNKNOWN"
    assert rejected.output["verification_record_uri"] is None
    assert rejected.assurance.level is CapabilityAssuranceLevel.COMPUTED
