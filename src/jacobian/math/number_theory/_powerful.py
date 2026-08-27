"""Exact bounded powerful-number decision and declaration."""

from __future__ import annotations

from jacobian.canonical import parse_canonical_integer
from jacobian.catalog._examples import example
from jacobian.math.number_theory._powerful_kernels import decide_powerful_data
from jacobian.math.number_theory._powerful_models import (
    PowerfulNumberRequest,
    PowerfulNumberResult,
)
from jacobian.math.number_theory._support import number_theory_operation


def decide_powerful(request: PowerfulNumberRequest) -> PowerfulNumberResult:
    """Return the exact source-bound powerful-number decision."""

    data = decide_powerful_data(parse_canonical_integer(request.value))
    return PowerfulNumberResult._from_kernel(request, data=data)


POWERFUL_NUMBER_OPERATION = number_theory_operation(
    "integer.decide.powerful",
    "Decide powerful-number status",
    "Decide exactly whether every prime exponent of one positive integer is at "
    "least two. Trial division through the derived cutoff B=ceil(n^(1/5)) and "
    "exact perfect-power classification of the B-rough residual avoid complete "
    "factorization while returning a source-bound partial certificate.",
    PowerfulNumberRequest,
    PowerfulNumberResult,
    decide_powerful,
    "number-theory",
    "2-full",
    "powerful",
    "powerful-number",
    "predicate",
    "certificate",
    examples=(
        example(
            "powerful_12168",
            "Decide whether 12168 is powerful from a bounded partial-factor "
            "certificate; the value must be a positive canonical integer with "
            "at most 25 digits.",
            {"value": "12168"},
        ),
    ),
)
