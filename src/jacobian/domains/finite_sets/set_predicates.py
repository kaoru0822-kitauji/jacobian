"""Finite-set predicate capabilities."""

from jacobian.contracts.finite_sets import (
    FiniteSetBooleanResult,
    FiniteSetPairRequest,
)
from jacobian.domains.finite_sets._support import finite_set_operation
from jacobian.domains.finite_sets.operations import (
    decide_disjoint,
    decide_proper_subset,
    decide_subset,
)

SET_PREDICATE_CAPABILITIES = (
    finite_set_operation(
        "finite_set.decide.subset",
        "Decide subset relation",
        "Decide whether every left-set element occurs in the right set.",
        FiniteSetPairRequest,
        FiniteSetBooleanResult,
        decide_subset,
        "finite-set",
        "predicate",
    ),
    finite_set_operation(
        "finite_set.decide.proper_subset",
        "Decide proper subset",
        "Decide whether the left set is a strict subset of the right set.",
        FiniteSetPairRequest,
        FiniteSetBooleanResult,
        decide_proper_subset,
        "finite-set",
        "predicate",
    ),
    finite_set_operation(
        "finite_set.decide.disjoint",
        "Decide disjointness",
        "Decide whether two finite integer sets have empty intersection.",
        FiniteSetPairRequest,
        FiniteSetBooleanResult,
        decide_disjoint,
        "finite-set",
        "predicate",
    ),
)
