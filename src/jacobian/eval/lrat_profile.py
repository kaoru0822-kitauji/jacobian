"""Validation-only checks for Jacobian's frozen ASCII LRAT profile."""

from __future__ import annotations

from jacobian.contracts.sat import CanonicalCnf, SatLratResourceLimits


def _profile_candidate_error(
    candidate: tuple[int, ...],
    hints: list[int],
    *,
    line_number: int,
    variable_count: int,
    limits: SatLratResourceLimits,
) -> str | None:
    if not hints:
        return f"line {line_number}: RUP hints are required"
    if any(literal == 0 or abs(literal) > variable_count for literal in candidate):
        return f"line {line_number}: literal is outside the CNF variables"
    if len(candidate) > limits.max_clause_literals:
        return f"line {line_number}: clause literal limit exceeded"
    if any(hint <= 0 for hint in hints):
        return f"line {line_number}: RAT and deletion hints are unsupported"
    if len(hints) > limits.max_hints_per_step:
        return f"line {line_number}: hint limit exceeded"
    return None


def _profile_line(
    line: str,
    *,
    line_number: int,
    last_id: int,
    variable_count: int,
    limits: SatLratResourceLimits,
) -> tuple[int, tuple[int, ...]] | str | None:
    if not line or line.startswith("c "):
        return None
    fields = line.split()
    try:
        values = [int(field) for field in fields]
    except ValueError:
        return f"line {line_number}: non-integer token"
    if len(values) < 4 or values.count(0) != 2:
        return f"line {line_number}: invalid addition framing"
    clause_id = values[0]
    if clause_id <= last_id:
        return f"line {line_number}: clause ids must increase"
    first_zero = values.index(0, 1)
    if values[-1] != 0:
        return f"line {line_number}: invalid addition terminators"
    candidate = tuple(values[1:first_zero])
    hints = values[first_zero + 1 : -1]
    candidate_error = _profile_candidate_error(
        candidate,
        hints,
        line_number=line_number,
        variable_count=variable_count,
        limits=limits,
    )
    if candidate_error is not None:
        return candidate_error
    return clause_id, candidate


def validate_lrat_profile(
    cnf: CanonicalCnf,
    proof: bytes,
    *,
    limits: SatLratResourceLimits,
) -> str | None:
    """Reject unsupported v1 syntax without replaying mathematical steps.

    A successful return only means that the bytes fit the frozen profile. It
    is not a proof result and cannot establish Jacobian verification.
    """

    if len(proof) > limits.max_proof_bytes:
        return "proof exceeds max_proof_bytes"
    try:
        text = proof.decode("ascii")
    except UnicodeDecodeError:
        return "proof is not ASCII"

    last_id = len(cnf.clauses)
    steps = 0
    last_candidate: tuple[int, ...] | None = None
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        parsed = _profile_line(
            raw_line.strip(),
            line_number=line_number,
            last_id=last_id,
            variable_count=len(cnf.variables),
            limits=limits,
        )
        if parsed is None:
            continue
        if isinstance(parsed, str):
            return parsed
        clause_id, candidate = parsed
        steps += 1
        if steps > limits.max_steps:
            return "proof step limit exceeded"
        last_id = clause_id
        last_candidate = candidate

    if steps == 0 or last_candidate != ():
        return "proof must end with an empty-clause addition"
    return None
