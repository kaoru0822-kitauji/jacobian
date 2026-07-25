"""NetworkX-backed capabilities for small simple undirected graphs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, cast

import networkx as nx

from jacobian.artifacts import ArtifactService
from jacobian.capabilities import CapabilityInvocationError
from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityCompleteness,
    CapabilityCompletenessStatus,
    CapabilityDescriptor,
    CapabilityDiagnostic,
    CapabilityMode,
    CapabilityRelationship,
    CapabilityRequest,
    CapabilityResult,
    CapabilityScope,
)
from jacobian.contracts.results import Execution, ExecutionStatus
from jacobian.schema_registry import SchemaRegistry
from jacobian.store import ArtifactStore, StoreError

_ARTIFACT_URI_PATTERN = r"^artifact://sha256/[0-9a-f]{64}$"
_PROPERTY_NAMES = (
    "bipartite",
    "connected",
    "degree_sequence",
    "independence_number",
    "maximum_degree",
    "minimum_degree",
    "order",
    "size",
    "tree",
    "triangle_count",
)
_GRAPH_PAYLOAD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "graph_schema_version": {"const": "1"},
        "vertices": {
            "type": "array",
            "items": {"type": "string"},
            "uniqueItems": True,
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 2,
            },
            "uniqueItems": True,
        },
    },
    "required": ["graph_schema_version", "vertices", "edges"],
    "additionalProperties": False,
}
_CONSTRAINT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "connected": {"type": "boolean"},
        "bipartite": {"type": "boolean"},
        "tree": {"type": "boolean"},
        "triangle_free": {"type": "boolean"},
        "minimum_edges": {"type": "integer", "minimum": 0},
        "maximum_edges": {"type": "integer", "minimum": 0},
        "minimum_degree": {"type": "integer", "minimum": 0},
        "maximum_degree": {"type": "integer", "minimum": 0},
        "independence_number": {"type": "integer", "minimum": 0},
    },
    "additionalProperties": False,
}


@dataclass(frozen=True)
class GraphCapabilityResources:
    store: ArtifactStore
    artifacts: ArtifactService
    semantics_uri: str
    graph_schema_uri: str
    scope_schema_uri: str
    property_schema_uri: str


def install_graph_capabilities(
    store: ArtifactStore,
    schemas: SchemaRegistry,
    artifacts: ArtifactService,
) -> tuple[GraphAtlasSearchAdapter, GraphPropertyAdapter]:
    """Register graph artifact contracts and return the bundled adapters."""

    semantics_uri = store.register_descriptor(
        kind="semantics",
        name="jacobian.simple-undirected-graph",
        version="1",
        definition={
            "domain": "finite simple undirected graphs",
            "vertices": "distinct string labels",
            "edges": "distinct two-vertex arrays in ascending label order",
            "atlas_scope": (
                "networkx.graph_atlas_g representatives with exactly the "
                "requested order, limited to orders zero through seven"
            ),
        },
    )
    graph_schema_uri = schemas.register(
        name="jacobian.simple-undirected-graph",
        version="1",
        schema=_GRAPH_PAYLOAD_SCHEMA,
    )
    scope_schema_uri = schemas.register(
        name="jacobian.graph-atlas-scope",
        version="1",
        schema={
            "type": "object",
            "properties": {
                "scope_schema_version": {"const": "1"},
                "source": {"const": "networkx.graph_atlas_g"},
                "backend_version": {"type": "string"},
                "order": {"type": "integer", "minimum": 0, "maximum": 7},
                "enumerated_count": {"type": "integer", "minimum": 0},
            },
            "required": [
                "scope_schema_version",
                "source",
                "backend_version",
                "order",
                "enumerated_count",
            ],
            "additionalProperties": False,
        },
    )
    property_schema_uri = schemas.register(
        name="jacobian.graph-property-batch",
        version="1",
        schema={
            "type": "object",
            "properties": {
                "property_schema_version": {"const": "1"},
                "graph_uri": {
                    "type": "string",
                    "pattern": _ARTIFACT_URI_PATTERN,
                },
                "backend_version": {"type": "string"},
                "properties": {"type": "object"},
            },
            "required": [
                "property_schema_version",
                "graph_uri",
                "backend_version",
                "properties",
            ],
            "additionalProperties": False,
        },
    )
    resources = GraphCapabilityResources(
        store=store,
        artifacts=artifacts,
        semantics_uri=semantics_uri,
        graph_schema_uri=graph_schema_uri,
        scope_schema_uri=scope_schema_uri,
        property_schema_uri=property_schema_uri,
    )
    return GraphAtlasSearchAdapter(resources), GraphPropertyAdapter(resources)


class GraphAtlasSearchAdapter:
    """Search NetworkX's bounded Graph Atlas using exact computed properties."""

    def __init__(self, resources: GraphCapabilityResources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="graph.search.atlas",
            version="1",
            title="Search the Graph Atlas",
            description=(
                "Search all Graph Atlas representatives of one exact order "
                "(0-7) using exact NetworkX-computed constraints."
            ),
            provider="jacobian.networkx",
            modes=(CapabilityMode.EXPLORE,),
            input_schema={
                "type": "object",
                "properties": {
                    "order": {"type": "integer", "minimum": 0, "maximum": 7},
                    "constraints": _CONSTRAINT_SCHEMA,
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": ["order", "constraints"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "properties": {
                    "candidates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "graph_uri": {
                                    "type": "string",
                                    "pattern": _ARTIFACT_URI_PATTERN,
                                },
                                "graph": _GRAPH_PAYLOAD_SCHEMA,
                                "properties": {"type": "object"},
                            },
                            "required": ["graph_uri", "graph", "properties"],
                            "additionalProperties": False,
                        },
                    },
                    "match_count": {"type": "integer", "minimum": 0},
                    "returned_count": {"type": "integer", "minimum": 0},
                    "truncated": {"type": "boolean"},
                    "scope_uri": {
                        "type": "string",
                        "pattern": _ARTIFACT_URI_PATTERN,
                    },
                    "backend": {"const": "networkx.graph_atlas_g"},
                    "backend_version": {"type": "string"},
                },
                "required": [
                    "candidates",
                    "match_count",
                    "returned_count",
                    "truncated",
                    "scope_uri",
                    "backend",
                    "backend_version",
                ],
                "additionalProperties": False,
            },
            tags=("graph", "construction", "bounded-search"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        started = time.monotonic()
        order = int(request.input["order"])
        constraints = dict(request.input["constraints"])
        _validate_constraint_ranges(constraints)
        limit = int(request.input.get("limit", 10))
        atlas_graphs = [
            graph for graph in nx.graph_atlas_g() if graph.number_of_nodes() == order
        ]
        scope = self.resources.artifacts.put(
            schema_uri=self.resources.scope_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload={
                "scope_schema_version": "1",
                "source": "networkx.graph_atlas_g",
                "backend_version": nx.__version__,
                "order": order,
                "enumerated_count": len(atlas_graphs),
            },
            summary=f"Graph Atlas representatives of order {order}",
        )
        matches: list[tuple[nx.Graph[Any], dict[str, Any]]] = []
        for graph in atlas_graphs:
            properties = _compute_all_properties(graph)
            if _matches_constraints(properties, constraints):
                matches.append((graph, properties))
        candidates: list[dict[str, Any]] = []
        graph_uris: list[str] = []
        for graph, properties in matches[:limit]:
            graph_payload = _graph_payload(graph)
            graph_artifact = self.resources.artifacts.put(
                schema_uri=self.resources.graph_schema_uri,
                semantics_uri=self.resources.semantics_uri,
                payload=graph_payload,
                parents=(scope.artifact_uri,),
                summary=f"Graph Atlas candidate of order {order}",
            )
            graph_uris.append(graph_artifact.artifact_uri)
            candidates.append(
                {
                    "graph_uri": graph_artifact.artifact_uri,
                    "graph": graph_payload,
                    "properties": properties,
                }
            )
        artifact_uris = (scope.artifact_uri, *graph_uris)
        relationships = tuple(
            CapabilityRelationship(
                relation_id="graph.relation.atlas-member",
                source_artifact_uris=(scope.artifact_uri,),
                target_artifact_uris=(graph_uri,),
            )
            for graph_uri in graph_uris
        )
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(
                status=ExecutionStatus.COMPLETED,
                runtime_ms=_runtime_ms(started),
            ),
            output={
                "candidates": candidates,
                "match_count": len(matches),
                "returned_count": len(candidates),
                "truncated": len(matches) > len(candidates),
                "scope_uri": scope.artifact_uri,
                "backend": "networkx.graph_atlas_g",
                "backend_version": nx.__version__,
            },
            scope=CapabilityScope(
                description=(
                    "all Graph Atlas representatives with the requested exact order"
                ),
                parameters={
                    "source": "networkx.graph_atlas_g",
                    "backend_version": nx.__version__,
                    "order": order,
                },
                artifact_uri=scope.artifact_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.COMPLETE,
                basis=(
                    "the maintained Graph Atlas provider was scanned to exhaustion; "
                    "this computation was not independently checked"
                ),
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            relationships=relationships,
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=(
                    "deterministic NetworkX Graph Atlas enumeration and exact "
                    "property filters; no independent checker was invoked"
                ),
            ),
            artifact_uris=artifact_uris,
        )


class GraphPropertyAdapter:
    """Compute a requested batch of exact properties for one graph artifact."""

    def __init__(self, resources: GraphCapabilityResources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="graph.compute.properties",
            version="1",
            title="Compute exact graph properties",
            description=(
                "Compute a requested batch of exact NetworkX properties for one "
                "Jacobian simple-undirected-graph artifact."
            ),
            provider="jacobian.networkx",
            modes=(CapabilityMode.EXPLORE,),
            input_schema={
                "type": "object",
                "properties": {
                    "graph_uri": {
                        "type": "string",
                        "pattern": _ARTIFACT_URI_PATTERN,
                    },
                    "properties": {
                        "type": "array",
                        "items": {"enum": list(_PROPERTY_NAMES)},
                        "minItems": 1,
                        "uniqueItems": True,
                    },
                },
                "required": ["graph_uri", "properties"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "properties": {
                    "graph_uri": {
                        "type": "string",
                        "pattern": _ARTIFACT_URI_PATTERN,
                    },
                    "property_artifact_uri": {
                        "type": "string",
                        "pattern": _ARTIFACT_URI_PATTERN,
                    },
                    "properties": {"type": "object"},
                    "backend_version": {"type": "string"},
                },
                "required": [
                    "graph_uri",
                    "property_artifact_uri",
                    "properties",
                    "backend_version",
                ],
                "additionalProperties": False,
            },
            tags=("graph", "properties", "exact-computation"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        started = time.monotonic()
        graph_uri = str(request.input["graph_uri"])
        graph = _load_graph(self.resources, graph_uri)
        all_properties = _compute_all_properties(graph)
        selected = {
            name: _property_result(name, all_properties[name])
            for name in sorted(str(item) for item in request.input["properties"])
        }
        property_artifact = self.resources.artifacts.put(
            schema_uri=self.resources.property_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload={
                "property_schema_version": "1",
                "graph_uri": graph_uri,
                "backend_version": nx.__version__,
                "properties": selected,
            },
            parents=(graph_uri,),
            summary="exact NetworkX graph-property batch",
        )
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(
                status=ExecutionStatus.COMPLETED,
                runtime_ms=_runtime_ms(started),
            ),
            output={
                "graph_uri": graph_uri,
                "property_artifact_uri": property_artifact.artifact_uri,
                "properties": selected,
                "backend_version": nx.__version__,
            },
            scope=CapabilityScope(
                description="the requested property batch for one exact graph artifact",
                parameters={
                    "graph_uri": graph_uri,
                    "properties": sorted(
                        str(item) for item in request.input["properties"]
                    ),
                },
                artifact_uri=graph_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.COMPLETE,
                basis=(
                    "every requested property was computed; no mathematical "
                    "conclusion or independent verification is claimed"
                ),
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            relationships=(
                CapabilityRelationship(
                    relation_id="graph.relation.properties-of",
                    source_artifact_uris=(graph_uri,),
                    target_artifact_uris=(property_artifact.artifact_uri,),
                ),
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=(
                    "deterministic exact NetworkX algorithms; no independent "
                    "checker was invoked"
                ),
            ),
            artifact_uris=(graph_uri, property_artifact.artifact_uri),
        )


def _validate_constraint_ranges(constraints: dict[str, Any]) -> None:
    for lower, upper in (
        ("minimum_edges", "maximum_edges"),
        ("minimum_degree", "maximum_degree"),
    ):
        if (
            lower in constraints
            and upper in constraints
            and int(constraints[lower]) > int(constraints[upper])
        ):
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_CONSTRAINT_RANGE",
                    stage="constraint_validation",
                    message=f"{lower} cannot exceed {upper}.",
                    path=f"constraints/{lower}",
                    hint="Swap the bounds or remove one of them, then retry.",
                )
            )


def _graph_payload(graph: nx.Graph[Any]) -> dict[str, Any]:
    labels = {node: f"v{index}" for index, node in enumerate(sorted(graph.nodes))}
    edges = sorted(
        [labels[source], labels[target]]
        if labels[source] < labels[target]
        else [labels[target], labels[source]]
        for source, target in graph.edges
    )
    return {
        "graph_schema_version": "1",
        "vertices": [labels[node] for node in sorted(graph.nodes)],
        "edges": edges,
    }


def _load_graph(resources: GraphCapabilityResources, graph_uri: str) -> nx.Graph[str]:
    try:
        artifact = resources.store.get(graph_uri)
    except StoreError as exc:
        raise CapabilityInvocationError(
            CapabilityDiagnostic(
                code="GRAPH_ARTIFACT_NOT_FOUND",
                stage="graph_resolution",
                message="The requested graph artifact is unavailable.",
                path="graph_uri",
                hint="Use a graph URI returned by graph.search.atlas.",
            )
        ) from exc
    if (
        artifact.manifest.schema_uri != resources.graph_schema_uri
        or artifact.manifest.semantics_uri != resources.semantics_uri
        or not isinstance(artifact.payload, dict)
    ):
        raise CapabilityInvocationError(
            CapabilityDiagnostic(
                code="INCOMPATIBLE_GRAPH_ARTIFACT",
                stage="graph_validation",
                message="The artifact is not a compatible simple undirected graph.",
                path="graph_uri",
                schema_uri=resources.graph_schema_uri,
                hint="Use a graph URI returned by graph.search.atlas.",
            )
        )
    payload = artifact.payload
    vertices = payload.get("vertices")
    edges = payload.get("edges")
    if (
        payload.get("graph_schema_version") != "1"
        or not isinstance(vertices, list)
        or not all(isinstance(vertex, str) for vertex in vertices)
        or len(set(vertices)) != len(vertices)
        or not isinstance(edges, list)
    ):
        raise CapabilityInvocationError(
            CapabilityDiagnostic(
                code="INCOMPATIBLE_GRAPH_ARTIFACT",
                stage="graph_validation",
                message="The graph artifact payload is malformed.",
                path="graph_uri",
                schema_uri=resources.graph_schema_uri,
                hint="Recreate the graph through its owning capability.",
            )
        )
    vertex_set = set(vertices)
    normalized_edges: list[tuple[str, str]] = []
    for edge in edges:
        if (
            not isinstance(edge, list)
            or len(edge) != 2
            or not all(isinstance(endpoint, str) for endpoint in edge)
            or edge[0] not in vertex_set
            or edge[1] not in vertex_set
            or edge[0] >= edge[1]
        ):
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INCOMPATIBLE_GRAPH_ARTIFACT",
                    stage="graph_validation",
                    message="The graph artifact violates simple-graph semantics.",
                    path="graph_uri",
                    schema_uri=resources.graph_schema_uri,
                    hint="Recreate the graph through its owning capability.",
                )
            )
        normalized_edges.append((edge[0], edge[1]))
    if len(set(normalized_edges)) != len(normalized_edges):
        raise CapabilityInvocationError(
            CapabilityDiagnostic(
                code="INCOMPATIBLE_GRAPH_ARTIFACT",
                stage="graph_validation",
                message="The graph artifact contains duplicate edges.",
                path="graph_uri",
                schema_uri=resources.graph_schema_uri,
                hint="Recreate the graph through its owning capability.",
            )
        )
    graph: nx.Graph[str] = nx.Graph()
    graph.add_nodes_from(vertices)
    graph.add_edges_from(normalized_edges)
    return graph


def _compute_all_properties(graph: nx.Graph[Any]) -> dict[str, Any]:
    order = graph.number_of_nodes()
    degrees = sorted((degree for _, degree in graph.degree), reverse=True)
    if order:
        independent_set, independence_number = nx.max_weight_clique(
            nx.complement(graph),
            weight=None,
        )
        assert len(independent_set) == independence_number
    else:
        independence_number = 0
    return {
        "order": order,
        "size": graph.number_of_edges(),
        "connected": nx.is_connected(graph) if order else False,
        "bipartite": nx.is_bipartite(graph),
        "tree": nx.is_tree(graph) if order else False,
        "degree_sequence": degrees,
        "minimum_degree": min(degrees) if degrees else None,
        "maximum_degree": max(degrees) if degrees else None,
        "triangle_count": (
            sum(cast(dict[Any, int], nx.triangles(graph)).values()) // 3
        ),
        "independence_number": independence_number,
    }


def _matches_constraints(
    properties: dict[str, Any],
    constraints: dict[str, Any],
) -> bool:
    if (
        "connected" in constraints
        and properties["connected"] is not constraints["connected"]
    ):
        return False
    if (
        "bipartite" in constraints
        and properties["bipartite"] is not constraints["bipartite"]
    ):
        return False
    if "tree" in constraints and properties["tree"] is not constraints["tree"]:
        return False
    if "triangle_free" in constraints and (
        (properties["triangle_count"] == 0) is not constraints["triangle_free"]
    ):
        return False
    if (
        "minimum_edges" in constraints
        and properties["size"] < constraints["minimum_edges"]
    ):
        return False
    if (
        "maximum_edges" in constraints
        and properties["size"] > constraints["maximum_edges"]
    ):
        return False
    if "minimum_degree" in constraints and (
        properties["minimum_degree"] is None
        or properties["minimum_degree"] < constraints["minimum_degree"]
    ):
        return False
    if "maximum_degree" in constraints and (
        properties["maximum_degree"] is None
        or properties["maximum_degree"] > constraints["maximum_degree"]
    ):
        return False
    return not (
        "independence_number" in constraints
        and properties["independence_number"] != constraints["independence_number"]
    )


def _property_result(name: str, value: Any) -> dict[str, Any]:
    backend = (
        "networkx.max_weight_clique(complement)"
        if name == "independence_number"
        else "networkx"
    )
    return {
        "value": value,
        "exactness": "EXACT",
        "backend": backend,
    }


def _runtime_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))
