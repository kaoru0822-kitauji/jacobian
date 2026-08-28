"""Native admission and prepared kernels for exact recurrence operations."""

from __future__ import annotations

import math
from fractions import Fraction

from jacobian._exact import CanonicalRational
from jacobian.canonical import format_canonical_integer
from jacobian.math.combinatorics._recurrence_models import (
    MAX_COMBINATORICS_RESULT_ARTIFACT_BYTES,
    MAX_COMBINATORICS_RESULT_RATIONAL_DIGITS,
    _validate_result_inline_size,
)

_LOG10_2 = math.log10(2)
_FRACTION_WIRE_FIXED_BYTES = 20
_RESIDUAL_WIRE_FIXED_BYTES = 32
_RESULT_WIRE_FIXED_BYTES = 1_024


def _lower_decimal_digits(value: int) -> int:
    if value == 0:
        return 1
    return math.floor((abs(value).bit_length() - 1) * _LOG10_2) + 1


def _fraction_wire(value: Fraction) -> dict[str, str]:
    return {
        "num": format_canonical_integer(value.numerator),
        "den": format_canonical_integer(value.denominator),
    }


def _minimum_fraction_wire_bytes(value: Fraction) -> int:
    return (
        _lower_decimal_digits(value.numerator)
        + _lower_decimal_digits(value.denominator)
        + _FRACTION_WIRE_FIXED_BYTES
    )


def _require_bounded_fraction(value: Fraction, *, label: str) -> None:
    if any(
        _lower_decimal_digits(component) > MAX_COMBINATORICS_RESULT_RATIONAL_DIGITS
        for component in (value.numerator, value.denominator)
    ):
        raise ValueError(
            f"{label} exceeds the {MAX_COMBINATORICS_RESULT_RATIONAL_DIGITS}-digit bound"
        )


def _admit_linear_recurrence(
    *,
    coefficients: tuple[CanonicalRational, ...],
    initial_values: tuple[CanonicalRational, ...],
    coefficient_convention: str,
    scope: str,
    requested_indices: tuple[int, ...],
) -> tuple[Fraction, ...]:
    """Prepare the recurrence prefix while checking its exact result envelope."""

    replay = [
        value.as_fraction() for value in initial_values[: requested_indices[-1] + 1]
    ]
    coefficient_values = tuple(value.as_fraction() for value in coefficients)
    while len(replay) <= requested_indices[-1]:
        replay.append(
            sum(
                (
                    coefficient * replay[len(replay) - offset]
                    for offset, coefficient in enumerate(coefficient_values, start=1)
                ),
                start=Fraction(),
            )
        )
    minimum_size = sum(_minimum_fraction_wire_bytes(value) for value in replay)
    minimum_size += sum(
        _minimum_fraction_wire_bytes(replay[index]) for index in requested_indices
    )
    if minimum_size + _RESULT_WIRE_FIXED_BYTES > MAX_COMBINATORICS_RESULT_ARTIFACT_BYTES:
        raise ValueError("the exact combinatorics result exceeds the bounded result limit")
    for value in replay:
        _require_bounded_fraction(value, label="recurrence result")
    _validate_result_inline_size(
        {
            "coefficient_convention": coefficient_convention,
            "determinism": "DETERMINISTIC",
            "exactness": "EXACT_RATIONAL",
            "replay_prefix": [_fraction_wire(value) for value in replay],
            "replay_scope_end": requested_indices[-1],
            "scope": scope,
            "values": [
                {"index": index, "value": _fraction_wire(replay[index])}
                for index in requested_indices
            ],
        }
    )
    return tuple(replay)


def _admit_p_recursive_recurrence(
    *,
    coefficient_polynomials: tuple[tuple[CanonicalRational, ...], ...],
    initial_values: tuple[CanonicalRational, ...],
    coefficient_convention: str,
    polynomial_convention: str,
    scope: str,
    requested_indices: tuple[int, ...],
) -> tuple[tuple[Fraction, ...], tuple[tuple[int, Fraction], ...]]:
    """Prepare a P-recursive prefix and its exact residual ledger."""

    polynomials = tuple(
        tuple(value.as_fraction() for value in polynomial)
        for polynomial in coefficient_polynomials
    )
    order = len(polynomials) - 1

    def polynomial_value(polynomial: tuple[Fraction, ...], index: int) -> Fraction:
        return sum(
            (
                coefficient * index**power
                for power, coefficient in enumerate(polynomial)
            ),
            start=Fraction(),
        )

    end = requested_indices[-1]
    replay = [value.as_fraction() for value in initial_values[: end + 1]]
    requested_index_set = set(requested_indices)
    minimum_size = _RESULT_WIRE_FIXED_BYTES + sum(
        _minimum_fraction_wire_bytes(value) * (1 + (index in requested_index_set))
        for index, value in enumerate(replay)
    )
    residuals: list[tuple[int, Fraction]] = []
    while len(replay) <= end:
        index = len(replay)
        coefficients = tuple(
            polynomial_value(polynomial, index) for polynomial in polynomials
        )
        if coefficients[0] == 0:
            raise ValueError(f"leading coefficient polynomial vanishes at index {index}")
        next_value = (
            -sum(
                (
                    coefficients[offset] * replay[index - offset]
                    for offset in range(1, order + 1)
                ),
                start=Fraction(),
            )
            / coefficients[0]
        )
        _require_bounded_fraction(
            next_value,
            label="polynomial-coefficient recurrence result",
        )
        minimum_size += _minimum_fraction_wire_bytes(next_value) * (
            1 + (index in requested_index_set)
        )
        minimum_size += _RESIDUAL_WIRE_FIXED_BYTES
        if minimum_size > MAX_COMBINATORICS_RESULT_ARTIFACT_BYTES:
            raise ValueError("the exact combinatorics result exceeds the bounded result limit")
        replay.append(next_value)
        residuals.append(
            (
                index,
                sum(
                    (
                        coefficients[offset] * replay[index - offset]
                        for offset in range(order + 1)
                    ),
                    start=Fraction(),
                ),
            )
        )
    _validate_result_inline_size(
        {
            "coefficient_convention": coefficient_convention,
            "polynomial_convention": polynomial_convention,
            "determinism": "DETERMINISTIC",
            "exactness": "EXACT_RATIONAL",
            "recurrence_order": order,
            "replay_prefix": [_fraction_wire(value) for value in replay],
            "residuals": [
                {"index": index, "value": _fraction_wire(value)}
                for index, value in residuals
            ],
            "replay_scope_end": end,
            "scope": scope,
            "values": [
                {"index": index, "value": _fraction_wire(replay[index])}
                for index in requested_indices
            ],
        }
    )
    return tuple(replay), tuple(residuals)


def _admit_series(
    *,
    numerator: tuple[CanonicalRational, ...],
    denominator: tuple[CanonicalRational, ...],
    coefficient_convention: str,
    expansion_point: str,
    truncation_order: int,
) -> tuple[Fraction, ...]:
    """Prepare a rational-series prefix while checking its exact result envelope."""

    numerator_values = tuple(value.as_fraction() for value in numerator)
    denominator_values = tuple(value.as_fraction() for value in denominator)
    coefficients: list[Fraction] = []
    for degree in range(truncation_order):
        numerator_coefficient = (
            numerator_values[degree] if degree < len(numerator_values) else Fraction()
        )
        known = sum(
            (
                denominator_values[offset] * coefficients[degree - offset]
                for offset in range(1, min(degree, len(denominator_values) - 1) + 1)
            ),
            start=Fraction(),
        )
        coefficient = (numerator_coefficient - known) / denominator_values[0]
        _require_bounded_fraction(coefficient, label="series coefficient")
        coefficients.append(coefficient)
    minimum_size = sum(_minimum_fraction_wire_bytes(value) for value in coefficients)
    minimum_size += truncation_order * _minimum_fraction_wire_bytes(Fraction())
    if minimum_size + _RESULT_WIRE_FIXED_BYTES > MAX_COMBINATORICS_RESULT_ARTIFACT_BYTES:
        raise ValueError("the exact combinatorics result exceeds the bounded result limit")
    _validate_result_inline_size(
        {
            "coefficient_convention": coefficient_convention,
            "coefficients": [_fraction_wire(value) for value in coefficients],
            "determinism": "DETERMINISTIC",
            "exactness": "EXACT_RATIONAL",
            "expansion_point": expansion_point,
            "residual_coefficients": [_fraction_wire(Fraction())] * truncation_order,
            "residual_congruence": (
                "DENOMINATOR_TIMES_SERIES_MINUS_NUMERATOR_IS_ZERO_MOD_X_TO_ORDER"
            ),
            "truncation_order": truncation_order,
        }
    )
    return tuple(coefficients)


__all__ = [
    "_admit_linear_recurrence",
    "_admit_p_recursive_recurrence",
    "_admit_series",
]
