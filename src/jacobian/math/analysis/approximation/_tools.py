"""Typed declarations for approximation theory operations."""

from collections.abc import Callable
from typing import Any

from jacobian._models import StrictModel
from jacobian.catalog._examples import example
from jacobian.catalog.models import MathTool, OperationExample
from jacobian.math.analysis.approximation._models import (
    LagrangeBasisRequest,
    LagrangeBasisResult,
)
from jacobian.math.analysis.approximation._operations import (
    compute_lagrange_basis,
)


def approximation_operation[
    RequestT: StrictModel,
    ResultT: StrictModel,
](
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


_BASIS_EXAMPLE: dict[str, Any] = {
    "nodes": {
        "nodes": [
            {"num": "0", "den": "1"},
            {"num": "1", "den": "2"},
            {"num": "1", "den": "1"},
        ]
    }
}

_INTERP_EXAMPLE: dict[str, Any] = {
    "nodes": {
        "nodes": [
            {"num": "0", "den": "1"},
            {"num": "1", "den": "1"},
            {"num": "2", "den": "1"},
        ]
    },
    "values": [
        {"num": "1", "den": "1"},
        {"num": "3", "den": "1"},
        {"num": "9", "den": "1"},
    ],
}


TOOLS: tuple[MathTool[Any, Any], ...] = (
    approximation_operation(
        "approximation.lagrange.basis.compute",
        "Compute Lagrange basis polynomials for rational nodes",
        "Given a finite set of distinct rational nodes x_0 < ... < x_{n-1}, "
        "compute the exact Lagrange basis polynomials l_k(x) and barycentric "
        "weights w_k = 1/prod_{i!=k}(x_k - x_i) over QQ.",
        LagrangeBasisRequest,
        LagrangeBasisResult,
        compute_lagrange_basis,
        "approximation",
        "lagrange",
        "interpolation",
        "exact",
        examples=(
            example(
                "three_nodes",
                "Compute the Lagrange basis for nodes 0, 1/2, 1.",
                _BASIS_EXAMPLE,
            ),
        ),
    ),
)


__all__ = ["TOOLS"]
