"""k-regular subgraph operations."""

from jacobian.math.graphs.regular_subgraph._models import (
    RegularSubgraphRequest,
    RegularSubgraphResult,
)
from jacobian.math.graphs.regular_subgraph._operations import (
    compute_k_regular_subgraph,
)

__all__ = [
    "RegularSubgraphRequest",
    "RegularSubgraphResult",
    "compute_k_regular_subgraph",
]
