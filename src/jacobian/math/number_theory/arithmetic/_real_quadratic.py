"""Typed real-quadratic order operation and checker declaration."""

from __future__ import annotations

from jacobian._models import StrictModel
from jacobian.catalog._examples import example
from jacobian.math.number_theory.algebraic_numbers.quadratic import (
    RealQuadraticOrderValue,
    RealQuadraticValue,
    real_quadratic_order,
)
from jacobian.math.number_theory.arithmetic._support import arithmetic_operation


class RealQuadraticOrderRequest(StrictModel):
    """One bounded comparison in a shared real quadratic field."""

    left: RealQuadraticValue
    right: RealQuadraticValue


def _compute_real_quadratic_order(
    request: RealQuadraticOrderRequest,
) -> RealQuadraticOrderValue:
    """Project the wire request onto the native canonical-value kernel."""

    return real_quadratic_order(request.left, request.right)


REAL_QUADRATIC_OPERATIONS = (
    arithmetic_operation(
        "arithmetic.real_quadratic.order.compute",
        "Compare exact real quadratic values",
        (
            "Compare two bounded values a+b*sqrt(d) in one shared real quadratic "
            "field, returning their exact difference and squared-magnitude sign data."
        ),
        RealQuadraticOrderRequest,
        RealQuadraticOrderValue,
        _compute_real_quadratic_order,
        "arithmetic",
        "real-quadratic",
        "quadratic-surd",
        "exact-order",
        examples=(
            example(
                "pang_m4_scalar_gap",
                "Compare 3*sqrt(3)/8 with 1/2+sqrt(3)/20 exactly.",
                {
                    "left": {
                        "rational_part": {"num": "0", "den": "1"},
                        "radical_coefficient": {"num": "3", "den": "8"},
                        "radicand": 3,
                    },
                    "right": {
                        "rational_part": {"num": "1", "den": "2"},
                        "radical_coefficient": {"num": "1", "den": "20"},
                        "radicand": 3,
                    },
                },
            ),
        ),
    ),
)

__all__ = ["REAL_QUADRATIC_OPERATIONS"]
