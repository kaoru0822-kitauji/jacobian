"""Ten exact deterministic graph-invariant primitives backed by pinned runtimes.

Capabilities:
  - graph.invariant.chromatic_number.compute
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

import time
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from jacobian.capabilities import CapabilityInvocationError
from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityCompleteness,
    CapabilityCompletenessStatus,
    CapabilityDescriptor,
    CapabilityDiagnostic,
    CapabilityMode,
    CapabilityRequest,
    CapabilityResult,
    CapabilityScope,
)
from jacobian.contracts.graph_coloring import (
    ChromaticGraph,
    ChromaticSearchStep,
    GraphChromaticNumberOutput,
    GraphChromaticNumberRequest,
)
from jacobian.contracts.results import Execution, ExecutionStatus
from jacobian.graph_coloring_semantics import canonical_graph, coloring_cnf
from jacobian.primitive_adapters._base import (
    PrimitiveAdapter,
    _build_graph,
    _edge_array_field,
    _schema,
    _string_array_field,
)
from jacobian.provider_runtime import known_provider_runtime
from jacobian.schema_registry import model_schema

if TYPE_CHECKING:
    from jacobian.capabilities import CapabilityAdapter
    from jacobian.kernel import JacobianKernel

_PROVIDER = "jacobian.networkx"
_Z3_PROVIDER = "jacobian.z3"
_MAX_VERTICES = 32
_MAX_EDGES = 496


def factory(kernel: JacobianKernel) -> tuple[CapabilityAdapter, ...]:
    return (
        _chromatic_number(),
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


class _ChromaticNumberAdapter:
    """Bounded Z3 k-colorability search with explicit non-conclusion handling."""

    def __init__(self) -> None:
        self._descriptor = CapabilityDescriptor(
            capability_id="graph.invariant.chromatic_number.compute",
            version="1",
            title="Exact chromatic number",
            description=(
                "Compute the exact chromatic number of a bounded simple undirected "
                "graph by bounded Z3 k-colorability decisions. A timeout returns "
                "an UNKNOWN result with the tested bounds and search trace."
            ),
            provider=_Z3_PROVIDER,
            provider_runtime=known_provider_runtime(
                _Z3_PROVIDER,
                features=("bounded-k-colorability", "timeout-aware"),
            ),
            modes=(CapabilityMode.EXPLORE,),
            input_schema=model_schema(GraphChromaticNumberRequest),
            output_schema=model_schema(GraphChromaticNumberOutput),
            tags=(
                "graph",
                "invariant",
                "chromatic_number",
                "exact",
                "bounded",
                "z3",
            ),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        try:
            validated = GraphChromaticNumberRequest.model_validate(request.input)
        except ValidationError as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_CHROMATIC_NUMBER_REQUEST",
                    stage="request_validation",
                    message=(
                        "The complete chromatic-number request is invalid: "
                        f"{exc.errors()[0].get('msg', 'validation failed')}"
                    ),
                    hint=(
                        "Supply a simple graph with unique vertices and undirected "
                        "edges, plus an optional wall_seconds budget from 1 to 120."
                    ),
                )
            ) from exc

        graph = validated.graph.model_dump(mode="python")
        g = _build_graph(graph)
        output = _solve_chromatic_number(
            g,
            graph=validated.graph,
            vertices=validated.graph.vertices,
            wall_seconds=validated.resource_budget.wall_seconds,
        )
        exact = output.status == "EXACT"
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description="one bounded simple undirected graph",
                parameters={
                    "order": output.order,
                    "wall_seconds": validated.resource_budget.wall_seconds,
                },
            ),
            completeness=CapabilityCompleteness(
                status=(
                    CapabilityCompletenessStatus.COMPLETE
                    if exact
                    else CapabilityCompletenessStatus.UNKNOWN
                ),
                basis=(
                    "Z3 settled every k-colorability decision through the first "
                    "satisfying k"
                    if exact
                    else "the declared wall-clock budget ended before exactness "
                    "was established"
                ),
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=(
                    "bounded Z3 computation; an independent graph-coloring checker "
                    "would still be required for VERIFIED assurance"
                ),
            ),
        )


def _chromatic_number() -> _ChromaticNumberAdapter:
    return _ChromaticNumberAdapter()


def _solve_chromatic_number(
    g: Any,
    *,
    graph: ChromaticGraph,
    vertices: tuple[str, ...],
    wall_seconds: int,
) -> GraphChromaticNumberOutput:
    import networkx as nx
    import z3  # type: ignore[import-untyped]

    nodes = list(vertices)
    n = len(nodes)
    if n == 0:
        return GraphChromaticNumberOutput(
            status="EXACT",
            vertices=vertices,
            order=0,
            chromatic_number=0,
            lower_bound=0,
            upper_bound=0,
            coloring={},
            solver_status="SPECIAL_CASE",
            tested=(),
            detail="the empty graph requires zero colors",
        )

    greedy = nx.coloring.greedy_color(
        g,
        strategy="saturation_largest_first",
    )
    upper_bound = max(greedy.values(), default=-1) + 1
    lower_bound = 2 if g.number_of_edges() else 1
    if upper_bound == lower_bound:
        return GraphChromaticNumberOutput(
            status="EXACT",
            vertices=vertices,
            order=n,
            chromatic_number=upper_bound,
            lower_bound=upper_bound,
            upper_bound=upper_bound,
            coloring={str(node): int(color) for node, color in greedy.items()},
            solver_status="SPECIAL_CASE",
            tested=(),
            detail="a maintained greedy coloring and graph edge bound coincide",
        )

    started = time.monotonic()
    tested: list[ChromaticSearchStep] = []
    encoded_graph = canonical_graph(graph)
    for colors in range(lower_bound, upper_bound + 1):
        remaining_ms = int((wall_seconds - (time.monotonic() - started)) * 1000)
        if remaining_ms <= 0:
            return _unknown_chromatic_result(
                vertices=vertices,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                coloring=greedy,
                tested=tested,
                detail="the chromatic-number wall-clock budget expired",
            )
        solver = z3.Solver()
        solver.set(timeout=max(1, remaining_ms))
        variable_names, clauses = coloring_cnf(encoded_graph, colors)
        variables = {
            index: z3.Bool(name) for index, name in enumerate(variable_names, start=1)
        }
        for clause in clauses:
            literals = tuple(
                variables[abs(literal)]
                if literal > 0
                else z3.Not(variables[abs(literal)])
                for literal in clause
            )
            solver.add(z3.Or(*literals))

        result = solver.check()
        if result == z3.unknown:
            tested.append(ChromaticSearchStep(colors=colors, status="UNKNOWN"))
            return _unknown_chromatic_result(
                vertices=vertices,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                coloring=greedy,
                tested=tested,
                detail=(
                    "Z3 did not settle the k-colorability decision within the "
                    "remaining wall-clock budget"
                ),
            )
        if result == z3.unsat:
            tested.append(ChromaticSearchStep(colors=colors, status="UNSATISFIABLE"))
            lower_bound = colors + 1
            continue

        tested.append(ChromaticSearchStep(colors=colors, status="SATISFIABLE"))
        model = solver.model()
        coloring = {
            node: next(
                color
                for color in range(colors)
                if z3.is_true(
                    model.eval(
                        variables[index * colors + color + 1],
                        model_completion=True,
                    )
                )
            )
            for index, node in enumerate(encoded_graph.vertices)
        }
        return GraphChromaticNumberOutput(
            status="EXACT",
            vertices=vertices,
            order=n,
            chromatic_number=colors,
            lower_bound=colors,
            upper_bound=colors,
            coloring={str(node): int(color) for node, color in coloring.items()},
            solver_status="SATISFIABLE",
            tested=tuple(tested),
            detail="Z3 found the first satisfying k after settling all smaller k",
        )

    return _unknown_chromatic_result(
        vertices=vertices,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        coloring=greedy,
        tested=tested,
        detail="the solver did not produce a coloring through the valid upper bound",
    )


def _unknown_chromatic_result(
    *,
    vertices: tuple[str, ...],
    lower_bound: int,
    upper_bound: int,
    coloring: dict[Any, int],
    tested: list[ChromaticSearchStep],
    detail: str,
) -> GraphChromaticNumberOutput:
    return GraphChromaticNumberOutput(
        status="UNKNOWN",
        vertices=vertices,
        order=len(vertices),
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        coloring={str(node): int(color) for node, color in coloring.items()},
        solver_status="UNKNOWN",
        tested=tuple(tested),
        detail=detail,
    )


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
