"""Polynomial map operation declarations."""

from collections.abc import Callable
from typing import Any

from jacobian._models import StrictModel
from jacobian.catalog._examples import example
from jacobian.catalog.models import MathTool, OperationExample
from jacobian.math.polynomials.maps._models import (
    GenericDegreeRequest,
    GenericDegreeResult,
    JacobianResult,
)
from jacobian.math.polynomials.maps._operations import (
    compute_generic_degree,
    compute_jacobian,
)
from jacobian.math.polynomials.maps.values import RationalPolynomialMap


def _polynomial(
    variable: str,
    *terms: tuple[int, int],
) -> dict[str, Any]:
    return {
        "domain": "QQ",
        "variables": [variable],
        "polynomial": {
            "terms": [
                {
                    "coefficient": {"num": str(coefficient), "den": "1"},
                    "exponents": [exponent],
                }
                for coefficient, exponent in terms
            ]
        },
    }


def _bivariate_polynomial(*terms: tuple[int, tuple[int, int]]) -> dict[str, Any]:
    return {
        "domain": "QQ",
        "variables": ["x", "y"],
        "polynomial": {
            "terms": [
                {
                    "coefficient": {"num": str(coefficient), "den": "1"},
                    "exponents": list(exponents),
                }
                for coefficient, exponents in terms
            ]
        },
    }


def _op[
    RequestT: StrictModel,
    ResultT: StrictModel,
](
    operation_id: str,
    title: str,
    description: str,
    request_model: type[RequestT],
    result_model: type[ResultT],
    operation: Callable[[RequestT], ResultT],
    *tags: str,
    examples: tuple[OperationExample, ...] = (),
) -> MathTool[RequestT, ResultT]:
    return MathTool(
        operation_id=operation_id,
        title=title,
        description=description,
        request_type=request_model,
        result_type=result_model,
        run=operation,
        tags=tags,
        examples=examples,
    )


TOOLS: tuple[MathTool[Any, Any], ...] = (
    _op(
        "polynomial.map.generic_degree.compute",
        "Compute the exact generic degree of a polynomial map",
        "Classify the generic scheme-theoretic fiber of a bounded polynomial "
        "map over QQ and, when it is finite, return its exact quotient dimension "
        "with source-bound Groebner evidence. This computes over the generic "
        "target function field and never infers degree from a sampled fiber.",
        GenericDegreeRequest,
        GenericDegreeResult,
        compute_generic_degree,
        "polynomial",
        "algebraic-geometry",
        "generic-fiber",
        "exact",
        examples=(
            example(
                "quadratic_generic_degree",
                "Compute generic degree 2 for (x, y) -> (x^2, y); every map "
                "component must use the complete ordered source axis.",
                {
                    "polynomial_map": {
                        "input_variables": ["x", "y"],
                        "output_polynomials": [
                            _bivariate_polynomial((1, (2, 0))),
                            _bivariate_polynomial((1, (0, 1))),
                        ],
                    }
                },
            ),
        ),
    ),
    _op(
        "polynomial.map.jacobian",
        "Compute the Jacobian matrix of a polynomial map",
        "Compute the row-major Jacobian matrix of a canonical polynomial map.",
        RationalPolynomialMap,
        JacobianResult,
        compute_jacobian,
        "polynomial",
        "jacobian",
        "exact",
        examples=(
            example(
                "simple_jacobian",
                "Compute the Jacobian of [x^2, y^2] with respect to (x, y); "
                "every output must use that complete ordered axis.",
                {
                    "input_variables": ["x", "y"],
                    "output_polynomials": [
                        _bivariate_polynomial((1, (2, 0))),
                        _bivariate_polynomial((1, (0, 2))),
                    ],
                },
            ),
        ),
    ),
)


__all__ = ["TOOLS"]
