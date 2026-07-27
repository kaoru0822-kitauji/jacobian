"""Number-theory operation declarations."""

from jacobian.operations import ComputedOperationFactory, OperationFailure

number_theory_operation = ComputedOperationFactory(
    OperationFailure(
        code="NUMBER_THEORY_OPERATION_NOT_APPLICABLE",
        stage="number_theory_computation",
        hint="Check divisibility, positivity, primality, and modular preconditions.",
    )
)
