"""Graph transform operation declarations."""

from collections.abc import Callable

from jacobian._models import StrictModel
from jacobian.catalog._examples import example
from jacobian.catalog.models import MathTool, MathTools, OperationExample
from jacobian.math.graphs.transforms._path_profile_models import (
    PathProfileRequest,
    PathProfileResult,
)
from jacobian.math.graphs.transforms._path_profile_operations import (
    compute_path_profile,
)


def gt_operation[RequestT: StrictModel, ResultT: StrictModel](
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


_GRAPH_EXAMPLE = {
    "graph": {
        "vertex_count": 3,
        "edges": [
            [0, 1],
            [1, 2],
        ],
    }
}


TOOLS: MathTools = (
    gt_operation(
        "graph.path_profile.compute",
        "Profile fixed-length simple paths by endpoint",
        "For each ordered pair of vertices, count simple paths of the given length; the request is bounded by a degree-sensitive search budget.",
        PathProfileRequest,
        PathProfileResult,
        compute_path_profile,
        "graph",
        "path",
        "profile",
        examples=(
            example(
                "path_profile_p3_len1",
                "Count length-1 paths in a path graph P3; path_length must be at most 10.",
                {
                    "graph": {
                        "vertices": ["a", "b", "c"],
                        "edges": [["a", "b"], ["b", "c"]],
                    },
                    "path_length": 1,
                },
            ),
        ),
    ),
)

__all__ = ["TOOLS"]
