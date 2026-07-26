"""Polynomial operation declarations."""

from sympy.polys.polyerrors import PolynomialError

from jacobian.operations import ComputedOperationFactory, OperationFailure

polynomial_operation = ComputedOperationFactory(
    OperationFailure(
        code="POLYNOMIAL_OPERATION_NOT_APPLICABLE",
        stage="polynomial_computation",
        hint="Check the declared ring, variable, and operation budgets.",
        exceptions=(PolynomialError, TypeError, ValueError),
    )
)
