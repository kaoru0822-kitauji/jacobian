"""Nine exact deterministic graph-invariant primitives backed by pinned runtimes.

Capabilities:
  - graph.invariant.clique_number.compute
  - graph.invariant.independence_number.compute
  - graph.invariant.girth.compute
  - graph.invariant.diameter.compute
  - graph.invariant.edge_connectivity.compute
  - graph.invariant.vertex_connectivity.compute
  - graph.invariant.is_eulerian.compute
  - graph.invariant.spanning_tree_count.compute
  - graph.invariant.maximum_matching.compute
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jacobian.primitive_adapters._base import (
    PrimitiveAdapter,
    _build_graph,
    _edge_array_field,
    _schema,
    _string_array_field,
)

if TYPE_CHECKING:
    from jacobian.capabilities import CapabilityAdapter
    from jacobian.kernel import JacobianKernel

_PROVIDER = "jacobian.networkx"
_MAX_VERTICES = 32
_MAX_EDGES = 496


def factory(kernel: JacobianKernel) -> tuple[CapabilityAdapter, ...]:
    return (
        _clique_number(),
        _independence_number(),
        _girth(),
        _diameter(),
        _edge_connectivity(),
        _vertex_connectivity(),
        _is_eulerian(),
        _spanning_tree_count(),
        _maximum_matching(),
    )


def _graph_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "vertices": _string_array_field(max_items=_MAX_VERTICES),
            "edges": _edge_array_field(max_items=_MAX_EDGES),
        },
        "required": ["vertices", "edges"],
        "additionalProperties": False,
    }


def _clique_number() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        import networkx as nx

        g = _build_graph(inp["graph"])
        if g.number_of_nodes() == 0:
            return {"clique_number": 0}
        omega = max(len(c) for c in nx.find_cliques(g))
        return {"clique_number": omega}

    return PrimitiveAdapter(
        capability_id="graph.invariant.clique_number.compute",
        title="Clique number (maximum clique size)",
        description=(
            "Compute the clique number omega(G) — the size of the maximum "
            "clique — using NetworkX's exact find_cliques enumeration."
        ),
        input_schema=_schema(
            {"graph": _graph_schema()},
            required=("graph",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("graph", "invariant", "clique_number", "exact"),
        scope_description="one bounded simple undirected graph (order <= 32)",
    )


def _independence_number() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        import networkx as nx

        g = _build_graph(inp["graph"])
        if g.number_of_nodes() == 0:
            return {"independence_number": 0}
        complement = nx.complement(g)
        alpha = max(len(c) for c in nx.find_cliques(complement))
        return {"independence_number": alpha}

    return PrimitiveAdapter(
        capability_id="graph.invariant.independence_number.compute",
        title="Independence number (maximum independent set size)",
        description=(
            "Compute the independence number alpha(G) via the clique number of "
            "the complement using NetworkX's exact find_cliques."
        ),
        input_schema=_schema(
            {"graph": _graph_schema()},
            required=("graph",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("graph", "invariant", "independence_number", "exact"),
        scope_description="one bounded simple undirected graph (order <= 32)",
    )


def _girth() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        import math

        import networkx as nx

        g = _build_graph(inp["graph"])
        if g.number_of_edges() == 0:
            return {"girth": 0, "has_cycle": False}
        computed = nx.girth(g)
        girth = 0 if math.isinf(computed) else int(computed)
        return {"girth": girth, "has_cycle": girth > 0}

    return PrimitiveAdapter(
        capability_id="graph.invariant.girth.compute",
        title="Girth (shortest cycle length)",
        description=(
            "Compute the girth — the length of the shortest cycle — using "
            "NetworkX. Returns 0 for acyclic graphs."
        ),
        input_schema=_schema(
            {"graph": _graph_schema()},
            required=("graph",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("graph", "invariant", "girth", "exact"),
        scope_description="one bounded simple undirected graph (order <= 32)",
    )


def _diameter() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        import networkx as nx

        g = _build_graph(inp["graph"])
        if g.number_of_nodes() == 0:
            return {"diameter": 0, "connected": False}
        if not nx.is_connected(g):
            return {"diameter": -1, "connected": False}
        diam = nx.diameter(g)
        return {"diameter": diam, "connected": True}

    return PrimitiveAdapter(
        capability_id="graph.invariant.diameter.compute",
        title="Diameter of a connected graph",
        description=(
            "Compute the exact diameter using NetworkX's BFS-based diameter. "
            "Returns -1 for disconnected graphs."
        ),
        input_schema=_schema(
            {"graph": _graph_schema()},
            required=("graph",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("graph", "invariant", "diameter", "exact"),
        scope_description="one bounded simple undirected graph (order <= 32)",
    )


def _edge_connectivity() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        import networkx as nx

        g = _build_graph(inp["graph"])
        if g.number_of_nodes() <= 1:
            return {"edge_connectivity": 0}
        ec = nx.edge_connectivity(g)
        return {"edge_connectivity": int(ec)}

    return PrimitiveAdapter(
        capability_id="graph.invariant.edge_connectivity.compute",
        title="Edge connectivity",
        description=(
            "Compute the exact edge connectivity (minimum edge cut) using "
            "NetworkX's edge_connectivity."
        ),
        input_schema=_schema(
            {"graph": _graph_schema()},
            required=("graph",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("graph", "invariant", "edge_connectivity", "exact"),
        scope_description="one bounded simple undirected graph (order <= 32)",
    )


def _vertex_connectivity() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        import networkx as nx

        g = _build_graph(inp["graph"])
        if g.number_of_nodes() <= 1:
            return {"vertex_connectivity": 0}
        vc = nx.node_connectivity(g)
        return {"vertex_connectivity": int(vc)}

    return PrimitiveAdapter(
        capability_id="graph.invariant.vertex_connectivity.compute",
        title="Vertex connectivity",
        description=(
            "Compute the exact vertex connectivity (minimum vertex cut) using "
            "NetworkX's node_connectivity."
        ),
        input_schema=_schema(
            {"graph": _graph_schema()},
            required=("graph",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("graph", "invariant", "vertex_connectivity", "exact"),
        scope_description="one bounded simple undirected graph (order <= 32)",
    )


def _is_eulerian() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        import networkx as nx

        g = _build_graph(inp["graph"])
        return {"is_eulerian": bool(nx.is_eulerian(g))}

    return PrimitiveAdapter(
        capability_id="graph.invariant.is_eulerian.compute",
        title="Eulerian graph test",
        description=(
            "Test whether a bounded simple undirected graph is Eulerian "
            "(connected and all vertices have even degree) using NetworkX."
        ),
        input_schema=_schema(
            {"graph": _graph_schema()},
            required=("graph",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("graph", "invariant", "eulerian", "exact"),
        scope_description="one bounded simple undirected graph (order <= 32)",
    )


def _spanning_tree_count() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        import networkx as nx
        from sympy import Matrix

        g = _build_graph(inp["graph"])
        n = g.number_of_nodes()
        if n == 0:
            return {"spanning_tree_count": 0}
        if not nx.is_connected(g):
            return {"spanning_tree_count": 0, "connected": False}
        nodes = list(g.nodes())
        idx = {v: i for i, v in enumerate(nodes)}
        laplacian = [[0] * n for _ in range(n)]
        for u, v in g.edges():
            i, j = idx[u], idx[v]
            laplacian[i][i] += 1
            laplacian[j][j] += 1
            laplacian[i][j] -= 1
            laplacian[j][i] -= 1
        if n == 1:
            return {"spanning_tree_count": 1, "connected": True}
        minor = Matrix([[laplacian[r][c] for c in range(n - 1)] for r in range(n - 1)])
        count = int(minor.det())
        return {"spanning_tree_count": count, "connected": True}

    return PrimitiveAdapter(
        capability_id="graph.invariant.spanning_tree_count.compute",
        title="Spanning tree count (Kirchhoff's theorem)",
        description=(
            "Compute the exact number of spanning trees via Kirchhoff's "
            "matrix-tree theorem using SymPy's exact determinant of the "
            "reduced Laplacian."
        ),
        input_schema=_schema(
            {"graph": _graph_schema()},
            required=("graph",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("graph", "invariant", "spanning_tree", "exact"),
        scope_description="one bounded simple undirected graph (order <= 32)",
    )


def _maximum_matching() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        import networkx as nx

        g = _build_graph(inp["graph"])
        matching = nx.max_weight_matching(g, maxcardinality=True)
        return {"maximum_matching_cardinality": len(matching)}

    return PrimitiveAdapter(
        capability_id="graph.invariant.maximum_matching.compute",
        title="Maximum matching cardinality",
        description=(
            "Compute the cardinality of a maximum matching using NetworkX's "
            "exact max_weight_matching with maxcardinality=True."
        ),
        input_schema=_schema(
            {"graph": _graph_schema()},
            required=("graph",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("graph", "invariant", "matching", "exact"),
        scope_description="one bounded simple undirected graph (order <= 32)",
    )
