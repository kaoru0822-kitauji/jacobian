"""Typed contracts owned by integer divisibility operations."""

from __future__ import annotations

from jacobian._models import StrictModel
from jacobian.math.number_theory._models import BoundedInteger


class IntegerPairRequest(StrictModel):
    """Two canonical integers supplied to a symmetric binary operation."""

    left: BoundedInteger
    right: BoundedInteger


class DivisibilityRequest(StrictModel):
    """A divisor and dividend supplied to a divisibility predicate."""

    divisor: BoundedInteger
    dividend: BoundedInteger


class ValuationRequest(StrictModel):
    """One integer and a prime base supplied to a p-adic valuation."""

    value: BoundedInteger
    prime: BoundedInteger


class ExtendedGcdResult(StrictModel):
    """A gcd together with exact Bezout coefficients."""

    gcd: BoundedInteger
    left_coefficient: BoundedInteger
    right_coefficient: BoundedInteger


__all__ = [
    "DivisibilityRequest",
    "ExtendedGcdResult",
    "IntegerPairRequest",
    "ValuationRequest",
]
