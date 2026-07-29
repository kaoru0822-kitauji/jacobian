from __future__ import annotations

import base64

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.runtime.model import JacobianRuntime

pytestmark = [
    pytest.mark.subprocess,
]


def _verify(runtime: JacobianRuntime, cnf_uri: str, proof: bytes, **extra: object):
    return runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="sat.lrat.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "cnf_uri": cnf_uri,
                "proof_base64": base64.b64encode(proof).decode("ascii"),
                **extra,
            },
        )
    )


def test_rup_lrat_derives_empty_clause_and_binds_artifacts(
    runtime_with_references,
) -> None:
    cnf = runtime_with_references.core.sat.put_cnf(
        variable_names=("x",), clauses=((-1,), (1,))
    )

    result = _verify(runtime_with_references, cnf.artifact_uri, b"3 0 1 2 0\n")

    assert result.output["status"] == "VERIFIED_UNSAT"
    assert result.output["conclusion"] == "TRUE"
    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert result.output["verification_record_uri"] is not None
    proof = runtime_with_references.core.store.get(result.output["proof_uri"])
    assert proof.manifest.parents == (cnf.artifact_uri,)
    assert (
        proof.payload["cnf"]["variable_map_digest"]
        == result.scope.parameters["variable_map_digest"]
    )
    assert (
        proof.payload["cnf"]["dimacs_digest"]
        == result.scope.parameters["dimacs_digest"]
    )


@pytest.mark.parametrize(
    "proof",
    (
        b"3 0 1 0\n",  # no conflict
        b"3 0 1 99 0\n",  # missing hint
        b"3 1 0 1 2 0\n",  # only a nonempty derived clause
        b"3 0 1 2",  # truncated framing
    ),
)
def test_invalid_or_incomplete_lrat_never_proves_sat_or_unsat(
    runtime_with_references, proof
) -> None:
    cnf = runtime_with_references.core.sat.put_cnf(
        variable_names=("x",), clauses=((-1,), (1,))
    )

    result = _verify(runtime_with_references, cnf.artifact_uri, proof)

    assert result.output["status"] == "REJECTED"
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["verification_record_uri"] is None


def test_negative_rat_hint_is_explicitly_unsupported(runtime_with_references) -> None:
    cnf = runtime_with_references.core.sat.put_cnf(
        variable_names=("x",), clauses=((-1,), (1,))
    )

    result = _verify(runtime_with_references, cnf.artifact_uri, b"3 0 -1 2 0\n")

    assert result.output["status"] == "UNSUPPORTED"
    assert result.output["conclusion"] == "UNKNOWN"


def test_timeout_and_cancellation_are_fail_closed(runtime_with_references) -> None:
    cnf = runtime_with_references.core.sat.put_cnf(
        variable_names=("x",), clauses=((-1,), (1,))
    )

    timed_out = _verify(
        runtime_with_references,
        cnf.artifact_uri,
        b"3 0 1 2 0\n",
        limits={"timeout_ms": 0},
    )
    cancelled = _verify(
        runtime_with_references, cnf.artifact_uri, b"3 0 1 2 0\n", cancelled=True
    )

    assert timed_out.output["status"] == "TIMEOUT"
    assert timed_out.output["conclusion"] == "UNKNOWN"
    assert timed_out.execution.status is ExecutionStatus.TIMEOUT
    assert cancelled.output["status"] == "CANCELLED"
    assert cancelled.output["conclusion"] == "UNKNOWN"
    assert cancelled.execution.status is ExecutionStatus.CANCELLED


def test_capability_is_absent_without_operator_authorized_references(
    runtime: JacobianRuntime,
) -> None:
    ids = {
        item.capability_id for item in runtime.core.capabilities.catalog().capabilities
    }
    assert "sat.lrat.verify" not in ids
