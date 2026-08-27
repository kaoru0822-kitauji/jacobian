"""Private MCP adapters for exact quadratic-form evaluation."""

from jacobian.math.quadratic_forms._models import EvaluationRequest, EvaluationResult
from jacobian.math.quadratic_forms.values import evaluate_rational_quadratic_form


def evaluate_form(request: EvaluationRequest) -> EvaluationResult:
    """Evaluate the request's form exactly with direct rational arithmetic."""

    return EvaluationResult._from_kernel(
        request,
        value=evaluate_rational_quadratic_form(request.form, request.vector),
    )


__all__ = ["evaluate_form"]
