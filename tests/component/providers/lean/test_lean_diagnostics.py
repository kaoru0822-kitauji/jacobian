from __future__ import annotations

from jacobian.contracts.lean import (
    LeanDiagnosticPhase,
    LeanDiagnosticSource,
    LeanEnvironment,
)
from jacobian.contracts.results import ResultEnvelope
from jacobian.lean_frontend.diagnostics import checker_diagnostics, repl_diagnostics
from jacobian.lean_frontend.repl_protocol import (
    LeanReplCommandResponse,
    LeanReplProofStepResponse,
)


def _command_with_warning(message: str) -> LeanReplCommandResponse:
    return LeanReplCommandResponse.model_validate(
        {
            "env": 0,
            "messages": [
                {
                    "pos": {"line": 1, "column": 0},
                    "endPos": {"line": 1, "column": 7},
                    "severity": "warning",
                    "data": message,
                }
            ],
            "sorries": [{"goal": "⊢ True", "proofState": 0}],
        }
    )


def _proof_step(*, error: str | None = None) -> LeanReplProofStepResponse:
    payload: dict[str, object] = {
        "proofState": 1,
        "proofStatus": "Goals",
        "goals": ["⊢ True"],
    }
    if error is not None:
        payload["messages"] = [
            {
                "pos": {"line": 0, "column": 6},
                "endPos": {"line": 0, "column": 7},
                "severity": "error",
                "data": error,
            }
        ]
    return LeanReplProofStepResponse.model_validate(payload)


def _rejected_checker_result(detail: str) -> ResultEnvelope:
    return ResultEnvelope.model_validate(
        {
            "execution": {"status": "COMPLETED"},
            "input": {"status": "REJECTED", "errors": [detail]},
            "conclusion": "UNKNOWN",
            "assurance": {
                "arithmetic": "SYMBOLIC",
                "method": "CHECKED_CERTIFICATE",
                "coverage": "NOT_APPLICABLE",
                "verification": "UNVERIFIED",
            },
        }
    )


def test_repl_diagnostics_omit_the_private_sorry_scaffold_warning() -> None:
    diagnostics = repl_diagnostics(
        (
            _command_with_warning("declaration uses `sorry`"),
            _proof_step(),
            _proof_step(error="type mismatch"),
        ),
        final_phase=LeanDiagnosticPhase.TERM_ELABORATION,
        final_source=LeanDiagnosticSource.TERM,
        final_column_offset=len("exact "),
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "LEAN_TYPE_MISMATCH"
    assert diagnostics[0].phase is LeanDiagnosticPhase.TERM_ELABORATION
    assert diagnostics[0].source_span is not None
    assert diagnostics[0].source_span.source is LeanDiagnosticSource.TERM


def test_repl_diagnostics_keep_other_source_warnings() -> None:
    diagnostics = repl_diagnostics(
        (
            _command_with_warning("caller-visible source warning"),
            _proof_step(),
            _proof_step(),
        )
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].phase is LeanDiagnosticPhase.SOURCE_ELABORATION
    assert diagnostics[0].severity == "WARNING"
    assert diagnostics[0].raw_backend_message == "caller-visible source warning"


def test_checker_diagnostics_classify_setup_failure_as_operational() -> None:
    detail = (
        "MATHLIB_MANIFEST: a pinned mathlib package checkout failed integrity "
        "validation"
    )

    diagnostics = checker_diagnostics(
        _rejected_checker_result(detail),
        statement="True",
        proof="by trivial",
        environment=LeanEnvironment.MATHLIB,
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "LEAN_MATHLIB_SETUP_FAILED"
    assert diagnostics[0].phase is LeanDiagnosticPhase.RUNTIME_SETUP
    assert diagnostics[0].source_span is None
    assert diagnostics[0].raw_backend_message == detail


def test_checker_diagnostics_keep_toolchain_failure_out_of_proof_repair() -> None:
    detail = (
        "TOOLCHAIN_PROBE: The pinned Lean 4.31.0 toolchain is unavailable. "
        "Install it and retry."
    )

    diagnostics = checker_diagnostics(
        _rejected_checker_result(detail),
        statement="True",
        proof="by trivial",
        environment=LeanEnvironment.CORE,
    )

    assert [diagnostic.code for diagnostic in diagnostics] == [
        "LEAN_TOOLCHAIN_SETUP_FAILED"
    ]
    assert all(
        diagnostic.phase is LeanDiagnosticPhase.RUNTIME_SETUP
        for diagnostic in diagnostics
    )
