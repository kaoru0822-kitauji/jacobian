from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.contracts.sat import SatProofArtifact
from jacobian.kernel import JacobianKernel
from jacobian.provider_runtime import (
    CADICAL_VERSION,
    DRAT_TRIM_RELEASE_TAG,
    cadical_provider_runtime,
    drat_trim_provider_runtime,
)



pytestmark = [
    pytest.mark.integration,
    pytest.mark.external_backend,
    pytest.mark.usefixtures("initialized_kernel_store_with_references"),
]

def _invoke(
    kernel: JacobianKernel,
    capability_id: str,
    payload: dict[str, object],
    *,
    mode: CapabilityMode,
):
    return kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id=capability_id,
            mode=mode,
            input=payload,
        )
    )


def test_cadical_text_proof_replays_in_pinned_drat_trim(
    tmp_path: Path,
) -> None:
    cadical = cadical_provider_runtime()
    drat_trim = drat_trim_provider_runtime()
    if cadical.version != CADICAL_VERSION:
        pytest.skip(f"requires pinned CaDiCaL {CADICAL_VERSION}")
    if drat_trim.version != DRAT_TRIM_RELEASE_TAG:
        pytest.skip(f"requires pinned DRAT-trim {DRAT_TRIM_RELEASE_TAG}")
    kernel = JacobianKernel(tmp_path, install_references=True)
    cnf = kernel.sat.put_cnf(
        variable_names=(
            "p1h1",
            "p1h2",
            "p2h1",
            "p2h2",
            "p3h1",
            "p3h2",
        ),
        clauses=(
            (1, 2),
            (3, 4),
            (5, 6),
            (-1, -3),
            (-1, -5),
            (-3, -5),
            (-2, -4),
            (-2, -6),
            (-4, -6),
        ),
    )

    produced = _invoke(
        kernel,
        "sat.unsat_proof.find",
        {
            "cnf_uri": cnf.artifact_uri,
            "resource_budget": {"wall_seconds": 5},
        },
        mode=CapabilityMode.EXPLORE,
    )
    assert produced.execution.status is ExecutionStatus.COMPLETED
    assert produced.output["status"] == "PROOF_PRODUCED"
    proof_uri = produced.output["proof_uri"]

    verified = _invoke(
        kernel,
        "sat.unsat_proof.verify",
        {"proof_uri": proof_uri},
        mode=CapabilityMode.VERIFY,
    )
    assert verified.execution.status is ExecutionStatus.COMPLETED
    assert verified.output["status"] == "VERIFIED_UNSAT"
    assert verified.output["conclusion"] == "TRUE"
    assert verified.assurance.level is CapabilityAssuranceLevel.VERIFIED

    stored_proof = SatProofArtifact.model_validate(kernel.store.get(proof_uri).payload)
    empty_proof = kernel.sat.put_proof(
        cnf_uri=cnf.artifact_uri,
        proof=b"",
        producer=stored_proof.producer,
        resource_budget=stored_proof.resource_budget,
    )
    rejected = _invoke(
        kernel,
        "sat.unsat_proof.verify",
        {"proof_uri": empty_proof.artifact_uri},
        mode=CapabilityMode.VERIFY,
    )
    assert rejected.output["status"] == "REJECTED"
    assert rejected.output["conclusion"] == "UNKNOWN"
    assert rejected.assurance.verification_record_uri is None

    raw_proof = stored_proof.raw_bytes()
    assert raw_proof.endswith(b"0\n")
    unsupported_contradiction = kernel.sat.put_proof(
        cnf_uri=cnf.artifact_uri,
        proof=b"0\n",
        producer=stored_proof.producer,
        resource_budget=stored_proof.resource_budget,
    )
    unsupported_replay = _invoke(
        kernel,
        "sat.unsat_proof.verify",
        {"proof_uri": unsupported_contradiction.artifact_uri},
        mode=CapabilityMode.VERIFY,
    )
    assert unsupported_replay.output["status"] == "REJECTED"
    assert unsupported_replay.output["conclusion"] == "UNKNOWN"
    assert unsupported_replay.assurance.verification_record_uri is None

    concatenated_proof = kernel.sat.put_proof(
        cnf_uri=cnf.artifact_uri,
        proof=raw_proof + b"1 0\n",
        producer=stored_proof.producer,
        resource_budget=stored_proof.resource_budget,
    )
    concatenated_replay = _invoke(
        kernel,
        "sat.unsat_proof.verify",
        {"proof_uri": concatenated_proof.artifact_uri},
        mode=CapabilityMode.VERIFY,
    )
    assert concatenated_replay.output["status"] == "REJECTED"
    assert concatenated_replay.output["conclusion"] == "UNKNOWN"
    assert concatenated_replay.assurance.verification_record_uri is None

    satisfiable = kernel.sat.put_cnf(
        variable_names=("x",),
        clauses=((1,),),
    )
    cross_bound = kernel.sat.put_proof(
        cnf_uri=satisfiable.artifact_uri,
        proof=stored_proof.raw_bytes(),
        producer=stored_proof.producer,
        resource_budget=stored_proof.resource_budget,
    )
    cross_replay = _invoke(
        kernel,
        "sat.unsat_proof.verify",
        {"proof_uri": cross_bound.artifact_uri},
        mode=CapabilityMode.VERIFY,
    )
    assert cross_replay.output["status"] == "REJECTED"
    assert cross_replay.output["conclusion"] == "UNKNOWN"
    assert cross_replay.assurance.verification_record_uri is None
