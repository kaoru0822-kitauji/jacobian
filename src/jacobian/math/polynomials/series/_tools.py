"""MathTool declarations for exact truncated formal power series operations."""

from __future__ import annotations

from jacobian.catalog._examples import example
from jacobian.catalog.models import MathTool
from jacobian.math.polynomials.series._models import (
    SeriesComposeRequest,
    SeriesComposeResult,
    SeriesDivideRequest,
    SeriesDivideResult,
    SeriesInverseRequest,
    SeriesInverseResult,
    SeriesMultiplyResult,
    SeriesPowerRequest,
    SeriesPowerResult,
    SeriesReversionRequest,
    SeriesReversionResult,
    _SeriesMultiplyRequest,
)
from jacobian.math.polynomials.series._operations import (
    compute_compose,
    compute_divide,
    compute_inverse,
    compute_multiply,
    compute_power,
    compute_reversion,
)

TOOLS = (
    MathTool(
        operation_id="formal_series.rational.multiply.compute",
        title="Multiply two truncated formal power series",
        description=(
            "Compute the exact Cauchy convolution of two truncated series in "
            "QQ[[x]]/(x^N).  Both operands must share the same variable and "
            "truncation order."
        ),
        request_type=_SeriesMultiplyRequest,
        result_type=SeriesMultiplyResult,
        run=lambda request: compute_multiply(request.left, request.right),
        tags=(
            "formal-series",
            "power-series",
            "arithmetic",
            "multiplication",
            "rational",
            "truncated",
            "exact",
        ),
        examples=(
            example(
                "multiply_1_plus_x",
                "Multiply (1+x) * (1+x) = 1+2x+x^2 at order 3.",
                {
                    "left": {
                        "variable": "x",
                        "truncation_order": 3,
                        "coefficients": [
                            {"num": "1", "den": "1"},
                            {"num": "1", "den": "1"},
                            {"num": "0", "den": "1"},
                        ],
                    },
                    "right": {
                        "variable": "x",
                        "truncation_order": 3,
                        "coefficients": [
                            {"num": "1", "den": "1"},
                            {"num": "1", "den": "1"},
                            {"num": "0", "den": "1"},
                        ],
                    },
                },
            ),
        ),
    ),
    MathTool(
        operation_id="formal_series.rational.power.compute",
        title="Raise a truncated formal power series to a nonnegative integer power",
        description=(
            "Compute the exact power of a truncated series in QQ[[x]]/(x^N) via "
            "binary exponentiation."
        ),
        request_type=SeriesPowerRequest,
        result_type=SeriesPowerResult,
        run=lambda request: compute_power(request.series, request.exponent),
        tags=(
            "formal-series",
            "power-series",
            "arithmetic",
            "power",
            "exponentiation",
            "rational",
            "truncated",
            "exact",
        ),
        examples=(
            example(
                "power_3_of_1_plus_x",
                "Compute (1+x)^3 at order 4.",
                {
                    "series": {
                        "variable": "x",
                        "truncation_order": 4,
                        "coefficients": [
                            {"num": "1", "den": "1"},
                            {"num": "1", "den": "1"},
                            {"num": "0", "den": "1"},
                            {"num": "0", "den": "1"},
                        ],
                    },
                    "exponent": 3,
                },
            ),
        ),
    ),
    MathTool(
        operation_id="formal_series.rational.inverse.compute",
        title="Invert a truncated formal power series",
        description=(
            "Compute the multiplicative inverse B(x) of A(x) modulo x^N, requiring "
            "a_0 != 0.  Returns the exact product residual A*B - 1."
        ),
        request_type=SeriesInverseRequest,
        result_type=SeriesInverseResult,
        run=lambda request: compute_inverse(request.as_series()),
        tags=(
            "formal-series",
            "power-series",
            "inverse",
            "unit",
            "rational",
            "truncated",
            "exact",
        ),
        examples=(
            example(
                "inverse_1_plus_x",
                "Invert (1+x) at order 4: 1-x+x^2-x^3.",
                {
                    "variable": "x",
                    "truncation_order": 4,
                    "coefficients": [
                        {"num": "1", "den": "1"},
                        {"num": "1", "den": "1"},
                        {"num": "0", "den": "1"},
                        {"num": "0", "den": "1"},
                    ],
                },
            ),
        ),
    ),
    MathTool(
        operation_id="formal_series.rational.divide.compute",
        title="Divide two truncated formal power series",
        description=(
            "Compute the exact quotient Q = A/B modulo x^N, requiring b_0 != 0. "
            "Returns the exact residual B*Q - A."
        ),
        request_type=SeriesDivideRequest,
        result_type=SeriesDivideResult,
        run=lambda request: compute_divide(request.left, request.right),
        tags=(
            "formal-series",
            "power-series",
            "division",
            "rational",
            "truncated",
            "exact",
        ),
        examples=(
            example(
                "divide_1_by_1_minus_x",
                "Divide 1 by (1-x) at order 4: 1+x+x^2+x^3.",
                {
                    "left": {
                        "variable": "x",
                        "truncation_order": 4,
                        "coefficients": [
                            {"num": "1", "den": "1"},
                            {"num": "0", "den": "1"},
                            {"num": "0", "den": "1"},
                            {"num": "0", "den": "1"},
                        ],
                    },
                    "right": {
                        "variable": "x",
                        "truncation_order": 4,
                        "coefficients": [
                            {"num": "1", "den": "1"},
                            {"num": "-1", "den": "1"},
                            {"num": "0", "den": "1"},
                            {"num": "0", "den": "1"},
                        ],
                    },
                },
            ),
        ),
    ),
    MathTool(
        operation_id="formal_series.rational.compose.compute",
        title="Compose two truncated formal power series",
        description=(
            "Compute the composition F(G(x)) mod x^N.  The inner series G must "
            "have zero constant term."
        ),
        request_type=SeriesComposeRequest,
        result_type=SeriesComposeResult,
        run=lambda request: compute_compose(request.outer, request.inner),
        tags=(
            "formal-series",
            "power-series",
            "composition",
            "rational",
            "truncated",
            "exact",
        ),
        examples=(
            example(
                "compose_x_with_x_squared",
                "Compose (1+x) with (x^2) at order 4: 1+x^2.",
                {
                    "outer": {
                        "variable": "x",
                        "truncation_order": 4,
                        "coefficients": [
                            {"num": "1", "den": "1"},
                            {"num": "1", "den": "1"},
                            {"num": "0", "den": "1"},
                            {"num": "0", "den": "1"},
                        ],
                    },
                    "inner": {
                        "variable": "x",
                        "truncation_order": 4,
                        "coefficients": [
                            {"num": "0", "den": "1"},
                            {"num": "0", "den": "1"},
                            {"num": "1", "den": "1"},
                            {"num": "0", "den": "1"},
                        ],
                    },
                },
            ),
        ),
    ),
    MathTool(
        operation_id="formal_series.rational.reversion.compute",
        title="Compositional inverse of a truncated formal power series",
        description=(
            "Compute the compositional inverse G(x) of F(x) mod x^N, requiring "
            "F(0)=0 and f_1 != 0.  Validates both left and right identities "
            "exactly."
        ),
        request_type=SeriesReversionRequest,
        result_type=SeriesReversionResult,
        run=lambda request: compute_reversion(request.as_series()),
        tags=(
            "formal-series",
            "power-series",
            "reversion",
            "compositional-inverse",
            "rational",
            "truncated",
            "exact",
        ),
        examples=(
            example(
                "reversion_of_2x",
                "Reversion of (2x) at order 4: (1/2)x.",
                {
                    "variable": "x",
                    "truncation_order": 4,
                    "coefficients": [
                        {"num": "0", "den": "1"},
                        {"num": "2", "den": "1"},
                        {"num": "0", "den": "1"},
                        {"num": "0", "den": "1"},
                    ],
                },
            ),
        ),
    ),
)


__all__ = ["TOOLS"]
