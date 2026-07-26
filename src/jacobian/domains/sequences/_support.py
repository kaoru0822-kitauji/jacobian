"""Sequence operation declarations."""

from jacobian.operations import ComputedOperationFactory, OperationFailure

sequence_operation = ComputedOperationFactory(
    OperationFailure(
        code="SEQUENCE_OPERATION_NOT_APPLICABLE",
        stage="sequence_computation",
        hint="Check the operation's sequence preconditions.",
        exceptions=(TypeError, ValueError, ArithmeticError),
    )
)
