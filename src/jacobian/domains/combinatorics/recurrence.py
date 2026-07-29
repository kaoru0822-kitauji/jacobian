"""Recurrence-owned exact combinatorics capabilities."""

from jacobian.contracts.combinatorics import (
    FibonacciPairRequest,
    FibonacciPairResult,
    IntegerResult,
    NonnegativeIntegerRequest,
    RationalResult,
)
from jacobian.domains._examples import example
from jacobian.domains.combinatorics._support import (
    combinatorics_operation,
)
from jacobian.domains.combinatorics.operations import (
    bernoulli,
    fibonacci,
    fibonacci_pair,
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
        invocation_examples=(
            example("fibonacci_10", "Compute the tenth Fibonacci number.", {"n": 10}),
        ),
    ),
    combinatorics_operation(
        "combinatorics.compute.fibonacci_pair",
        "Compute consecutive Fibonacci values",
        "Return F_n and F_(n+1) as one exact recurrence boundary.",
        FibonacciPairRequest,
        FibonacciPairResult,
        fibonacci_pair,
        "combinatorics",
        "fibonacci",
        "recurrence-boundary",
        invocation_examples=(
            example(
                "fibonacci_pair_8",
                "Return consecutive Fibonacci values at n=8.",
                {"n": 8},
            ),
        ),
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
        invocation_examples=(
            example("lucas_7", "Compute the seventh Lucas number.", {"n": 7}),
        ),
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
        invocation_examples=(
            example("bernoulli_4", "Compute the fourth Bernoulli number.", {"n": 4}),
        ),
    ),
)
