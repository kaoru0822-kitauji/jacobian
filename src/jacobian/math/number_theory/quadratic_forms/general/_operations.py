"""Private MCP adapters for exact quadratic-form evaluation."""

from pydantic_core import PydanticCustomError

from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.number_theory.quadratic_forms.general._models import (
    EvaluationRequest,
    EvaluationResult,
)
from jacobian.math.number_theory.quadratic_forms.general.values import (
    evaluate_rational_quadratic_form,
)


def evaluate_form(request: EvaluationRequest) -> EvaluationResult:
    """Evaluate the request's form exactly with direct rational arithmetic."""

    try:
        value = evaluate_rational_quadratic_form(request.form, request.vector)
    except PydanticCustomError as exc:
        raise OperationDomainValidationError(
            location=("form", "vector"), code=exc.type, message=exc.message()
        ) from exc
    except ValueError as exc:
        raise OperationDomainValidationError(
            location=("form", "vector"),
            code="quadratic_form.domain_invalid",
            message=str(exc),
        ) from exc
    return EvaluationResult._from_kernel(request, value=value)


__all__ = ["evaluate_form"]
