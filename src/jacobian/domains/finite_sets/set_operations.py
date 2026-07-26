"""Binary set-operation capabilities over finite integer sets."""

from jacobian.contracts.finite_sets import (
    FiniteSetElementListResult,
    FiniteSetPairRequest,
)
from jacobian.domains.finite_sets._support import finite_set_operation
from jacobian.domains.finite_sets.operations import (
    set_difference,
    set_intersection,
    set_symmetric_difference,
    set_union,
)

SET_OPERATION_CAPABILITIES = (
    finite_set_operation(
        "finite_set.compute.union",
        "Compute finite-set union",
        "Return the sorted union of two finite integer sets.",
        FiniteSetPairRequest,
        FiniteSetElementListResult,
        set_union,
        "finite-set",
        "exact",
    ),
    finite_set_operation(
        "finite_set.compute.intersection",
        "Compute finite-set intersection",
        "Return the sorted intersection of two finite integer sets.",
        FiniteSetPairRequest,
        FiniteSetElementListResult,
        set_intersection,
        "finite-set",
        "exact",
    ),
    finite_set_operation(
        "finite_set.compute.difference",
        "Compute finite-set difference",
        "Return elements in the first finite set but not the second.",
        FiniteSetPairRequest,
        FiniteSetElementListResult,
        set_difference,
        "finite-set",
        "exact",
    ),
    finite_set_operation(
        "finite_set.compute.symmetric_difference",
        "Compute symmetric difference",
        "Return elements occurring in exactly one of two finite integer sets.",
        FiniteSetPairRequest,
        FiniteSetElementListResult,
        set_symmetric_difference,
        "finite-set",
        "exact",
    ),
)
