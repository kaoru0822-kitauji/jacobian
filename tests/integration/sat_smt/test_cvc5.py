from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from jacobian.bounded_process import BoundedProcessResult
from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityInstallTier,
    CapabilityProviderAvailability,
    CapabilityProviderRuntime,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel
from jacobian.provider_measurements import measure_provider
from jacobian.smt import SmtArtifactError

pytestmark = pytest.mark.external_backend

_QF_UF_UNSAT = (
    "(set-logic QF_UF)\n"
    "(declare-sort U 0)\n"
    "(declare-fun a () U)\n"
    "(declare-fun b () U)\n"
    "(assert (= a b))\n"
    "(assert (not (= a b)))\n"
    "(check-sat)\n"
)
_QF_LIA_UNSAT = (
    "(set-logic QF_LIA)\n"
    "(declare-fun x () Int)\n"
    "(assert (>= x 1))\n"
    "(assert (<= x 0))\n"
    "(check-sat)\n"
)
_QF_LRA_UNSAT = (
    "(set-logic QF_LRA)\n"
    "(declare-fun x () Real)\n"
    "(assert (> x 1.0))\n"
    "(assert (< x 0.0))\n"
    "(check-sat)\n"
)
_QF_UF_SAT = "(set-logic QF_UF)\n(declare-fun p () Bool)\n(assert p)\n(check-sat)\n"


def _invoke(kernel: JacobianKernel, text: str, *, logic: str = "QF_UF"):
    return kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="smt.unsat_proof.find",
            input={
                "logic": logic,
                "smtlib_text": text,
                "resource_budget": {"wall_seconds": 5},
            },
        )
    )


@pytest.fixture(scope="module")
def kernel(
    tmp_path_factory: pytest.TempPathFactory,
    kernel_store_template: Path,
) -> JacobianKernel:
    root = tmp_path_factory.mktemp("cvc5-kernel")
    shutil.copytree(kernel_store_template, root, dirs_exist_ok=True)
    return JacobianKernel(root)


def test_pinned_cvc5_capability_is_discoverable(kernel: JacobianKernel) -> None:
    assert kernel.cvc5_runtime.availability is CapabilityProviderAvailability.AVAILABLE
    catalog = kernel.capabilities.catalog().capabilities
    descriptor = next(
        descriptor
        for descriptor in catalog
        if descriptor.capability_id == "smt.unsat_proof.find"
    )
    assert descriptor.provider == "cvc5"
    assert descriptor.provider_runtime == kernel.cvc5_runtime
    assert descriptor.provider_runtime.checker_ids == ()
    assert "smt.unsat_proof.verify" not in {
        installed.capability_id for installed in catalog
    }
    assert kernel.smt.installation.problem_schema_uri.startswith("artifact://sha256/")
    assert kernel.smt.installation.proof_schema_uri.startswith("artifact://sha256/")


def test_pinned_cvc5_measurement_runs_its_proof_reproduction(
    kernel: JacobianKernel,
) -> None:
    measurement = measure_provider(kernel.cvc5_runtime)

    assert measurement.cold_start.status.value == "COMPLETED"
    assert measurement.reproduction_case.status.value == "COMPLETED"
    assert measurement.cold_install.status.value == "SKIPPED"
    assert measurement.installed_bytes > 0


def test_qf_uf_proof_is_durable_computed_evidence(kernel: JacobianKernel) -> None:
    result = _invoke(kernel, _QF_UF_UNSAT)

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.output["status"] == "PROOF_PRODUCED"
    assert result.output["solver_status"] == "UNSATISFIABLE"
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["contains_holes"] is False
    assert result.output["alethe_hole_count"] == 0
    assert result.assurance.verification_record_uri is None
    assert len(result.artifact_uris) == 2

    resolved = kernel.smt.resolve_proof(result.output["proof_uri"])
    assert resolved.proof.problem.problem_artifact_uri == result.output["problem_uri"]
    assert resolved.proof.raw_bytes().startswith(b"(\n")
    assert resolved.proof.contains_holes is False
    assert result.output["problem_uri"] in resolved.artifact.manifest.parents


@pytest.mark.parametrize(
    ("logic", "text"),
    (
        ("QF_LIA", _QF_LIA_UNSAT),
        ("QF_LRA", _QF_LRA_UNSAT),
    ),
)
def test_linear_arithmetic_holes_stay_explicit_and_unverified(
    kernel: JacobianKernel,
    logic: str,
    text: str,
) -> None:
    result = _invoke(kernel, text, logic=logic)

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["status"] == "PROOF_PRODUCED"
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["contains_holes"] is True
    assert result.output["alethe_hole_count"] >= 1
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.assurance.verification_record_uri is None


def test_sat_report_produces_no_unsat_artifact_or_conclusion(
    kernel: JacobianKernel,
) -> None:
    result = _invoke(kernel, _QF_UF_SAT)

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output == {
        "alethe_hole_count": None,
        "conclusion": "UNKNOWN",
        "contains_holes": None,
        "detail": (
            "cvc5 reported SATISFIABLE without producing an UNSAT proof; "
            "no SAT or UNSAT conclusion follows."
        ),
        "problem_uri": result.output["problem_uri"],
        "proof_uri": None,
        "solver_status": "SATISFIABLE",
        "status": "NO_PROOF_PRODUCED",
    }
    assert result.artifact_uris == (result.output["problem_uri"],)


def test_incremental_or_mismatched_queries_are_rejected_before_solver_evidence(
    kernel: JacobianKernel,
) -> None:
    for invalid in (
        _QF_UF_UNSAT.replace("(check-sat)\n", "(push 1)\n(check-sat)\n"),
        _QF_UF_UNSAT.replace("QF_UF", "QF_LIA"),
        _QF_UF_UNSAT + "(check-sat)\n",
    ):
        result = _invoke(kernel, invalid)
        assert result.execution.status is ExecutionStatus.ERROR
        assert result.output["error"]["code"] == "INVALID_SMT_UNSAT_PROOF_REQUEST"
        assert result.artifact_uris == ()
        assert result.diagnostics[0].code == "INVALID_SMT_UNSAT_PROOF_REQUEST"


def test_theory_outside_declared_logic_fails_in_isolated_parser(
    kernel: JacobianKernel,
) -> None:
    nonlinear_lia = (
        "(set-logic QF_LIA)\n"
        "(declare-fun x () Int)\n"
        "(assert (= (* x x) 2))\n"
        "(check-sat)\n"
    )

    result = _invoke(kernel, nonlinear_lia, logic="QF_LIA")

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.output == {}
    assert result.assurance.level is CapabilityAssuranceLevel.HEURISTIC
    assert result.diagnostics[0].code == "CVC5_EXECUTION_FAILED"
    assert len(result.artifact_uris) == 1


def test_problem_and_proof_bindings_reject_cross_domain_artifacts(
    kernel: JacobianKernel,
) -> None:
    cnf_uri = kernel.sat.put_cnf(
        variable_names=("x",),
        clauses=((1,),),
    ).artifact_uri

    with pytest.raises(SmtArtifactError):
        kernel.smt.resolve_problem(cnf_uri)
    with pytest.raises(SmtArtifactError):
        kernel.smt.resolve_proof(cnf_uri)


def test_worker_proof_metadata_mismatch_fails_closed(
    kernel: JacobianKernel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_worker(command: list[str], **_kwargs: Any) -> BoundedProcessResult:
        Path(command[5]).write_bytes(
            b'(\n(step t0 (cl) :rule hole :args ("untranslated rewrite"))\n)\n'
        )
        stdout = json.dumps(
            {
                "protocol": "jacobian.cvc5-worker/v1",
                "solver_status": "UNSATISFIABLE",
                "proof_written": True,
                "alethe_hole_count": 0,
            },
            separators=(",", ":"),
        ).encode()
        return BoundedProcessResult(
            returncode=0,
            stdout=stdout,
            stderr=b"",
            stdout_exceeded=False,
            stderr_exceeded=False,
            timed_out=False,
        )

    monkeypatch.setattr("jacobian.cvc5.run_bounded_process", fake_worker)

    result = _invoke(kernel, _QF_UF_UNSAT)

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.output == {}
    assert result.assurance.level is CapabilityAssuranceLevel.HEURISTIC
    assert result.diagnostics[0].code == "CVC5_PROOF_METADATA_MISMATCH"
    assert len(result.artifact_uris) == 1


def test_worker_timeout_fails_without_solver_conclusion(
    kernel: JacobianKernel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "jacobian.cvc5.run_bounded_process",
        lambda *_args, **_kwargs: BoundedProcessResult(
            returncode=None,
            stdout=b"",
            stderr=b"",
            stdout_exceeded=False,
            stderr_exceeded=False,
            timed_out=True,
        ),
    )

    result = _invoke(kernel, _QF_UF_UNSAT)

    assert result.execution.status is ExecutionStatus.TIMEOUT
    assert result.output == {}
    assert result.assurance.level is CapabilityAssuranceLevel.HEURISTIC
    assert result.diagnostics[0].code == "CVC5_TIMEOUT"
    assert len(result.artifact_uris) == 1


def test_missing_optional_cvc5_leaves_artifact_boundary_but_no_capability(
    tmp_path: Path,
    initialized_kernel_store: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unavailable = CapabilityProviderRuntime(
        provider="cvc5",
        availability=CapabilityProviderAvailability.UNAVAILABLE,
        platform="linux-x86_64",
        install_tier=CapabilityInstallTier.T1,
        license_id="BSD-3-Clause",
        diagnostic="cvc5 is intentionally unavailable for this test.",
    )
    monkeypatch.setattr(
        "jacobian.kernel.cvc5_provider_runtime",
        lambda: unavailable,
    )

    without_cvc5 = JacobianKernel(tmp_path)

    assert "smt.unsat_proof.find" not in {
        descriptor.capability_id
        for descriptor in without_cvc5.capabilities.catalog().capabilities
    }
    assert without_cvc5.smt.installation.problem_schema_uri.startswith(
        "artifact://sha256/"
    )
