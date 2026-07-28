from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from jacobian.contracts.capabilities import CapabilityMode, CapabilityRequest
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel
from jacobian.provider_runtime import CADICAL_VERSION, cadical_provider_runtime

pytestmark = [
    pytest.mark.external_backend,
    pytest.mark.skipif(
        shutil.which("cadical") is None,
        reason="CaDiCaL is not installed",
    ),
]


def test_pinned_cadical_produces_a_model_and_text_drat_proof(
    tmp_path: Path,
) -> None:
    runtime = cadical_provider_runtime()
    if runtime.version != CADICAL_VERSION:
        pytest.skip(f"requires pinned CaDiCaL {CADICAL_VERSION}")
    kernel = JacobianKernel(tmp_path)
    capability_ids = {
        descriptor.capability_id
        for descriptor in kernel.capabilities.catalog().capabilities
    }
    assert {"sat.model.find", "sat.unsat_proof.find"}.issubset(capability_ids)

    satisfiable = kernel.sat.put_cnf(
        variable_names=("x", "y"),
        clauses=((1,), (-2,)),
    )
    model = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="sat.model.find",
            mode=CapabilityMode.EXPLORE,
            input={
                "cnf_uri": satisfiable.artifact_uri,
                "resource_budget": {"wall_seconds": 5},
            },
        )
    )
    assert model.execution.status is ExecutionStatus.COMPLETED
    assert model.output["status"] == "ASSIGNMENT_PRODUCED"
    assert model.output["conclusion"] == "UNKNOWN"

    unsatisfiable = kernel.sat.put_cnf(
        variable_names=("x",),
        clauses=((1,), (-1,)),
    )
    proof = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="sat.unsat_proof.find",
            mode=CapabilityMode.EXPLORE,
            input={
                "cnf_uri": unsatisfiable.artifact_uri,
                "resource_budget": {"wall_seconds": 5},
            },
        )
    )
    assert proof.execution.status is ExecutionStatus.COMPLETED
    assert proof.output["status"] == "PROOF_PRODUCED"
    assert proof.output["conclusion"] == "UNKNOWN"
