"""Search-side support for bounded Erdős-Straus verification."""

from __future__ import annotations

from fractions import Fraction
from typing import Any, TypeGuard

_MIN_N = 2
_MAX_N = 10_000


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _claim_view(payload: dict[str, Any]) -> dict[str, Any]:
    predicate = payload.get("predicate")
    if not isinstance(predicate, dict):
        return payload
    parameters = predicate.get("parameters", {})
    return {
        "predicate": predicate.get("name"),
        **(parameters if isinstance(parameters, dict) else {}),
    }


def _validate_range(payload: dict[str, Any]) -> list[str]:
    lower = payload.get("lower_bound")
    upper = payload.get("upper_bound")
    if not _is_int(lower) or not _is_int(upper):
        return ["lower_bound and upper_bound must be integers"]
    if lower < _MIN_N:
        return [f"lower_bound must be at least {_MIN_N}"]
    if upper < lower:
        return ["upper_bound must be at least lower_bound"]
    if upper > _MAX_N:
        return [f"upper_bound exceeds the reference limit of {_MAX_N}"]
    return []


def validate_claim(payload: dict[str, Any]) -> list[str]:
    if payload.get("predicate") != "erdos_straus_range":
        return ["unsupported Erdős-Straus claim predicate"]
    return _validate_range(payload)


def validate_candidate(payload: dict[str, Any]) -> list[str]:
    return _validate_range(payload)


def _validate_candidate_for_claim(
    claim: dict[str, Any],
    candidate: dict[str, Any],
) -> list[str]:
    errors = validate_candidate(candidate)
    if errors:
        return errors
    if (
        candidate["lower_bound"] != claim["lower_bound"]
        or candidate["upper_bound"] != claim["upper_bound"]
    ):
        return ["candidate range must exactly match the claim range"]
    return []


def _decompose(n: int) -> tuple[int, int, int] | None:
    """Find ordered positive denominators using exact rational arithmetic."""

    for x in range(n // 4 + 1, (3 * n) // 4 + 1):
        remaining = Fraction(4, n) - Fraction(1, x)
        if remaining <= 0:
            continue
        y_min = max(x, remaining.denominator // remaining.numerator + 1)
        y_max = (2 * remaining.denominator) // remaining.numerator
        for y in range(y_min, y_max + 1):
            last = remaining - Fraction(1, y)
            if last > 0 and last.denominator % last.numerator == 0:
                z = last.denominator // last.numerator
                return x, y, z
    return None


def _decomposition_table(
    lower: int,
    upper: int,
) -> tuple[list[dict[str, int]], int | None]:
    table: list[dict[str, int]] = []
    for n in range(lower, upper + 1):
        decomposition = _decompose(n)
        if decomposition is None:
            return table, n
        x, y, z = decomposition
        table.append({"n": n, "x": x, "y": y, "z": z})
    return table, None


def evaluate_capability(request: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a bounded range without granting verification authority."""

    claim = _claim_view(request.get("claim", {}))
    candidate = request.get("candidate")
    errors = validate_claim(claim)
    if not isinstance(candidate, dict):
        errors.append("candidate must be an object")
    elif not errors:
        errors.extend(_validate_candidate_for_claim(claim, candidate))
    if errors:
        raise ValueError("; ".join(errors))
    assert isinstance(candidate, dict)

    lower = candidate["lower_bound"]
    upper = candidate["upper_bound"]
    table, missing = _decomposition_table(lower, upper)
    complete = missing is None
    return {
        "response_version": "1",
        "conclusion": "TRUE" if complete else "UNKNOWN",
        "arithmetic": "EXACT_INTEGER",
        "method": "EXHAUSTIVE_FINITE" if complete else "BOUNDED_SEARCH",
        "coverage": "EXHAUSTIVE" if complete else "BOUNDED",
        "objectives": {
            "range_size": upper - lower + 1,
            "decompositions_found": len(table),
        },
        "features": {
            "lower_bound": lower,
            "upper_bound": upper,
        },
        "failure_classifications": ([] if complete else ["decomposition_not_found"]),
        "detail": (
            f"exact decompositions found for every n in [{lower}, {upper}]"
            if complete
            else f"search did not find a decomposition for n={missing}"
        ),
    }


def find_witness_capability(request: dict[str, Any]) -> dict[str, Any]:
    """Propose a complete bounded decomposition table as unverified evidence."""

    claim = _claim_view(request.get("claim", {}))
    candidate = request.get("candidate")
    role = request.get("witness_role")
    errors = validate_claim(claim)
    if role != "SUPPORTS_CLAIM":
        errors.append("erdos_straus_range supports only SUPPORTS_CLAIM witnesses")
    if not isinstance(candidate, dict):
        errors.append("candidate must be an object")
    elif not errors:
        errors.extend(_validate_candidate_for_claim(claim, candidate))
    if errors:
        raise ValueError("; ".join(errors))
    assert isinstance(candidate, dict)

    lower = candidate["lower_bound"]
    upper = candidate["upper_bound"]
    table, missing = _decomposition_table(lower, upper)
    if missing is not None:
        return {
            "response_version": "1",
            "status": "NOT_FOUND_WITHIN_SCOPE",
            "arithmetic": "EXACT_INTEGER",
            "coverage": "BOUNDED",
            "detail": (
                f"search found {len(table)} decompositions but none for n={missing}; "
                "this is not a counterexample"
            ),
        }
    return {
        "response_version": "1",
        "status": "FOUND",
        "witness": {"decompositions": table},
        "witness_format": "erdos_straus.decomposition_table",
        "format_version": "1",
        "role": "SUPPORTS_CLAIM",
        "arithmetic": "EXACT_INTEGER",
        "coverage": "EXHAUSTIVE",
        "detail": f"complete proposed decomposition table for [{lower}, {upper}]",
    }
