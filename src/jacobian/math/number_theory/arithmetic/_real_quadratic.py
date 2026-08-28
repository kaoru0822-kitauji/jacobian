"""Typed real-quadratic order operation and checker declaration."""

from __future__ import annotations

from pydantic import Field

from jacobian._models import StrictModel
from jacobian.catalog._examples import example
from jacobian.math.number_theory.algebraic_numbers.quadratic import (
    _MAX_EMBEDDING_PROFILE_RESULT_DIGITS,
    RealQuadraticEmbeddingProfile,
    RealQuadraticOrderValue,
    RealQuadraticValue,
    real_quadratic_embeddings,
    real_quadratic_order,
)
from jacobian.math.number_theory.arithmetic._support import arithmetic_operation


class RealQuadraticEmbeddingsRequest(StrictModel):
    """One bounded element whose two real embeddings are requested."""

    element: RealQuadraticValue = Field(
        description=(
            "The exact element a + b*sqrt(d) in a real quadratic field. "
            "Its square-free radicand selects the field and its rational "
            "components are bounded to 256 decimal digits."
        ),
    )


class RealQuadraticOrderRequest(StrictModel):
    """One bounded comparison in a shared real quadratic field."""

    left: RealQuadraticValue
    right: RealQuadraticValue


def _compute_real_quadratic_embeddings(
    request: RealQuadraticEmbeddingsRequest,
) -> RealQuadraticEmbeddingProfile:
    return real_quadratic_embeddings(request.element)


def _compute_real_quadratic_order(
    request: RealQuadraticOrderRequest,
) -> RealQuadraticOrderValue:
    """Project the wire request onto the native canonical-value kernel."""

    return real_quadratic_order(request.left, request.right)


REAL_QUADRATIC_OPERATIONS = (
    arithmetic_operation(
        "arithmetic.real_quadratic.embeddings.compute",
        "Compute all exact embeddings of a real quadratic element",
        (
            "Return the two ordered exact real embedding images of "
            "a+b*sqrt(d), along with its exact trace and norm. Images retain "
            "the source and explicitly identify the maps sqrt(d) -> +sqrt(d) "
            "and sqrt(d) -> -sqrt(d); the profile is available only for a "
            "square-free positive radicand with 256-digit input components and "
            f"a trace and norm within the {_MAX_EMBEDDING_PROFILE_RESULT_DIGITS:,}-digit result bound."
        ),
        RealQuadraticEmbeddingsRequest,
        RealQuadraticEmbeddingProfile,
        _compute_real_quadratic_embeddings,
        "arithmetic",
        "real-quadratic",
        "number-field",
        "embedding",
        "trace",
        "norm",
        "exact",
        examples=(
            example(
                "sqrt2_embedding_profile",
                "Compute both exact embeddings, trace, and norm of 1+sqrt(2). "
                "The radicand must be positive and square-free, and the derived "
                f"trace and norm must fit the {_MAX_EMBEDDING_PROFILE_RESULT_DIGITS:,}-digit result bound.",
                {
                    "element": {
                        "rational_part": {"num": "1", "den": "1"},
                        "radical_coefficient": {"num": "1", "den": "1"},
                        "radicand": 2,
                    }
                },
            ),
        ),
    ),
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
