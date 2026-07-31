"""Isolated Python-FLINT worker for integer row Hermite normal form."""

from __future__ import annotations

import importlib
import re
import sys
from typing import Any

from jacobian.canonical import (
    CanonicalizationError,
    canonicalize_json,
    loads_strict_json,
)

FLINT_HNF_WORKER_PROTOCOL = "jacobian.flint-hnf-worker/v1"
FLINT_HNF_INPUT_LIMIT = 1_000_000
MAX_MATRIX_DIMENSION = 32
MAX_INTEGER_DIGITS = 256
_INTEGER = re.compile(r"^-?(?:0|[1-9][0-9]*)$")


class FlintHnfWorkerError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _emit(payload: dict[str, object]) -> None:
    sys.stdout.buffer.write(
        canonicalize_json({"protocol": FLINT_HNF_WORKER_PROTOCOL, **payload}) + b"\n"
    )
    sys.stdout.flush()


def _read_request() -> dict[str, Any]:
    encoded = sys.stdin.buffer.read(FLINT_HNF_INPUT_LIMIT + 1)
    if len(encoded) > FLINT_HNF_INPUT_LIMIT:
        raise FlintHnfWorkerError("FLINT_HNF_INPUT_LIMIT_EXCEEDED")
    try:
        payload = loads_strict_json(encoded)
    except CanonicalizationError as exc:
        raise FlintHnfWorkerError("FLINT_HNF_INPUT_INVALID") from exc
    if not isinstance(payload, dict):
        raise FlintHnfWorkerError("FLINT_HNF_INPUT_INVALID")
    return payload


def _integer(value: object) -> int:
    if (
        not isinstance(value, str)
        or _INTEGER.fullmatch(value) is None
        or len(value.lstrip("-")) > MAX_INTEGER_DIGITS
    ):
        raise FlintHnfWorkerError("FLINT_HNF_MATRIX_INVALID")
    result = int(value)
    if str(result) != value:
        raise FlintHnfWorkerError("FLINT_HNF_MATRIX_INVALID")
    return result


def _validate_matrix(request: dict[str, Any]) -> list[list[int]]:
    if (
        set(request) != {"protocol", "matrix"}
        or request.get("protocol") != FLINT_HNF_WORKER_PROTOCOL
    ):
        raise FlintHnfWorkerError("FLINT_HNF_INPUT_INVALID")
    matrix = request["matrix"]
    if not isinstance(matrix, dict) or set(matrix) != {
        "matrix_schema_version",
        "domain",
        "entries",
    }:
        raise FlintHnfWorkerError("FLINT_HNF_MATRIX_INVALID")
    if matrix["matrix_schema_version"] != "1" or matrix["domain"] != "ZZ":
        raise FlintHnfWorkerError("FLINT_HNF_MATRIX_INVALID")
    entries = matrix["entries"]
    if (
        not isinstance(entries, list)
        or not 1 <= len(entries) <= MAX_MATRIX_DIMENSION
        or not isinstance(entries[0], list)
        or not 1 <= len(entries[0]) <= MAX_MATRIX_DIMENSION
        or any(
            not isinstance(row, list) or len(row) != len(entries[0]) for row in entries
        )
    ):
        raise FlintHnfWorkerError("FLINT_HNF_MATRIX_INVALID")
    return [[_integer(value) for value in row] for row in entries]


def _wire_matrix(matrix: Any) -> list[list[str]]:
    entries = [
        [str(matrix[row, column]) for column in range(matrix.ncols())]
        for row in range(matrix.nrows())
    ]
    if any(
        _INTEGER.fullmatch(value) is None or len(value.lstrip("-")) > MAX_INTEGER_DIGITS
        for row in entries
        for value in row
    ):
        raise FlintHnfWorkerError("FLINT_HNF_OUTPUT_LIMIT_EXCEEDED")
    return entries


def _run(request: dict[str, Any]) -> dict[str, object]:
    entries = _validate_matrix(request)
    try:
        flint: Any = importlib.import_module("flint")
        if getattr(flint, "__version__", None) != "0.9.0":
            raise FlintHnfWorkerError("FLINT_HNF_VERSION_MISMATCH")
        if getattr(flint, "__FLINT_VERSION__", None) != "3.6.0":
            raise FlintHnfWorkerError("FLINT_HNF_LIBRARY_VERSION_MISMATCH")
        matrix = flint.fmpz_mat(entries)
        normal_form, transformation = matrix.hnf(transform=True)
    except FlintHnfWorkerError:
        raise
    except (
        AttributeError,
        ImportError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        raise FlintHnfWorkerError("FLINT_HNF_EXECUTION_FAILED") from exc
    return {
        "status": "NORMAL_FORM_PRODUCED",
        "backend_version": "0.9.0",
        "flint_library_version": "3.6.0",
        "normal_form": _wire_matrix(normal_form),
        "transformation": _wire_matrix(transformation),
    }


def main() -> int:
    try:
        result = _run(_read_request())
    except FlintHnfWorkerError as exc:
        _emit({"error_code": exc.code})
        return 2
    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
