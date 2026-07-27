from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityProviderAvailability,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.contracts.smt import SmtResourceBudget
from jacobian.kernel import JacobianKernel
from jacobian.provider_runtime import carcara_provider_runtime


pytestmark = [
    pytest.mark.external_backend,
    pytest.mark.usefixtures("initialized_kernel_store_with_references"),
]

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "smt"


@pytest.fixture(scope="module")
def kernel(tmp_path_factory: pytest.TempPathFactory) -> JacobianKernel:
    runtime = carcara_provider_runtime()
    if runtime.availability is not CapabilityProviderAvailability.AVAILABLE:
        pytest.skip("the exact operator-provenanced Carcara runtime is unavailable")
    installed = JacobianKernel(
        tmp_path_factory.mktemp("carcara-kernel"),
        install_references=True,
    )
    assert installed.carcara_runtime == runtime
    return installed


def _produce(kernel: JacobianKernel, logic: str, fixture: str):
    return kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="smt.unsat_proof.find",
            input={
                "logic": logic,
                "smtlib_text": (_FIXTURES / fixture).read_text(encoding="ascii"),
                "resource_budget": {"wall_seconds": 5},
            },
        )
    )


def _verify(kernel: JacobianKernel, proof_uri: str):
    return kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="smt.unsat_proof.verify",
            mode=CapabilityMode.VERIFY,
            input={"proof_uri": proof_uri},
        )
    )


def test_zero_hole_qf_uf_proof_is_independently_verified(
    kernel: JacobianKernel,
) -> None:
    produced = _produce(kernel, "QF_UF", "qf_uf_equality_unsat.smt2")

    assert produced.output["contains_holes"] is False
    assert produced.output["conclusion"] == "UNKNOWN"
    verified = _verify(kernel, produced.output["proof_uri"])

    assert verified.execution.status is ExecutionStatus.COMPLETED
    assert verified.output["status"] == "VERIFIED_UNSAT"
    assert verified.output["conclusion"] == "TRUE"
    assert verified.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert verified.output["verification_record_uri"] is not None


@pytest.mark.parametrize(
    ("logic", "fixture"),
    (
        ("QF_LIA", "qf_lia_bounds_unsat.smt2"),
        ("QF_LRA", "qf_lra_bounds_unsat.smt2"),
    ),
)
def test_holey_arithmetic_proofs_remain_unverified(
    kernel: JacobianKernel,
    logic: str,
    fixture: str,
) -> None:
    produced = _produce(kernel, logic, fixture)

    assert produced.output["contains_holes"] is True
    assert produced.output["alethe_hole_count"] >= 1
    checked = _verify(kernel, produced.output["proof_uri"])

    assert checked.execution.status is ExecutionStatus.COMPLETED
    assert checked.output["status"] == "REJECTED"
    assert checked.output["conclusion"] == "UNKNOWN"
    assert checked.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert checked.output["verification_record_uri"] is None


def test_unknown_rule_is_not_silently_treated_as_verified(
    kernel: JacobianKernel,
) -> None:
    produced = _produce(kernel, "QF_UF", "qf_uf_equality_unsat.smt2")
    resolved = kernel.smt.resolve_proof(produced.output["proof_uri"])
    unknown_rule = resolved.proof.raw_bytes().replace(
        b":rule resolution",
        b":rule jacobian_unknown_rule",
    )
    mutated = kernel.smt.put_proof(
        problem_uri=produced.output["problem_uri"],
        proof=unknown_rule,
        producer=kernel.cvc5_runtime,
        resource_budget=SmtResourceBudget(wall_seconds=5),
    )

    checked = _verify(kernel, mutated.artifact_uri)

    assert checked.execution.status is ExecutionStatus.COMPLETED
    assert checked.output["status"] == "REJECTED"
    assert checked.output["conclusion"] == "UNKNOWN"
    assert checked.output["verification_record_uri"] is None
