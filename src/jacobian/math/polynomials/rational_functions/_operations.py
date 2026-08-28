"""Public exact rational-function operation adapters and certificate checks."""

from __future__ import annotations

from pydantic_core import PydanticCustomError

from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.polynomials.rational_functions._models import (
    HermiteReductionRequest,
    HermiteReductionResult,
    require_hermite_reduction_budget,
)
from jacobian.math.polynomials.rational_functions.operations import hermite_reduction


def compute_hermite_reduction(
    request: HermiteReductionRequest,
) -> HermiteReductionResult:
    try:
        require_hermite_reduction_budget(request.function)
    except PydanticCustomError as exc:
        raise OperationDomainValidationError(
            location=(), code=exc.type, message=exc.message()
        ) from exc
    except ValueError as exc:
        raise OperationDomainValidationError(
            location=(), code="polynomial.rational_function_admission", message=str(exc)
        ) from exc
    rational_part, remainder = hermite_reduction(request.function)
    return HermiteReductionResult._from_kernel(
        function=request.function,
        rational_part=rational_part,
        remainder=remainder,
    )


__all__ = ["compute_hermite_reduction"]
