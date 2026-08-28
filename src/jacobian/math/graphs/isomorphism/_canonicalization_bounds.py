"""Shared mathematical admission for colored-graph canonicalization."""

from pydantic_core import PydanticCustomError

from jacobian.math.graphs.isomorphism._canonicalization import (
    MAX_CANONICAL_PERMUTATIONS,
    MAX_CANONICALIZATION_RESULT_BYTES,
    MAX_CANONICALIZATION_WORK,
    canonical_permutation_count,
    canonicalization_result_wire_bytes,
    canonicalization_work,
)
from jacobian.math.graphs.values import ColoredUndirectedGraph


def require_admitted_colored_graph_canonicalization(
    graph: ColoredUndirectedGraph,
) -> None:
    """Check the full execution and canonical-result envelope for ``graph``."""

    candidate_count = canonical_permutation_count(graph)
    if candidate_count > MAX_CANONICAL_PERMUTATIONS:
        raise PydanticCustomError(
            "graph.colored_canonicalization_exceeds_max_canonical_permutations_permutatio",
            "colored-graph canonicalization exceeds the "
            f"{MAX_CANONICAL_PERMUTATIONS}-permutation bound",
        )
    execution_work = canonicalization_work(graph)
    if execution_work > MAX_CANONICALIZATION_WORK:
        raise PydanticCustomError(
            "graph.colored_canonicalization_exceeds_max_canonicalization_work",
            "colored-graph canonicalization exceeds the "
            f"{MAX_CANONICALIZATION_WORK}-unit execution work bound",
        )
    result_bytes = canonicalization_result_wire_bytes(graph)
    if result_bytes > MAX_CANONICALIZATION_RESULT_BYTES:
        raise PydanticCustomError(
            "graph.colored_canonicalization_exceeds_max_canonicalization_result_bytes",
            "colored-graph canonicalization exceeds the "
            f"{MAX_CANONICALIZATION_RESULT_BYTES}-byte result bound",
        )


__all__ = [
    "MAX_CANONICALIZATION_RESULT_BYTES",
    "canonicalization_result_wire_bytes",
    "require_admitted_colored_graph_canonicalization",
]
