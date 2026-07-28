from __future__ import annotations

import subprocess
from copy import deepcopy
from typing import Any

import pytest

import jacobian_checkers.sat
from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityInstallTier,
    CapabilityMode,
    CapabilityProviderAvailability,
    CapabilityProviderDigestKind,
    CapabilityProviderRuntime,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.contracts.sat import SatResourceBudget
from jacobian.contracts.verification import VerificationRecord
from jacobian.kernel import JacobianKernel
from jacobian.verification import CheckerExecutionError


def _producer() -> CapabilityProviderRuntime:
    return CapabilityProviderRuntime(
        provider="cadical",
        availability=CapabilityProviderAvailability.AVAILABLE,
        version="2.1.3",
        digest="sha256:" + "d" * 64,
        digest_kind=CapabilityProviderDigestKind.EXECUTABLE,
        platform="linux-x86_64",
        install_tier=CapabilityInstallTier.T2,
        license_id="MIT",
    )


def _assignment(
    kernel: JacobianKernel,
    *,
    values: tuple[bool, bool],
) -> tuple[str, str]:
    cnf = kernel.sat.put_cnf(
        variable_names=("a", "b"),
        clauses=((-1, 2), (1, 2)),
    )
    assignment = kernel.sat.put_assignment(
        cnf_uri=cnf.artifact_uri,
        values=values,
        producer=_producer(),
        resource_budget=SatResourceBudget(wall_seconds=30),
    )
    return cnf.artifact_uri, assignment.artifact_uri


def _verify(kernel: JacobianKernel, assignment_uri: str):
    return kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="sat.model.verify",
            mode=CapabilityMode.VERIFY,
            input={"assignment_uri": assignment_uri},
        )
    )


@pytest.mark.subprocess
def test_sat_assignment_is_verified_by_an_authorized_clean_process(
    kernel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cnf_uri, assignment_uri = _assignment(kernel, values=(False, True))

    monkeypatch.setattr(
        jacobian_checkers.sat,
        "check_assignment",
        lambda _request: {
            "accepted": False,
            "conclusion": "UNKNOWN",
            "arithmetic": "SYMBOLIC",
            "method": "DIRECT_WITNESS",
            "coverage": "NOT_APPLICABLE",
            "detail": "parent-process monkeypatch",
        },
    )
    result = _verify(kernel, assignment_uri)

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert result.output["status"] == "VERIFIED_SATISFYING"
    assert result.output["conclusion"] == "TRUE"
    assert result.output["cnf_uri"] == cnf_uri
    assert result.output["assignment_uri"] == assignment_uri
    record_uri = result.assurance.verification_record_uri
    assert record_uri is not None
    record_artifact = kernel.store.get(record_uri)
    record = VerificationRecord.model_validate(record_artifact.payload)
    assert record.checker_id == kernel.sat_assignment_checker.checker_id
    assert record.evidence_uri == result.output["witness_uri"]
    assert set(record_artifact.manifest.parents) == {
        cnf_uri,
        assignment_uri,
        result.output["witness_uri"],
    }


@pytest.mark.subprocess
def test_unsatisfying_assignment_is_rejected_without_an_opposite_conclusion(
    kernel,
) -> None:
    _cnf_uri, assignment_uri = _assignment(kernel, values=(False, False))

    result = _verify(kernel, assignment_uri)

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.output["status"] == "REJECTED"
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["verification_record_uri"] is None
    assert result.assurance.verification_record_uri is None


def test_sat_assignment_verify_requires_operator_authorized_checker(
    kernel,
) -> None:

    assert kernel.sat_assignment_checker.checker_id is None
    assert "sat.model.verify" not in {
        descriptor.capability_id
        for descriptor in kernel.capabilities.catalog().capabilities
    }


def test_misbound_assignment_artifact_fails_before_checker_dispatch(
    kernel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cnf_uri, assignment_uri = _assignment(kernel, values=(False, True))
    second = kernel.sat.put_cnf(variable_names=("a", "b"), clauses=((1,),))
    stored = kernel.store.get(assignment_uri)
    payload = deepcopy(stored.payload)
    payload["cnf"]["cnf_artifact_uri"] = second.artifact_uri
    forged = kernel.store.put(
        schema_uri=stored.manifest.schema_uri,
        semantics_uri=stored.manifest.semantics_uri,
        payload=payload,
        parents=(cnf_uri,),
        summary="forged SAT assignment binding",
    )
    called = False

    def unexpected_checker(**_kwargs: Any):
        nonlocal called
        called = True
        raise AssertionError("checker must not receive malformed source bindings")

    monkeypatch.setattr(kernel.verification, "_run_checker", unexpected_checker)
    result = _verify(kernel, forged.artifact_uri)

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.assurance.level is not CapabilityAssuranceLevel.VERIFIED
    assert called is False


def test_checker_timeout_cannot_create_a_sat_conclusion(
    kernel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _cnf_uri, assignment_uri = _assignment(kernel, values=(False, True))

    def timeout(**_kwargs: Any):
        raise subprocess.TimeoutExpired(cmd=("sat-assignment-checker",), timeout=1)

    monkeypatch.setattr(kernel.verification, "_run_checker", timeout)
    result = _verify(kernel, assignment_uri)

    assert result.execution.status is ExecutionStatus.TIMEOUT
    assert result.assurance.level is not CapabilityAssuranceLevel.VERIFIED
    assert result.output["status"] == "TIMEOUT"
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.assurance.verification_record_uri is None


def test_checker_error_cannot_create_a_sat_conclusion(
    kernel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _cnf_uri, assignment_uri = _assignment(kernel, values=(False, True))

    def fail(**_kwargs: Any):
        raise CheckerExecutionError("deliberate checker failure")

    monkeypatch.setattr(kernel.verification, "_run_checker", fail)
    result = _verify(kernel, assignment_uri)

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.assurance.level is not CapabilityAssuranceLevel.VERIFIED
    assert result.output["status"] == "ERROR"
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.assurance.verification_record_uri is None
