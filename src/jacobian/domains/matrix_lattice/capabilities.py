"""Exact matrix capability declarations."""

from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.contracts.matrix_operations import (
    CharacteristicPolynomialResult,
    IntegerMatrixRequest,
    MatrixAdjugateResult,
    MatrixInverseResult,
    MatrixTraceResult,
    NullspaceResult,
    RationalLinearSolveRequest,
    RationalLinearSolveResult,
    RationalMatrixRequest,
    RrefResult,
    SmithNormalFormResult,
    SquareIntegerMatrixRequest,
    SquareRationalMatrixRequest,
)
from jacobian.contracts.results import ContractModel, ExecutionStatus
from jacobian.domains.matrix_lattice.operations import (
    compute_adjugate,
    compute_characteristic_polynomial,
    compute_inverse,
    compute_nullspace,
    compute_rational_linear_solve,
    compute_rref,
    compute_smith_normal_form,
    compute_trace,
)
from jacobian.operations import (
    ComputedNotApplicable,
    ComputedOperation,
    ComputedOutcome,
    ComputedSuccess,
    OperationExecutionFailure,
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
        except ValidationError as exc:
            return OperationExecutionFailure(
                status=ExecutionStatus.ERROR,
                diagnostic=CapabilityDiagnostic(
                    code="MATRIX_OUTPUT_LIMIT_EXCEEDED",
                    stage="matrix_result_validation",
                    message=(
                        "The exact matrix result exceeded its bounded output "
                        f"contract: {exc}"
                    ),
                    hint=(
                        "Reduce the matrix dimension or scalar size; no result "
                        "artifact was retained."
                    ),
                ),
            )
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
        "matrix.rational_linear_system.solve",
        "Solve an exact rational linear system",
        "Compute the unique solution to a bounded square system Ax=b over QQ.",
        RationalLinearSolveRequest,
        RationalLinearSolveResult,
        compute_rational_linear_solve,
        "matrix.relation.solution-of",
        "matrix",
        "linear-system",
        "exact-rational",
    ),
    matrix_operation(
        "matrix.adjugate.compute",
        "Compute an exact matrix adjugate",
        "Compute the classical adjugate of a square integer matrix.",
        SquareIntegerMatrixRequest,
        MatrixAdjugateResult,
        compute_adjugate,
        "matrix.relation.adjugate-of",
        "matrix",
        "adjugate",
        "exact-integer",
    ),
    matrix_operation(
        "matrix.inverse.compute",
        "Compute the exact inverse of an integer matrix",
        "Compute the rational two-sided inverse of a nonsingular square matrix.",
        SquareIntegerMatrixRequest,
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
        SquareIntegerMatrixRequest,
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
