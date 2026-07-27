"""Combinatorics operation declarations."""

from jacobian.operations import ComputedOperationFactory, OperationFailure

combinatorics_operation = ComputedOperationFactory(
    OperationFailure(
        code="COMBINATORICS_OPERATION_NOT_APPLICABLE",
        stage="combinatorics_computation",
        hint="Check non-negativity and ordering preconditions.",
        exceptions=(TypeError, ValueError, ArithmeticError),
    )
)
