"""Recurrence-owned exact combinatorics capabilities."""

from jacobian.contracts.combinatorics import (
    IntegerResult,
    NonnegativeIntegerRequest,
    RationalResult,
)
from jacobian.domains.combinatorics._support import (
    combinatorics_operation,
)
from jacobian.domains.combinatorics.operations import (
    bernoulli,
    fibonacci,
    lucas,
)

RECURRENCE_CAPABILITIES = (
    combinatorics_operation(
        "combinatorics.compute.fibonacci",
        "Compute Fibonacci number",
        "Compute the nth Fibonacci number exactly.",
        NonnegativeIntegerRequest,
        IntegerResult,
        fibonacci,
        "combinatorics",
        "sequence",
    ),
    combinatorics_operation(
        "combinatorics.compute.lucas",
        "Compute Lucas number",
        "Compute the nth Lucas number exactly.",
        NonnegativeIntegerRequest,
        IntegerResult,
        lucas,
        "combinatorics",
        "sequence",
    ),
    combinatorics_operation(
        "combinatorics.compute.bernoulli",
        "Compute Bernoulli number",
        "Compute the nth Bernoulli number as a reduced rational.",
        NonnegativeIntegerRequest,
        RationalResult,
        bernoulli,
        "combinatorics",
        "sequence",
    ),
)
