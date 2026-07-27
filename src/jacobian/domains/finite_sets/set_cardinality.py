"""Finite-set cardinality capabilities."""

from jacobian.contracts.finite_sets import (
    FiniteSetCardinalityResult,
    FiniteSetPairRequest,
)
from jacobian.domains.finite_sets._support import finite_set_operation
from jacobian.domains.finite_sets.operations import (
    intersection_cardinality,
    left_cardinality,
    union_cardinality,
)

SET_CARDINALITY_CAPABILITIES = (
    finite_set_operation(
        "finite_set.compute.left_cardinality",
        "Count left finite set",
        "Count distinct elements in the left finite integer set.",
        FiniteSetPairRequest,
        FiniteSetCardinalityResult,
        left_cardinality,
        "finite-set",
        "counting",
    ),
    finite_set_operation(
        "finite_set.compute.intersection_cardinality",
        "Count set intersection",
        "Count common elements of two finite integer sets.",
        FiniteSetPairRequest,
        FiniteSetCardinalityResult,
        intersection_cardinality,
        "finite-set",
        "counting",
    ),
    finite_set_operation(
        "finite_set.compute.union_cardinality",
        "Count set union",
        "Count distinct elements occurring in either finite integer set.",
        FiniteSetPairRequest,
        FiniteSetCardinalityResult,
        union_cardinality,
        "finite-set",
        "counting",
    ),
)
