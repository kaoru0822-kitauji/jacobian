from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPRODUCTIONS = (
    PROJECT_ROOT / "benchmarks" / "reproduction_cases" / "sat_public_reproductions.json"
)

pytestmark = [
    pytest.mark.external_backend,
    pytest.mark.subprocess,
    pytest.mark.skipif(
        shutil.which("cadical") is None or shutil.which("drat-trim") is None,
        reason="pinned CaDiCaL and DRAT-trim runtimes are not installed",
    ),
]


@pytest.fixture
def kernel(kernel_with_references: JacobianKernel) -> JacobianKernel:
    return kernel_with_references


def _load_cases() -> list[dict[str, Any]]:
    suite = json.loads(REPRODUCTIONS.read_text(encoding="utf-8"))
    assert suite["scored"] is False
    assert suite["purpose"].endswith("never hidden evaluation")
    assert len(suite["attack_coverage"]) >= 4
    agent_case = suite["agent_regressions"][0]
    assert agent_case["case_id"] == "ERDOS-SCHUR-F4-AGENT-001"
    assert agent_case["expected_answer"] == 45
    assert agent_case["route_is_not_prescribed"] is True
    cases = suite["cases"]
    assert isinstance(cases, list)
    return cases


def test_sat_public_reproductions_reach_checker_bound_results(
    kernel,
) -> None:

    for case in _load_cases():
        cnf = kernel.sat.put_cnf(
            variable_names=tuple(case["variable_names"]),
            clauses=tuple(tuple(clause) for clause in case["clauses"]),
        )
        if case["expected_status"] == "SATISFIABLE":
            find_id = "sat.model.find"
            verify_id = "sat.model.verify"
            evidence_field = "assignment_uri"
        else:
            find_id = "sat.unsat_proof.find"
            verify_id = "sat.unsat_proof.verify"
            evidence_field = "proof_uri"

        found = kernel.capabilities.invoke(
            CapabilityRequest(
                capability_id=find_id,
                mode=CapabilityMode.EXPLORE,
                input={
                    "cnf_uri": cnf.artifact_uri,
                    "resource_budget": {"wall_seconds": 5},
                },
            )
        )
        assert found.execution.status is ExecutionStatus.COMPLETED
        assert found.output["conclusion"] == "UNKNOWN"
        evidence_uri = found.output[evidence_field]
        assert evidence_uri is not None
        if case["expected_status"] == "SATISFIABLE":
            assert found.output["assignment"] is not None

        verified = kernel.capabilities.invoke(
            CapabilityRequest(
                capability_id=verify_id,
                mode=CapabilityMode.VERIFY,
                input={evidence_field: evidence_uri},
            )
        )
        assert verified.execution.status is ExecutionStatus.COMPLETED
        assert verified.assurance.level is CapabilityAssuranceLevel.VERIFIED
        assert verified.output["conclusion"] == "TRUE"
        assert verified.output["cnf_uri"] == cnf.artifact_uri
        assert verified.output[evidence_field] == evidence_uri
        assert verified.assurance.verification_record_uri is not None
        assert case["required_capabilities"] == [find_id, verify_id]
