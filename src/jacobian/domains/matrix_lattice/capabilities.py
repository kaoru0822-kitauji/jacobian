"""Exact matrix capability declarations."""

from collections.abc import Callable
from typing import Any

from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.contracts.matrix_operations import (
    CharacteristicPolynomialResult,
    IntegerMatrixRequest,
    MatrixInverseResult,
    MatrixTraceResult,
    NullspaceResult,
    RationalMatrixRequest,
    RrefResult,
    SmithNormalFormResult,
    SquareRationalMatrixRequest,
)
from jacobian.contracts.results import ContractModel
from jacobian.domains.matrix_lattice.operations import (
    compute_characteristic_polynomial,
    compute_inverse,
    compute_nullspace,
    compute_rref,
    compute_smith_normal_form,
    compute_trace,
)
from jacobian.operations import (
    ComputedNotApplicable,
    ComputedOperation,
    ComputedOutcome,
    ComputedSuccess,
)


def matrix_operation(
    capability_id: str,
    title: str,
    description: str,
    request_model: type[ContractModel],
    result_model: type[ContractModel],
    operation: Callable[[Any], ContractModel],
    relation_id: str,
    *tags: str,
) -> ComputedOperation[Any, Any]:
    def implementation(request: ContractModel) -> ComputedOutcome[Any]:
        try:
            return ComputedSuccess(operation(request))
        except (ArithmeticError, TypeError, ValueError) as exc:
            return ComputedNotApplicable(
                CapabilityDiagnostic(
                    code="MATRIX_OPERATION_NOT_APPLICABLE",
                    stage="matrix_computation",
                    message=str(exc),
                    hint="Check the operation's matrix-domain and shape preconditions.",
                )
            )

    return ComputedOperation(
        capability_id=capability_id,
        title=title,
        description=description,
        request_model=request_model,
        result_model=result_model,
        implementation=implementation,
        relation_id=relation_id,
        tags=tags,
    )


MATRIX_CAPABILITIES = (
    matrix_operation(
        "matrix.inverse.compute",
        "Compute the exact inverse of an integer matrix",
        "Compute the rational two-sided inverse of a nonsingular square matrix.",
        IntegerMatrixRequest,
        MatrixInverseResult,
        compute_inverse,
        "matrix.relation.inverse-of",
        "matrix",
        "inverse",
        "exact-rational",
    ),
    matrix_operation(
        "matrix.trace.compute",
        "Compute the exact trace of an integer matrix",
        "Compute the sum of the diagonal entries of a square integer matrix.",
        IntegerMatrixRequest,
        MatrixTraceResult,
        compute_trace,
        "matrix.relation.trace-of",
        "matrix",
        "trace",
        "exact-integer",
    ),
    matrix_operation(
        "matrix.normal_form.rref.compute",
        "Compute exact reduced row echelon form",
        "Compute the unique reduced row echelon form over QQ.",
        RationalMatrixRequest,
        RrefResult,
        compute_rref,
        "matrix.relation.rref-of",
        "matrix",
        "rref",
        "exact-rational",
    ),
    matrix_operation(
        "matrix.nullspace.compute",
        "Compute a canonical exact nullspace basis",
        "Compute the RREF fundamental basis of the right nullspace over QQ.",
        RationalMatrixRequest,
        NullspaceResult,
        compute_nullspace,
        "matrix.relation.nullspace-of",
        "matrix",
        "nullspace",
        "exact-rational",
    ),
    matrix_operation(
        "matrix.characteristic_polynomial.compute",
        "Compute an exact characteristic polynomial",
        "Compute dense coefficients of det(lambda I - A) over QQ.",
        SquareRationalMatrixRequest,
        CharacteristicPolynomialResult,
        compute_characteristic_polynomial,
        "matrix.relation.characteristic-polynomial-of",
        "matrix",
        "characteristic-polynomial",
        "exact-rational",
    ),
    matrix_operation(
        "matrix.normal_form.smith.compute",
        "Compute an exact Smith normal form",
        (
            "Compute the canonical diagonal Smith form over ZZ without claiming "
            "unavailable left or right transformations."
        ),
        IntegerMatrixRequest,
        SmithNormalFormResult,
        compute_smith_normal_form,
        "matrix.relation.smith-normal-form-of",
        "matrix",
        "smith-normal-form",
        "exact-integer",
    ),
)
