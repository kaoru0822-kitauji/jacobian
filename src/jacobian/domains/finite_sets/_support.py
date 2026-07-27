"""Finite-set operation declarations."""

from jacobian.operations import ComputedOperationFactory, OperationFailure

finite_set_operation = ComputedOperationFactory(
    OperationFailure(
        code="FINITE_SET_OPERATION_NOT_APPLICABLE",
        stage="finite_set_computation",
        hint="Check the operation's finite-set preconditions.",
    )
)
