"""Geometry operation declarations."""

from jacobian.operations import ComputedOperationFactory, OperationFailure

geometry_operation = ComputedOperationFactory(
    OperationFailure(
        code="GEOMETRY_OPERATION_NOT_APPLICABLE",
        stage="geometry_computation",
        hint="Check the operation's nondegeneracy preconditions.",
    )
)
