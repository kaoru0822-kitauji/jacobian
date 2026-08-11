"""Lean-owned conversion of backend messages into stable diagnostics."""

from __future__ import annotations

import re

from jacobian.contracts.lean import (
    LeanDiagnostic,
    LeanDiagnosticPhase,
    LeanDiagnosticPosition,
    LeanDiagnosticSource,
    LeanDiagnosticSourceSpan,
    LeanEnvironment,
)
from jacobian.contracts.results import ResultEnvelope
from jacobian.lean_frontend.repl import _response_errors
from jacobian.lean_frontend.repl_protocol import (
    LeanReplErrorResponse,
    LeanReplMessage,
    LeanReplValidatedExecution,
)

_CHECKER_REJECTION = re.compile(
    r"^Lean rejected the proof at line (?P<line>\d+), column "
    r"(?P<column>\d+): (?P<message>.+?)\. Correct the proof body and retry\.$"
)
_METAVARIABLE = re.compile(r"\?m\.\d+|\?[A-Za-z_][A-Za-z0-9_.]*")
_INTERNAL_SCAFFOLD_WARNINGS = frozenset({"declaration uses `sorry`"})
_MESSAGE_CLASSIFIERS = (
    (
        ("type mismatch", "application type mismatch"),
        "LEAN_TYPE_MISMATCH",
        "Lean reported a type mismatch.",
    ),
    (
        ("unsolved goals", "unsolved goal"),
        "LEAN_UNSOLVED_GOALS",
        "Lean left one or more goals unsolved.",
    ),
    (
        ("unknown identifier", "unknown constant"),
        "LEAN_UNKNOWN_IDENTIFIER",
        "Lean could not resolve an identifier.",
    ),
    (
        ("failed to synthesize", "failed to find instance"),
        "LEAN_SYNTHESIS_FAILED",
        "Lean could not synthesize a required instance or value.",
    ),
    (
        ("no goals to be solved",),
        "LEAN_NO_GOALS",
        "The tactic was applied after all goals were closed.",
    ),
    (
        ("forbidden lean command", "proof hole"),
        "LEAN_FORBIDDEN_SOURCE",
        "The source uses a forbidden Lean construct.",
    ),
)
_PHASE_FALLBACKS = {
    LeanDiagnosticPhase.TERM_ELABORATION: (
        "LEAN_TERM_REJECTED",
        "Lean rejected the supplied term.",
    ),
    LeanDiagnosticPhase.TACTIC_EXECUTION: (
        "LEAN_TACTIC_REJECTED",
        "Lean rejected the supplied tactic.",
    ),
    LeanDiagnosticPhase.STATE_RECONSTRUCTION: (
        "LEAN_STATE_RECONSTRUCTION_FAILED",
        "Lean could not reconstruct the proof state.",
    ),
    LeanDiagnosticPhase.SOURCE_ELABORATION: (
        "LEAN_SOURCE_REJECTED",
        "Lean rejected the supplied source.",
    ),
    LeanDiagnosticPhase.KERNEL_CHECK: (
        "LEAN_PROOF_REJECTED",
        "Lean rejected the supplied proof.",
    ),
}


def repl_diagnostics(
    responses: LeanReplValidatedExecution,
    *,
    final_phase: LeanDiagnosticPhase = LeanDiagnosticPhase.TACTIC_EXECUTION,
    final_source: LeanDiagnosticSource = LeanDiagnosticSource.TACTIC,
    final_column_offset: int = 0,
) -> tuple[LeanDiagnostic, ...]:
    """Convert one clean replay into bounded, payload-relative diagnostics."""

    diagnostics: list[LeanDiagnostic] = []
    seen: set[tuple[LeanDiagnosticPhase, str]] = set()
    for index, response in enumerate(responses):
        phase = (
            LeanDiagnosticPhase.SOURCE_ELABORATION
            if index == 0
            else (
                LeanDiagnosticPhase.STATE_RECONSTRUCTION if index == 1 else final_phase
            )
        )
        source = (
            LeanDiagnosticSource.STATEMENT
            if index == 0
            else (final_source if index == 2 else None)
        )
        offset = final_column_offset if index == 2 else 0
        if isinstance(response, LeanReplErrorResponse):
            _append_diagnostic(
                diagnostics,
                seen,
                raw=response.message,
                severity="ERROR",
                phase=phase,
                source=None,
                message=None,
                column_offset=0,
                goal_index=(0 if index == 2 else None),
            )
            continue
        response_messages = response.messages
        for item in response_messages:
            if (
                index == 0
                and item.severity == "warning"
                and item.data.strip() in _INTERNAL_SCAFFOLD_WARNINGS
            ):
                # The initial source deliberately contains one private `sorry`
                # placeholder so the REPL can expose a proof state. It is not
                # part of the caller's statement, tactic, or term and therefore
                # must not outrank payload-owned diagnostics in agent results.
                continue
            severity = (
                "ERROR"
                if item.severity == "error"
                else ("WARNING" if item.severity == "warning" else "INFO")
            )
            _append_diagnostic(
                diagnostics,
                seen,
                raw=item.data,
                severity=severity,
                phase=phase,
                source=source,
                message=item,
                column_offset=offset,
                goal_index=(0 if index == 2 and severity == "ERROR" else None),
            )
        emitted_errors = {item.data for item in response_messages}
        for raw in _response_errors(response):
            if raw in emitted_errors:
                continue
            _append_diagnostic(
                diagnostics,
                seen,
                raw=raw,
                severity="ERROR",
                phase=phase,
                source=None,
                message=None,
                column_offset=0,
                goal_index=(0 if index == 2 else None),
            )
    return tuple(diagnostics)


def checker_diagnostics(
    result: ResultEnvelope,
    *,
    statement: str,
    proof: str,
    environment: LeanEnvironment,
) -> tuple[LeanDiagnostic, ...]:
    """Convert a checker rejection without changing its mathematical verdict."""

    diagnostics: list[LeanDiagnostic] = []
    for detail in result.input.errors:
        match = _CHECKER_REJECTION.fullmatch(detail)
        raw = match.group("message") if match is not None else detail
        source_span = (
            _checker_payload_span(
                line=int(match.group("line")),
                column=int(match.group("column")),
                statement=statement,
                proof=proof,
                environment=environment,
            )
            if match is not None
            else None
        )
        code, message = _classify(raw, LeanDiagnosticPhase.KERNEL_CHECK)
        diagnostics.append(
            LeanDiagnostic(
                code=code,
                phase=LeanDiagnosticPhase.KERNEL_CHECK,
                severity="ERROR",
                message=message,
                source_span=source_span,
                metavariable=_first_metavariable(raw),
                raw_backend_message=raw,
            )
        )
    return tuple(diagnostics)


def _append_diagnostic(
    diagnostics: list[LeanDiagnostic],
    seen: set[tuple[LeanDiagnosticPhase, str]],
    *,
    raw: str,
    severity: str,
    phase: LeanDiagnosticPhase,
    source: LeanDiagnosticSource | None,
    message: LeanReplMessage | None,
    column_offset: int,
    goal_index: int | None,
) -> None:
    key = (phase, raw)
    if key in seen:
        return
    seen.add(key)
    code, normalized = _classify(raw, phase)
    diagnostics.append(
        LeanDiagnostic.model_validate(
            {
                "code": code,
                "phase": phase,
                "severity": severity,
                "message": normalized,
                "source_span": _repl_source_span(
                    source,
                    message,
                    column_offset=column_offset,
                ),
                "goal_index": goal_index,
                "metavariable": _first_metavariable(raw),
                "raw_backend_message": raw,
            }
        )
    )


def _classify(
    raw: str,
    phase: LeanDiagnosticPhase,
) -> tuple[str, str]:
    lowered = raw.casefold()
    for needles, code, message in _MESSAGE_CLASSIFIERS:
        if any(needle in lowered for needle in needles):
            return code, message
    return _PHASE_FALLBACKS[phase]


def _repl_source_span(
    source: LeanDiagnosticSource | None,
    message: LeanReplMessage | None,
    *,
    column_offset: int,
) -> LeanDiagnosticSourceSpan | None:
    if source is None or message is None:
        return None
    start = _offset_position(
        message.pos.line,
        message.pos.column,
        column_offset=column_offset,
    )
    end_position = message.end_pos or message.pos
    end = _offset_position(
        end_position.line,
        end_position.column,
        column_offset=column_offset,
    )
    if (end.line, end.column) < (start.line, start.column):
        end = start
    return LeanDiagnosticSourceSpan(source=source, start=start, end=end)


def _offset_position(
    line: int,
    column: int,
    *,
    column_offset: int,
) -> LeanDiagnosticPosition:
    return LeanDiagnosticPosition(
        line=line,
        column=max(0, column - column_offset) if line == 0 else column,
    )


def _checker_payload_span(
    *,
    line: int,
    column: int,
    statement: str,
    proof: str,
    environment: LeanEnvironment,
) -> LeanDiagnosticSourceSpan | None:
    theorem_line = 4 if environment is LeanEnvironment.MATHLIB else 3
    theorem_prefix = "theorem jacobian_theorem : ("
    proof_prefix = f"theorem jacobian_theorem : ({statement}) := "
    if line == theorem_line:
        if len(theorem_prefix) <= column <= len(theorem_prefix) + len(statement):
            position = LeanDiagnosticPosition(
                line=0,
                column=min(len(statement), max(0, column - len(theorem_prefix))),
            )
            source = LeanDiagnosticSource.STATEMENT
        elif column >= len(proof_prefix):
            position = LeanDiagnosticPosition(
                line=0,
                column=min(len(proof.splitlines()[0]), column - len(proof_prefix)),
            )
            source = LeanDiagnosticSource.PROOF
        else:
            return None
    elif line > theorem_line:
        complete_proof_term = re.match(r"^by(?:\s|$)", proof.lstrip()) is not None
        proof_line = (
            line - theorem_line if complete_proof_term else line - theorem_line - 1
        )
        proof_lines = proof.splitlines()
        if proof_line < 0 or proof_line >= len(proof_lines):
            return None
        position = LeanDiagnosticPosition(
            line=proof_line,
            column=min(
                len(proof_lines[proof_line]),
                max(0, column if complete_proof_term else column - 2),
            ),
        )
        source = LeanDiagnosticSource.PROOF
    else:
        return None
    return LeanDiagnosticSourceSpan(source=source, start=position, end=position)


def _first_metavariable(raw: str) -> str | None:
    match = _METAVARIABLE.search(raw)
    return match.group(0) if match is not None else None


__all__ = ["checker_diagnostics", "repl_diagnostics"]
