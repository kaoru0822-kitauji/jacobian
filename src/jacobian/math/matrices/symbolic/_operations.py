"""Domain-owned symbolic matrix operations."""

from __future__ import annotations

from typing import Literal, cast

from pydantic_core import PydanticCustomError
from sympy.matrices.exceptions import MatrixError

from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.matrices.symbolic import (
    symbolic_characteristic_polynomial,
    symbolic_determinant,
    symbolic_eigenvalues,
    symbolic_matrix_multiply,
    symbolic_rank,
)
from jacobian.math.matrices.symbolic._models import (
    SymbolicCharacteristicPolynomialRequest,
    SymbolicCharacteristicPolynomialResult,
    SymbolicDeterminantRequest,
    SymbolicDeterminantResult,
    SymbolicEigenvaluesResult,
    SymbolicLinearSystemRequest,
    SymbolicLinearSystemResult,
    SymbolicMatrix,
    SymbolicMatrixProductRequest,
    SymbolicMatrixRequest,
    SymbolicRankResult,
    _require_determinant_family_result_budget,
)
from jacobian.math.polynomials.values import RationalFunction


def _domain_call(call: object, *args: object, **kwargs: object) -> object:
    try:
        return call(*args, **kwargs)  # type: ignore[operator]
    except PydanticCustomError as exc:
        raise OperationDomainValidationError(
            location=("request",), code=exc.type, message=exc.message()
        ) from exc
    except (ValueError, TypeError) as exc:
        raise OperationDomainValidationError(
            location=("request",), code="matrix.domain_invalid", message=str(exc)
        ) from exc


def _admit_determinant(request: SymbolicDeterminantRequest) -> None:
    _domain_call(
        _require_determinant_family_result_budget,
        request.matrix,
        characteristic_polynomial=False,
    )


def _admit_characteristic(request: SymbolicCharacteristicPolynomialRequest) -> None:
    _domain_call(
        _require_determinant_family_result_budget,
        request.matrix,
        characteristic_polynomial=True,
    )


def compute_symbolic_determinant(
    request: SymbolicDeterminantRequest,
) -> SymbolicDeterminantResult:
    _admit_determinant(request)
    determinant = symbolic_determinant(
        request.matrix.entries,
        request.matrix.variables,
    )
    return SymbolicDeterminantResult(determinant=determinant)


def compute_symbolic_rank(
    request: SymbolicMatrixRequest,
) -> SymbolicRankResult:
    rank, pivot_columns = symbolic_rank(
        request.matrix.entries,
        request.matrix.variables,
    )
    return SymbolicRankResult(rank=rank, pivot_columns=pivot_columns)


def compute_symbolic_matrix_product(
    request: SymbolicMatrixProductRequest,
) -> SymbolicMatrix:
    """Compute one exact symbolic matrix product."""

    return _domain_call(symbolic_matrix_multiply, request.left, request.right)  # type: ignore[return-value]


def compute_symbolic_characteristic_polynomial(
    request: SymbolicCharacteristicPolynomialRequest,
) -> SymbolicCharacteristicPolynomialResult:
    _admit_characteristic(request)
    degree, coeffs = symbolic_characteristic_polynomial(
        request.matrix.entries,
        request.matrix.variables,
    )
    return SymbolicCharacteristicPolynomialResult(
        degree=degree,
        coefficients_descending=tuple(coeffs),
    )


def compute_symbolic_eigenvalues(
    request: SymbolicCharacteristicPolynomialRequest,
) -> SymbolicEigenvaluesResult:
    _admit_characteristic(request)
    entries = request.matrix.entries
    variables = request.matrix.variables
    try:
        eigenvalues = symbolic_eigenvalues(entries, variables)
    except MatrixError:
        # SymPy raises MatrixError when eigenvalues cannot be represented
        # in radicals.  Return the exact characteristic polynomial instead.
        degree, coeffs = symbolic_characteristic_polynomial(entries, variables)
        return SymbolicEigenvaluesResult(
            representation="ROOTS_BY_POLYNOMIAL",
            characteristic_polynomial=tuple(coeffs),
            degree=degree,
        )
    return SymbolicEigenvaluesResult(
        representation="EXPLICIT_ROOTS",
        eigenvalues=tuple(value for value, _ in eigenvalues),
        multiplicities=tuple(mult for _, mult in eigenvalues),
    )


def compute_symbolic_linear_system(
    request: SymbolicLinearSystemRequest,
) -> SymbolicLinearSystemResult:
    """Classify and solve ``A x = b`` over ``QQ(t_1, ..., t_n)``."""

    from jacobian.math.matrices.symbolic import symbolic_linear_system_solve
    from jacobian.math.matrices.symbolic._models import (
        SymbolicLinearSystemResult,
    )

    classification, solution, particular, nullspace = cast(
        tuple[
            Literal["UNIQUE", "NON_UNIQUE", "INCONSISTENT"],
            tuple[RationalFunction, ...] | None,
            tuple[RationalFunction, ...] | None,
            tuple[tuple[RationalFunction, ...], ...] | None,
        ],
        _domain_call(
            symbolic_linear_system_solve,
            request.matrix.entries,
            request.rhs,
            request.matrix.variables,
        ),
    )

    return SymbolicLinearSystemResult._from_kernel(
        system=request,
        classification=classification,
        solution=solution,
        particular_solution=particular,
        nullspace_basis=nullspace,
    )
