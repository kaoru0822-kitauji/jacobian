"""Independent real-quadratic order replay using only the standard library.

This module imports neither SymPy nor the arithmetic producer and accepts only
passive artifact-bound JSON from the exact replay protocol.
"""

from __future__ import annotations

import math
import re
from fractions import Fraction
from typing import Any, Literal

from jacobian_checkers.bound_artifacts import bound_request

_INTEGER = re.compile(r"^(?:0|-?[1-9][0-9]*)$")
_MAX_DIGITS = 256
_MAX_RADICAND = 1_000_000
_OPERATION_ID = "arithmetic.real_quadratic.order.compute"
_WITNESS_FORMAT = "arithmetic.real-quadratic-order.fraction-square-replay"


def _reject(detail: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "conclusion": "UNKNOWN",
        "arithmetic": "EXACT_RATIONAL",
        "method": "DIRECT_WITNESS",
        "coverage": "NOT_APPLICABLE",
        "detail": detail,
    }


def _accept() -> dict[str, Any]:
    return {
        "accepted": True,
        "conclusion": "TRUE",
        "arithmetic": "EXACT_RATIONAL",
        "method": "DIRECT_WITNESS",
        "coverage": "NOT_APPLICABLE",
        "detail": "independent exact real-quadratic order replay accepted the result",
    }


def _rational(value: object) -> Fraction:
    if not isinstance(value, dict) or set(value) != {"num", "den"}:
        raise ValueError("rational is malformed")
    numerator = value["num"]
    denominator = value["den"]
    if (
        not isinstance(numerator, str)
        or not isinstance(denominator, str)
        or len(numerator.lstrip("-")) > _MAX_DIGITS
        or len(denominator.lstrip("-")) > _MAX_DIGITS
        or _INTEGER.fullmatch(numerator) is None
        or _INTEGER.fullmatch(denominator) is None
    ):
        raise ValueError("rational is outside checker bounds")
    parsed = Fraction(int(numerator), int(denominator))
    if str(parsed.numerator) != numerator or str(parsed.denominator) != denominator:
        raise ValueError("rational is not canonical")
    return parsed


def _square_free(value: int) -> bool:
    return all(
        value % (divisor * divisor) for divisor in range(2, math.isqrt(value) + 1)
    )


def _value(value: object) -> tuple[Fraction, Fraction, int]:
    if not isinstance(value, dict) or set(value) != {
        "rational_part",
        "radical_coefficient",
        "radicand",
    }:
        raise ValueError("real-quadratic value is malformed")
    radicand = value["radicand"]
    if (
        type(radicand) is not int
        or not 2 <= radicand <= _MAX_RADICAND
        or not _square_free(radicand)
    ):
        raise ValueError("real-quadratic radicand is outside checker scope")
    return (
        _rational(value["rational_part"]),
        _rational(value["radical_coefficient"]),
        radicand,
    )


def _wire_rational(value: Fraction) -> dict[str, str]:
    return {"num": str(value.numerator), "den": str(value.denominator)}


def _wire_value(a: Fraction, b: Fraction, d: int) -> dict[str, object]:
    return {
        "rational_part": _wire_rational(a),
        "radical_coefficient": _wire_rational(b),
        "radicand": d,
    }


def _order(left: Fraction, right: Fraction) -> Literal["LT", "EQ", "GT"]:
    if left < right:
        return "LT"
    if left > right:
        return "GT"
    return "EQ"


def _sign(a: Fraction, b: Fraction, d: int) -> int:
    if b == 0:
        return -1 if a < 0 else 1 if a > 0 else 0
    if a == 0:
        return -1 if b < 0 else 1
    if (a > 0) == (b > 0):
        return -1 if a < 0 else 1
    rational_square = a * a
    radical_square = b * b * d
    if rational_square == radical_square:
        raise ValueError("square-free quadratic magnitudes cannot tie")
    dominant = b if radical_square > rational_square else a
    return -1 if dominant < 0 else 1


def _expected(source: dict[str, Any]) -> dict[str, Any]:
    if set(source) != {"left", "right"}:
        raise ValueError("real-quadratic request is malformed")
    left_a, left_b, left_d = _value(source["left"])
    right_a, right_b, right_d = _value(source["right"])
    if left_d != right_d:
        raise ValueError("comparison values do not share a radicand")
    difference_a = left_a - right_a
    difference_b = left_b - right_b
    sign = _sign(difference_a, difference_b, left_d)
    rational_square = difference_a * difference_a
    radical_square = difference_b * difference_b * left_d
    basis = (
        "RATIONAL_ONLY"
        if difference_b == 0
        else "RADICAL_ONLY"
        if difference_a == 0
        else "SAME_SIGN"
        if (difference_a > 0) == (difference_b > 0)
        else "OPPOSING_SIGNS_SQUARED_MAGNITUDES"
    )
    return {
        "result_schema_version": "1",
        "left": source["left"],
        "right": source["right"],
        "difference": _wire_value(difference_a, difference_b, left_d),
        "order": "LT" if sign < 0 else "GT" if sign > 0 else "EQ",
        "sign_basis": basis,
        "sign_certificate": {
            "rational_part_squared": _wire_rational(rational_square),
            "radical_part_squared": _wire_rational(radical_square),
            "magnitude_order": _order(rational_square, radical_square),
        },
        "arithmetic": "EXACT_REAL_QUADRATIC",
    }


def check_real_quadratic_order(request: object) -> dict[str, Any]:
    try:
        source, candidate = bound_request(
            request,
            operation_id=_OPERATION_ID,
            witness_format=_WITNESS_FORMAT,
        )
        if candidate != _expected(source):
            return _reject(
                "declared order does not match independent real-quadratic replay"
            )
        return _accept()
    except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError):
        return _reject("malformed, unsupported, or mismatched checker request")


__all__ = ["check_real_quadratic_order"]
