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

    prefix = [
        value.as_fraction() for value in initial_values[: requested_indices[-1] + 1]
    ]
    coefficient_values = tuple(value.as_fraction() for value in coefficients)
    while len(prefix) <= requested_indices[-1]:
        prefix.append(
            sum(
                (
                    coefficient * prefix[len(prefix) - offset]
                    for offset, coefficient in enumerate(coefficient_values, start=1)
                ),
                start=Fraction(),
            )
        )
    minimum_size = sum(
        _minimum_fraction_wire_bytes(prefix[index]) for index in requested_indices
    )
    if (
        minimum_size + _RESULT_WIRE_FIXED_BYTES
        > MAX_COMBINATORICS_RESULT_ARTIFACT_BYTES
    ):
        raise ValueError(
            "the exact combinatorics result exceeds the bounded result limit"
        )
    for value in prefix:
        _require_bounded_fraction(value, label="recurrence result")
    _validate_result_inline_size(
        {
            "coefficient_convention": coefficient_convention,
            "determinism": "DETERMINISTIC",
            "exactness": "EXACT_RATIONAL",
            "scope": scope,
            "values": [
                {"index": index, "value": _fraction_wire(prefix[index])}
                for index in requested_indices
            ],
        }
    )
    return tuple(prefix)


def _admit_p_recursive_recurrence(
    *,
    coefficient_polynomials: tuple[tuple[CanonicalRational, ...], ...],
    initial_values: tuple[CanonicalRational, ...],
    coefficient_convention: str,
    polynomial_convention: str,
    scope: str,
    requested_indices: tuple[int, ...],
) -> tuple[Fraction, ...]:
    """Prepare a P-recursive prefix and check the projected result envelope."""

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
    prefix = [value.as_fraction() for value in initial_values[: end + 1]]
    requested_index_set = set(requested_indices)
    minimum_size = _RESULT_WIRE_FIXED_BYTES + sum(
        _minimum_fraction_wire_bytes(value)
        for index, value in enumerate(prefix)
        if index in requested_index_set
    )
    while len(prefix) <= end:
        index = len(prefix)
        coefficients = tuple(
            polynomial_value(polynomial, index) for polynomial in polynomials
        )
        if coefficients[0] == 0:
            raise ValueError(
                f"leading coefficient polynomial vanishes at index {index}"
            )
        next_value = (
            -sum(
                (
                    coefficients[offset] * prefix[index - offset]
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
        if index in requested_index_set:
            minimum_size += _minimum_fraction_wire_bytes(next_value)
        if minimum_size > MAX_COMBINATORICS_RESULT_ARTIFACT_BYTES:
            raise ValueError(
                "the exact combinatorics result exceeds the bounded result limit"
            )
        prefix.append(next_value)
    _validate_result_inline_size(
        {
            "coefficient_convention": coefficient_convention,
            "polynomial_convention": polynomial_convention,
            "determinism": "DETERMINISTIC",
            "exactness": "EXACT_RATIONAL",
            "recurrence_order": order,
            "scope": scope,
            "values": [
                {"index": index, "value": _fraction_wire(prefix[index])}
                for index in requested_indices
            ],
        }
    )
    return tuple(prefix)


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
    if (
        minimum_size + _RESULT_WIRE_FIXED_BYTES
        > MAX_COMBINATORICS_RESULT_ARTIFACT_BYTES
    ):
        raise ValueError(
            "the exact combinatorics result exceeds the bounded result limit"
        )
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
