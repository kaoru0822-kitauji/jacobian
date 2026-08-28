"""Finite metric space operation declarations."""

from collections.abc import Callable
from typing import Any

from jacobian._models import StrictModel
from jacobian.catalog._examples import example
from jacobian.catalog.models import MathTool, OperationExample
from jacobian.math.geometry.metric_spaces._models import (
    GromovHyperbolicityRequest,
    GromovHyperbolicityResult,
    MetricProfileRequest,
    MetricProfileResult,
)
from jacobian.math.geometry.metric_spaces._operations import (
    compute_gromov_hyperbolicity,
    compute_metric_profile,
)


def fms_operation[RequestT: StrictModel, ResultT: StrictModel](
    operation_id: str,
    title: str,
    description: str,
    request_model: type[RequestT],
    result_model: type[ResultT],
    operation: Callable[[RequestT], ResultT],
    *tags: str,
    examples: tuple[OperationExample, ...] = (),
) -> MathTool[RequestT, ResultT]:
    return MathTool(
        operation_id=operation_id,
        title=title,
        description=description,
        request_type=request_model,
        result_type=result_model,
        run=operation,
        tags=tags,
        examples=examples,
    )


_METRIC_SPACE = {
    "metric_space": {
        "point_count": 3,
        "distances": [[0, 1, 2], [1, 0, 1], [2, 1, 0]],
    }
}


TOOLS: tuple[MathTool[Any, Any], ...] = (
    fms_operation(
        "metric_space.profile.compute",
        "Compute diameter, radius, eccentricities, centers, and periphery",
        "Compute the exact metric profile of a finite metric space: "
        "diameter (max eccentricity), radius (min eccentricity), "
        "eccentricities for all points, centers, and periphery.",
        MetricProfileRequest,
        MetricProfileResult,
        compute_metric_profile,
        "metric",
        "profile",
        "exact",
        examples=(
            example(
                "path_graph",
                "Profile of a path metric space with 3 points.",
                _METRIC_SPACE,
            ),
        ),
    ),
    fms_operation(
        "metric_space.gromov_hyperbolicity.compute",
        "Compute the four-point Gromov hyperbolicity",
        "Compute the exact four-point Gromov hyperbolicity of a finite "
        "metric space by brute-force enumeration over all quadruples.",
        GromovHyperbolicityRequest,
        GromovHyperbolicityResult,
        compute_gromov_hyperbolicity,
        "metric",
        "hyperbolicity",
        "exact",
        examples=(
            example(
                "path_graph",
                "Gromov hyperbolicity of a 3-point path metric.",
                _METRIC_SPACE,
            ),
        ),
    ),
)


__all__ = ["TOOLS"]
