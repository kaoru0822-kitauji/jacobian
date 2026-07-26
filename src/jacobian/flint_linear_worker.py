"""Isolated Python-FLINT worker for one exact rational solution candidate."""

from __future__ import annotations

import importlib
import json
import re
import sys
from fractions import Fraction
from typing import Any

FLINT_LINEAR_WORKER_PROTOCOL = "jacobian.flint-linear-worker/v1"
FLINT_LINEAR_INPUT_LIMIT = 1_000_000
MAX_LINEAR_DIMENSION = 32
MAX_RATIONAL_DIGITS = 256
_INTEGER = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
_VARIABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


class FlintLinearWorkerError(RuntimeError):
    """One worker request could not produce usable evidence."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _emit(payload: dict[str, object]) -> None:
    sys.stdout.write(
        json.dumps(
            {"protocol": FLINT_LINEAR_WORKER_PROTOCOL, **payload},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    sys.stdout.flush()


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _read_request() -> dict[str, Any]:
    encoded = sys.stdin.buffer.read(FLINT_LINEAR_INPUT_LIMIT + 1)
    if len(encoded) > FLINT_LINEAR_INPUT_LIMIT:
        raise FlintLinearWorkerError("FLINT_LINEAR_INPUT_LIMIT_EXCEEDED")
    try:
        payload = json.loads(encoded, object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise FlintLinearWorkerError("FLINT_LINEAR_INPUT_INVALID") from exc
    if not isinstance(payload, dict):
        raise FlintLinearWorkerError("FLINT_LINEAR_INPUT_INVALID")
    return payload


def _rational(value: Any) -> Fraction:
    if not isinstance(value, dict) or set(value) != {"num", "den"}:
        raise FlintLinearWorkerError("FLINT_LINEAR_SYSTEM_INVALID")
    numerator = value["num"]
    denominator = value["den"]
    if (
        not isinstance(numerator, str)
        or not isinstance(denominator, str)
        or _INTEGER.fullmatch(numerator) is None
        or _INTEGER.fullmatch(denominator) is None
        or len(numerator.lstrip("-")) > MAX_RATIONAL_DIGITS
        or len(denominator.lstrip("-")) > MAX_RATIONAL_DIGITS
    ):
        raise FlintLinearWorkerError("FLINT_LINEAR_SYSTEM_INVALID")
    try:
        result = Fraction(int(numerator), int(denominator))
    except (ValueError, ZeroDivisionError) as exc:
        raise FlintLinearWorkerError("FLINT_LINEAR_SYSTEM_INVALID") from exc
    if str(result.numerator) != numerator or str(result.denominator) != denominator:
        raise FlintLinearWorkerError("FLINT_LINEAR_SYSTEM_INVALID")
    return result


def _validate_system(
    request: dict[str, Any],
) -> tuple[list[list[Fraction]], list[Fraction]]:
    if (
        set(request) != {"protocol", "system"}
        or request.get("protocol") != FLINT_LINEAR_WORKER_PROTOCOL
    ):
        raise FlintLinearWorkerError("FLINT_LINEAR_INPUT_INVALID")
    system = request["system"]
    if not isinstance(system, dict) or set(system) != {
        "system_schema_version",
        "domain",
        "relation",
        "variables",
        "coefficients",
        "rhs",
    }:
        raise FlintLinearWorkerError("FLINT_LINEAR_SYSTEM_INVALID")
    if (
        system["system_schema_version"] != "1"
        or system["domain"] != "QQ"
        or system["relation"] != "AX_EQUALS_B"
    ):
        raise FlintLinearWorkerError("FLINT_LINEAR_SYSTEM_INVALID")
    variables = system["variables"]
    if (
        not isinstance(variables, list)
        or not 1 <= len(variables) <= MAX_LINEAR_DIMENSION
        or any(
            not isinstance(variable, str) or _VARIABLE.fullmatch(variable) is None
            for variable in variables
        )
        or len(set(variables)) != len(variables)
    ):
        raise FlintLinearWorkerError("FLINT_LINEAR_SYSTEM_INVALID")
    matrix = system["coefficients"]
    if not isinstance(matrix, dict) or set(matrix) != {
        "matrix_schema_version",
        "domain",
        "entries",
    }:
        raise FlintLinearWorkerError("FLINT_LINEAR_SYSTEM_INVALID")
    if matrix["matrix_schema_version"] != "1" or matrix["domain"] != "QQ":
        raise FlintLinearWorkerError("FLINT_LINEAR_SYSTEM_INVALID")
    entries = matrix["entries"]
    rhs = system["rhs"]
    if (
        not isinstance(entries, list)
        or not isinstance(rhs, list)
        or not 1 <= len(entries) <= MAX_LINEAR_DIMENSION
        or len(entries) != len(rhs)
        or any(
            not isinstance(row, list) or len(row) != len(variables) for row in entries
        )
    ):
        raise FlintLinearWorkerError("FLINT_LINEAR_SYSTEM_INVALID")
    return (
        [[_rational(value) for value in row] for row in entries],
        [_rational(value) for value in rhs],
    )


def _run(request: dict[str, Any]) -> dict[str, object]:
    coefficients, rhs = _validate_system(request)
    try:
        flint: Any = importlib.import_module("flint")
        if getattr(flint, "__version__", None) != "0.9.0":
            raise FlintLinearWorkerError("FLINT_LINEAR_VERSION_MISMATCH")
        augmented = flint.fmpq_mat(
            [
                [flint.fmpq(value.numerator, value.denominator) for value in row]
                + [flint.fmpq(bound.numerator, bound.denominator)]
                for row, bound in zip(coefficients, rhs, strict=True)
            ]
        )
        reduced, _ = augmented.rref()
    except (AttributeError, ImportError, OSError, RuntimeError, TypeError) as exc:
        raise FlintLinearWorkerError("FLINT_LINEAR_EXECUTION_FAILED") from exc

    column_count = len(coefficients[0])
    values = [flint.fmpq(0) for _ in range(column_count)]
    for row_index in range(reduced.nrows()):
        pivot = next(
            (
                column
                for column in range(column_count)
                if reduced[row_index, column] != 0
            ),
            None,
        )
        if pivot is None:
            if reduced[row_index, column_count] != 0:
                return {
                    "status": "NO_SOLUTION_PRODUCED",
                    "backend_version": "0.9.0",
                }
            continue
        values[pivot] = reduced[row_index, column_count]

    return {
        "status": "SOLUTION_PRODUCED",
        "backend_version": "0.9.0",
        "values": [
            {"num": str(value.numerator), "den": str(value.denominator)}
            for value in values
        ],
    }


def main() -> int:
    try:
        result = _run(_read_request())
    except FlintLinearWorkerError as exc:
        _emit({"error_code": exc.code})
        return 2
    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
