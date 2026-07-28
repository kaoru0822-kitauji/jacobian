"""Independent checker declarations owned by the graph-optimization domain."""

from jacobian.checker_operations import ExactReplayCheckerDeclaration
from jacobian.contracts.graph_optimization import GraphOptimizationRequest

GRAPH_OPTIMIZATION_EXACT_REPLAY_CHECKERS = (
    ExactReplayCheckerDeclaration(
        "graph.induced_tree.maximum.compute",
        GraphOptimizationRequest,
        "check_graph_induced_tree_maximum",
        "graph.induced-tree.maximum.exhaustive-replay",
    ),
)


__all__ = ["GRAPH_OPTIMIZATION_EXACT_REPLAY_CHECKERS"]
