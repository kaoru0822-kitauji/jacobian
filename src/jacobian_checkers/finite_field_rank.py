"""Independent SymPy replay for prime-field linear-map rank.

This checker parses the passive wire values itself. It does not import the
finite-field producer, its FLINT conversions, or Jacobian domain contracts.
"""

from __future__ import annotations

from typing import Any

from jacobian_checkers.bound_artifacts import bound_request

_MAX_DIMENSION = 256


def _reject(detail: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "conclusion": "UNKNOWN",
        "arithmetic": "EXACT_INTEGER",
        "method": "DIRECT_WITNESS",
        "coverage": "NOT_APPLICABLE",
        "detail": detail,
    }


def _matrix_rank(linear_map: object) -> int:
    if not isinstance(linear_map, dict) or set(linear_map) != {
        "source_axis",
        "target_axis",
        "matrix",
    }:
        raise ValueError("linear map is malformed")
    matrix = linear_map["matrix"]
    if not isinstance(matrix, dict) or set(matrix) != {
        "prime",
        "entries",
        "columns",
    }:
        raise ValueError("prime-field matrix is malformed")
    prime = matrix["prime"]
    columns = matrix["columns"]
    entries = matrix["entries"]
    if (
        type(prime) is not int
        or type(columns) is not int
        or not isinstance(entries, list)
        or not 0 <= columns <= _MAX_DIMENSION
        or len(entries) > _MAX_DIMENSION
        or any(
            not isinstance(row, list)
            or len(row) != columns
            or any(type(value) is not int or not 0 <= value < prime for value in row)
            for row in entries
        )
    ):
        raise ValueError("prime-field matrix exceeds its exact bounded shape")

    from sympy import GF, isprime
    from sympy.polys.matrices import DomainMatrix

    if not isprime(prime):
        raise ValueError("matrix modulus is not prime")
    if not entries or columns == 0:
        return 0
    return int(DomainMatrix(entries, (len(entries), columns), GF(prime)).rank())


def check_finite_field_linear_map_rank(request: dict[str, Any]) -> dict[str, Any]:
    claim, candidate = bound_request(
        request,
        operation_id="finite_field.linear_map.rank.compute",
        witness_format="finite-field.linear-map-rank.sympy-replay",
    )
    if set(claim) != {"direction", "linear_map"} or set(candidate) != {
        "direction",
        "linear_map",
        "rank",
    }:
        raise ValueError("rank relation is malformed")
    if (
        candidate["direction"] != claim["direction"]
        or candidate["linear_map"] != claim["linear_map"]
    ):
        return _reject("candidate is not bound to the supplied direction and map")
    expected = _matrix_rank(claim["linear_map"])
    if type(candidate["rank"]) is not int or candidate["rank"] != expected:
        return _reject("candidate rank does not match independent SymPy replay")
    return {
        "accepted": True,
        "conclusion": "TRUE",
        "arithmetic": "EXACT_INTEGER",
        "method": "DIRECT_WITNESS",
        "coverage": "NOT_APPLICABLE",
        "detail": "recomputed the exact rank over the bound prime field with SymPy",
    }


__all__ = ["check_finite_field_linear_map_rank"]
