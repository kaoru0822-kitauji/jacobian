"""Independent exact checkers for finite integer-matrix evidence."""

from __future__ import annotations

import itertools
import re
from fractions import Fraction
from typing import Any

_INTEGER = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
MAX_ENUMERATED_MATRICES = 65_536


def _reject(
    detail: str,
    *,
    method: str = "DIRECT_WITNESS",
) -> dict[str, Any]:
    return {
        "accepted": False,
        "conclusion": "UNKNOWN",
        "arithmetic": "EXACT_RATIONAL",
        "method": method,
        "coverage": (
            "EXHAUSTIVE" if method == "EXHAUSTIVE_FINITE" else "NOT_APPLICABLE"
        ),
        "detail": detail,
    }


def check_kernel_vector(request: dict[str, Any]) -> dict[str, Any]:
    """Verify a nonzero rational vector lies in an integer matrix kernel."""

    try:
        if request.get("request_version") != "1":
            return _reject("unsupported request version")
        claim = _claim_view(request["claim"]["payload"])
        witness = request["witness"]["payload"]
        if claim.get("predicate") != "is_nonsingular":
            return _reject("unsupported claim predicate")
        if witness.get("witness_format") != "matrix.kernel_vector":
            return _reject("unexpected witness format")
        if witness.get("format_version") != "1":
            return _reject("unsupported witness format version")
        if witness.get("role") != "DEFEATS_CANDIDATE":
            return _reject("witness role does not defeat the candidate")
        if witness.get("bindings") != request["expected_bindings"]:
            return _reject("witness bindings do not match the request")
        matrix = _parse_matrix(request["candidate"]["payload"])
        if len(matrix) != len(matrix[0]):
            return _reject("nonsingularity requires a square matrix")
        vector_data = witness.get("payload", {}).get("vector")
        if not isinstance(vector_data, list):
            return _reject("kernel vector must be a list")
        vector = [_parse_rational(value) for value in vector_data]
        if len(vector) != len(matrix[0]):
            return _reject("kernel vector dimension does not match matrix")
        if all(value == 0 for value in vector):
            return _reject("kernel vector must be nonzero")
        for row in matrix:
            if (
                sum(
                    Fraction(coefficient) * value
                    for coefficient, value in zip(row, vector, strict=True)
                )
                != 0
            ):
                return _reject("vector is not in the matrix kernel")
        return {
            "accepted": True,
            "conclusion": "FALSE",
            "arithmetic": "EXACT_RATIONAL",
            "method": "DIRECT_WITNESS",
            "coverage": "NOT_APPLICABLE",
            "detail": "nonzero rational kernel vector replayed exactly",
        }
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return _reject("malformed checker request")


def check_row_major_transformation(
    request: dict[str, Any],
) -> dict[str, Any]:
    """Independently replay the matrix-to-row-major representation."""

    try:
        if request.get("request_version") != "1":
            return _reject(
                "unsupported request version",
                method="CHECKED_CERTIFICATE",
            )
        transformation = request["transformation"]["payload"]
        if transformation.get("transform_format") != "matrix.row_major":
            return _reject(
                "unexpected transformation format",
                method="CHECKED_CERTIFICATE",
            )
        if transformation.get("format_version") != "1":
            return _reject(
                "unsupported transformation version",
                method="CHECKED_CERTIFICATE",
            )
        if transformation.get("relation") != "EQUIVALENT":
            return _reject(
                "row-major checker only certifies equivalence",
                method="CHECKED_CERTIFICATE",
            )
        if transformation.get("bindings") != request["expected_bindings"]:
            return _reject(
                "transformation bindings do not match the request",
                method="CHECKED_CERTIFICATE",
            )

        matrix = _parse_matrix(request["source"]["payload"])
        target = request["target"]["payload"]
        if not isinstance(target, dict):
            raise ValueError("target must be an object")
        rows = target.get("rows")
        cols = target.get("cols")
        values = target.get("values")
        if (
            rows != len(matrix)
            or cols != len(matrix[0])
            or not isinstance(values, list)
        ):
            return _reject(
                "target dimensions do not match the source",
                method="CHECKED_CERTIFICATE",
            )
        expected = [value for row in matrix for value in row]
        actual = [_parse_integer(value) for value in values]
        if actual != expected:
            return _reject(
                "target values are not the source row-major entries",
                method="CHECKED_CERTIFICATE",
            )
        obligation = transformation.get("obligation")
        if obligation != {
            "kind": "row_major_bijection",
            "source_entry_count": len(expected),
            "target_value_count": len(actual),
        }:
            return _reject(
                "row-major obligation payload is invalid",
                method="CHECKED_CERTIFICATE",
            )
        return {
            "accepted": True,
            "conclusion": "TRUE",
            "arithmetic": "EXACT_INTEGER",
            "method": "CHECKED_CERTIFICATE",
            "coverage": "NOT_APPLICABLE",
            "detail": "row-major representation replayed entry by entry",
        }
    except (KeyError, TypeError, ValueError):
        return _reject(
            "malformed transformation request",
            method="CHECKED_CERTIFICATE",
        )


def check_maximizer_witness(request: dict[str, Any]) -> dict[str, Any]:
    """Exhaustively verify that a proposed matrix maximizes the scoped objective."""

    try:
        if request.get("request_version") != "1":
            return _reject(
                "unsupported request version",
                method="EXHAUSTIVE_FINITE",
            )
        claim = _claim_view(request["claim"]["payload"])
        witness = request["witness"]["payload"]
        if claim.get("predicate") != "maximize_absolute_determinant":
            return _reject(
                "unsupported claim predicate",
                method="EXHAUSTIVE_FINITE",
            )
        if witness.get("witness_format") != "matrix.maximizer":
            return _reject(
                "unexpected witness format",
                method="EXHAUSTIVE_FINITE",
            )
        if witness.get("format_version") != "1":
            return _reject(
                "unsupported witness format version",
                method="EXHAUSTIVE_FINITE",
            )
        if witness.get("role") != "SUPPORTS_CLAIM":
            return _reject(
                "witness role does not support the claim",
                method="EXHAUSTIVE_FINITE",
            )
        if witness.get("bindings") != request["expected_bindings"]:
            return _reject(
                "witness bindings do not match the request",
                method="EXHAUSTIVE_FINITE",
            )

        scope = claim.get("scope")
        rows, cols, values = _parse_scope(scope)
        if rows != cols:
            return _reject(
                "determinant scope must be square",
                method="EXHAUSTIVE_FINITE",
            )
        total = len(values) ** (rows * cols)
        if total > MAX_ENUMERATED_MATRICES:
            return _reject(
                "scope exceeds the independent checker limit",
                method="EXHAUSTIVE_FINITE",
            )

        inner = witness.get("payload")
        if not isinstance(inner, dict):
            return _reject(
                "maximizer witness payload is missing",
                method="EXHAUSTIVE_FINITE",
            )
        proposed = _parse_matrix(inner.get("matrix"))
        candidate = _parse_matrix(request["candidate"]["payload"])
        if len(candidate) != rows or len(candidate[0]) != cols:
            return _reject(
                "candidate dimensions do not match scope",
                method="EXHAUSTIVE_FINITE",
            )
        if any(entry not in values for row in candidate for entry in row):
            return _reject(
                "candidate entry is outside scope",
                method="EXHAUSTIVE_FINITE",
            )
        if len(proposed) != rows or len(proposed[0]) != cols:
            return _reject(
                "proposed matrix dimensions do not match scope",
                method="EXHAUSTIVE_FINITE",
            )
        if any(entry not in values for row in proposed for entry in row):
            return _reject(
                "proposed matrix entry is outside scope",
                method="EXHAUSTIVE_FINITE",
            )
        declared = _parse_rational(inner.get("objective_value"))
        if declared.denominator != 1:
            return _reject(
                "integer determinant objective must be integral",
                method="EXHAUSTIVE_FINITE",
            )

        maximum = -1
        for flat in itertools.product(values, repeat=rows * cols):
            matrix = [
                list(flat[index * cols : (index + 1) * cols]) for index in range(rows)
            ]
            maximum = max(maximum, abs(_determinant(matrix)))
        proposed_value = abs(_determinant(proposed))
        candidate_value = abs(_determinant(candidate))
        if (
            proposed_value != maximum
            or candidate_value != maximum
            or declared != maximum
        ):
            return _reject(
                "proposed matrix or bound candidate is not a scoped maximizer",
                method="EXHAUSTIVE_FINITE",
            )
        return {
            "accepted": True,
            "conclusion": "TRUE",
            "arithmetic": "EXACT_INTEGER",
            "method": "EXHAUSTIVE_FINITE",
            "coverage": "EXHAUSTIVE",
            "detail": f"replayed all {total} matrices in the declared scope",
        }
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return _reject(
            "malformed checker request",
            method="EXHAUSTIVE_FINITE",
        )


def check_maxdet_enumeration(request: dict[str, Any]) -> dict[str, Any]:
    """Exhaustively verify a bounded integer-matrix determinant maximum."""

    try:
        if request.get("request_version") != "1":
            return _reject(
                "unsupported request version",
                method="EXHAUSTIVE_FINITE",
            )
        claim = _claim_view(request["claim"]["payload"])
        certificate = request["certificate"]["payload"]
        if claim.get("predicate") != "maximize_absolute_determinant":
            return _reject(
                "unsupported claim predicate",
                method="EXHAUSTIVE_FINITE",
            )
        if certificate.get("certificate_type") != "matrix.maxdet_enumeration":
            return _reject(
                "unexpected certificate format",
                method="EXHAUSTIVE_FINITE",
            )
        if certificate.get("format_version") != "1":
            return _reject(
                "unsupported certificate version",
                method="EXHAUSTIVE_FINITE",
            )
        if certificate.get("bindings") != request["expected_bindings"]:
            return _reject(
                "certificate bindings do not match the request",
                method="EXHAUSTIVE_FINITE",
            )
        candidate = _parse_matrix(request["candidate"]["payload"])
        scope = claim.get("scope")
        rows, cols, values = _parse_scope(scope)
        if rows != cols:
            return _reject(
                "determinant scope must be square",
                method="EXHAUSTIVE_FINITE",
            )
        if len(candidate) != rows or len(candidate[0]) != cols:
            return _reject(
                "candidate dimensions do not match scope",
                method="EXHAUSTIVE_FINITE",
            )
        if any(entry not in values for row in candidate for entry in row):
            return _reject(
                "candidate entry is outside scope",
                method="EXHAUSTIVE_FINITE",
            )
        total = len(values) ** (rows * cols)
        if total > MAX_ENUMERATED_MATRICES:
            return _reject(
                "scope exceeds the independent checker limit",
                method="EXHAUSTIVE_FINITE",
            )
        inner = certificate.get("payload")
        if not isinstance(inner, dict):
            return _reject(
                "certificate payload is missing",
                method="EXHAUSTIVE_FINITE",
            )
        declared_maximum = _parse_rational(inner.get("maximum"))
        if declared_maximum.denominator != 1:
            return _reject(
                "integer determinant maximum must be integral",
                method="EXHAUSTIVE_FINITE",
            )
        maximum = -1
        for flat in itertools.product(values, repeat=rows * cols):
            matrix = [
                list(flat[index * cols : (index + 1) * cols]) for index in range(rows)
            ]
            maximum = max(maximum, abs(_determinant(matrix)))
        candidate_value = abs(_determinant(candidate))
        if maximum != declared_maximum or candidate_value != maximum:
            return _reject(
                "declared maximum or bound candidate is incorrect",
                method="EXHAUSTIVE_FINITE",
            )
        if inner.get("objects_checked") != total:
            return _reject(
                "certificate enumeration count is incorrect",
                method="EXHAUSTIVE_FINITE",
            )
        return {
            "accepted": True,
            "conclusion": "TRUE",
            "arithmetic": "EXACT_INTEGER",
            "method": "EXHAUSTIVE_FINITE",
            "coverage": "EXHAUSTIVE",
            "detail": f"replayed all {total} matrices in the declared scope",
        }
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return _reject(
            "malformed checker request",
            method="EXHAUSTIVE_FINITE",
        )


def check_singular_preservation(request: dict[str, Any]) -> dict[str, Any]:
    """Verify a reduced square integer matrix remains singular."""

    try:
        if request.get("request_version") != "1":
            return _reject(
                "unsupported request version",
                method="EXHAUSTIVE_FINITE",
            )
        claim = _claim_view(request["claim"]["payload"])
        evidence = request["preservation"]["payload"]
        if claim.get("predicate") != "is_nonsingular":
            return _reject(
                "unsupported claim predicate",
                method="EXHAUSTIVE_FINITE",
            )
        if evidence.get("preservation_format") != ("matrix.singular_preservation"):
            return _reject(
                "unexpected preservation format",
                method="EXHAUSTIVE_FINITE",
            )
        if evidence.get("format_version") != "1":
            return _reject(
                "unsupported preservation version",
                method="EXHAUSTIVE_FINITE",
            )
        if evidence.get("bindings") != request["expected_bindings"]:
            return _reject(
                "preservation bindings do not match the request",
                method="EXHAUSTIVE_FINITE",
            )
        matrix = _parse_matrix(request["reduced"]["payload"])
        if len(matrix) != len(matrix[0]):
            return _reject(
                "singularity preservation requires a square matrix",
                method="EXHAUSTIVE_FINITE",
            )
        if _determinant(matrix) != 0:
            return _reject(
                "reduced matrix is nonsingular",
                method="EXHAUSTIVE_FINITE",
            )
        return {
            "accepted": True,
            "conclusion": "FALSE",
            "arithmetic": "EXACT_INTEGER",
            "method": "EXHAUSTIVE_FINITE",
            "coverage": "EXHAUSTIVE",
            "detail": "reduced matrix singularity replayed exactly",
        }
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return _reject(
            "malformed checker request",
            method="EXHAUSTIVE_FINITE",
        )


def _claim_view(payload: dict[str, Any]) -> dict[str, Any]:
    predicate = payload.get("predicate")
    if not isinstance(predicate, dict):
        return payload
    parameters = predicate.get("parameters", {})
    bounds = payload.get("bounds", {})
    return {
        "predicate": predicate.get("name"),
        **(parameters if isinstance(parameters, dict) else {}),
        **(bounds if isinstance(bounds, dict) else {}),
    }


def _parse_integer(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and _INTEGER.fullmatch(value):
        return int(value)
    raise ValueError("invalid exact integer")


def _parse_rational(value: Any) -> Fraction:
    if not isinstance(value, dict) or set(value) != {"num", "den"}:
        raise ValueError("invalid rational object")
    numerator = value["num"]
    denominator = value["den"]
    if (
        not isinstance(numerator, str)
        or not isinstance(denominator, str)
        or not _INTEGER.fullmatch(numerator)
        or not _INTEGER.fullmatch(denominator)
    ):
        raise ValueError("invalid rational components")
    result = Fraction(int(numerator), int(denominator))
    if {"num": str(result.numerator), "den": str(result.denominator)} != value:
        raise ValueError("rational is not canonical")
    return result


def _parse_matrix(payload: Any) -> list[list[int]]:
    if not isinstance(payload, dict):
        raise ValueError("matrix must be an object")
    rows = payload.get("rows")
    cols = payload.get("cols")
    entries = payload.get("entries")
    if (
        not isinstance(rows, int)
        or isinstance(rows, bool)
        or rows < 1
        or not isinstance(cols, int)
        or isinstance(cols, bool)
        or cols < 1
        or not isinstance(entries, list)
        or len(entries) != rows
    ):
        raise ValueError("invalid matrix dimensions")
    matrix: list[list[int]] = []
    for row in entries:
        if not isinstance(row, list) or len(row) != cols:
            raise ValueError("matrix is not rectangular")
        matrix.append([_parse_integer(value) for value in row])
    return matrix


def _parse_scope(scope: Any) -> tuple[int, int, tuple[int, ...]]:
    if not isinstance(scope, dict):
        raise ValueError("matrix scope must be an object")
    rows = scope.get("rows")
    cols = scope.get("cols")
    raw_values = scope.get("entries")
    if (
        not isinstance(rows, int)
        or isinstance(rows, bool)
        or rows < 1
        or not isinstance(cols, int)
        or isinstance(cols, bool)
        or cols < 1
        or not isinstance(raw_values, list)
        or not raw_values
    ):
        raise ValueError("invalid matrix scope")
    values = tuple(_parse_integer(value) for value in raw_values)
    if len(values) != len(set(values)):
        raise ValueError("scope values must be unique")
    return rows, cols, values


def _determinant(matrix: list[list[int]]) -> int:
    """Bareiss fraction-free determinant for square integer matrices."""

    size = len(matrix)
    if any(len(row) != size for row in matrix):
        raise ValueError("determinant requires a square matrix")
    if size == 1:
        return matrix[0][0]
    work = [row[:] for row in matrix]
    sign = 1
    previous = 1
    for pivot_index in range(size - 1):
        pivot_row = next(
            (row for row in range(pivot_index, size) if work[row][pivot_index] != 0),
            None,
        )
        if pivot_row is None:
            return 0
        if pivot_row != pivot_index:
            work[pivot_index], work[pivot_row] = (
                work[pivot_row],
                work[pivot_index],
            )
            sign *= -1
        pivot = work[pivot_index][pivot_index]
        for row in range(pivot_index + 1, size):
            for column in range(pivot_index + 1, size):
                numerator = (
                    work[row][column] * pivot
                    - work[row][pivot_index] * work[pivot_index][column]
                )
                work[row][column] = numerator // previous
        previous = pivot
    return sign * work[-1][-1]
