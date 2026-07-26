"""Arithmetic operation declarations."""

from jacobian.operations import ComputedOperationFactory, OperationFailure

arithmetic_operation = ComputedOperationFactory(
    OperationFailure(
        code="ARITHMETIC_OPERATION_NOT_APPLICABLE",
        stage="arithmetic_computation",
        hint="Check the operation's exact-arithmetic preconditions.",
    )
)
