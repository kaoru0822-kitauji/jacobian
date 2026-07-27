"""Graph composition and bounded nonisomorphic enumeration capabilities.

Two domain-atomic graph capabilities backed by NetworkX:

* ``graph.construct.compose`` — apply disjoint union, join, complement, or
  lexicographic product to existing simple-undirected-graph artifacts and
  materialize the result as a new graph artifact with deterministic
  ``COMPUTED`` assurance.

* ``graph.enumerate.nonisomorphic`` — enumerate all nonisomorphic simple
  undirected graphs of one exact order (0-7) from the NetworkX Graph Atlas
  backend and materialize the catalog with an explicit backend boundary
  scope.  The scope artifact records that the catalog is the Graph Atlas
  representative set, not all nonisomorphic graphs of that order in
  existence.

Both capabilities preserve the ``jacobian.simple-undirected-graph`` payload
schema and semantics.  Neither returns a mathematical conclusion or
``VERIFIED`` assurance.  Construction and enumeration are deterministic
NetworkX operations; no independent checker is invoked.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, cast

import networkx as nx
from pydantic import ValidationError

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
from jacobian.contracts.graph_composition import (
    GraphCompositionRequest,
    GraphCompositionResultArtifact,
    GraphEnumerationRequest,
    GraphEnumerationScopeArtifact,
)
from jacobian.contracts.results import Execution, ExecutionStatus
from jacobian.graph_atlas import graph_atlas_order
from jacobian.provider_runtime import known_provider_runtime
from jacobian.schema_registry import SchemaRegistry, model_schema
from jacobian.store import ArtifactStore, StoreError

_ARTIFACT_URI_PATTERN = r"^artifact://sha256/[0-9a-f]{64}$"

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

#: Explicit backend boundary statement for the enumeration scope.
_ENUMERATION_BACKEND_BOUNDARY = (
    "NetworkX graph_atlas_g representatives with exactly the requested order; "
    "this is the Graph Atlas catalog (orders 0-7), not all nonisomorphic "
    "graphs of that order in existence"
)


@dataclass(frozen=True, slots=True)
class GraphCompositionInstallation:
    """Installation record for graph composition and enumeration contracts."""

    semantics_uri: str
    graph_schema_uri: str
    composition_result_schema_uri: str
    enumeration_scope_schema_uri: str


@dataclass(frozen=True)
class GraphCompositionResources:
    """Shared resources for graph composition and enumeration adapters."""

    store: ArtifactStore
    artifacts: ArtifactService
    semantics_uri: str
    graph_schema_uri: str
    composition_result_schema_uri: str
    enumeration_scope_schema_uri: str


def install_graph_composition_capabilities(
    store: ArtifactStore,
    schemas: SchemaRegistry,
    artifacts: ArtifactService,
    *,
    semantics_uri: str,
    graph_schema_uri: str,
) -> tuple[
    tuple[
        GraphComposeAdapter,
        GraphEnumerateNonisomorphicAdapter,
    ],
    GraphCompositionInstallation,
]:
    """Register composition and enumeration schemas and return adapters.

    This installer reuses the ``jacobian.simple-undirected-graph`` semantics
    and graph payload schema already registered by ``graph_capabilities``.
    The caller must pass the existing ``semantics_uri`` and
    ``graph_schema_uri`` from ``GraphInstallation``.
    """

    composition_result_schema_uri = schemas.register(
        name="jacobian.graph-composition-result",
        version="1",
        schema=model_schema(GraphCompositionResultArtifact),
    )
    enumeration_scope_schema_uri = schemas.register(
        name="jacobian.graph-enumeration-scope",
        version="1",
        schema=model_schema(GraphEnumerationScopeArtifact),
    )
    installation = GraphCompositionInstallation(
        semantics_uri=semantics_uri,
        graph_schema_uri=graph_schema_uri,
        composition_result_schema_uri=composition_result_schema_uri,
        enumeration_scope_schema_uri=enumeration_scope_schema_uri,
    )
    resources = GraphCompositionResources(
        store=store,
        artifacts=artifacts,
        semantics_uri=semantics_uri,
        graph_schema_uri=graph_schema_uri,
        composition_result_schema_uri=composition_result_schema_uri,
        enumeration_scope_schema_uri=enumeration_scope_schema_uri,
    )
    return (
        (
            GraphComposeAdapter(resources),
            GraphEnumerateNonisomorphicAdapter(resources),
        ),
        installation,
    )


# ---------------------------------------------------------------------------
# Graph composition
# ---------------------------------------------------------------------------


class GraphComposeAdapter:
    """Apply one graph composition operation to existing graph artifacts."""

    def __init__(self, resources: GraphCompositionResources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="graph.construct.compose",
            version="1",
            title="Compose graphs",
            description=(
                "Apply one deterministic graph composition operation "
                "(disjoint union, join, complement, or lexicographic product) "
                "to one or two existing simple-undirected-graph artifacts and "
                "materialize the result as a new graph artifact."
            ),
            provider="jacobian.networkx",
            provider_runtime=known_provider_runtime(
                "jacobian.networkx",
                features=(
                    "graph-composition",
                    "simple-undirected-graphs",
                ),
            ),
            modes=(CapabilityMode.EXPLORE,),
            input_schema=GraphCompositionRequest.model_json_schema(),
            output_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "enum": [
                            "DISJOINT_UNION",
                            "JOIN",
                            "COMPLEMENT",
                            "LEXICOGRAPHIC_PRODUCT",
                        ],
                    },
                    "result_graph_uri": {
                        "type": "string",
                        "pattern": _ARTIFACT_URI_PATTERN,
                    },
                    "result_graph": _GRAPH_PAYLOAD_SCHEMA,
                    "composition_artifact_uri": {
                        "type": "string",
                        "pattern": _ARTIFACT_URI_PATTERN,
                    },
                    "backend": {"type": "string"},
                    "backend_version": {"type": "string"},
                },
                "required": [
                    "operation",
                    "result_graph_uri",
                    "result_graph",
                    "composition_artifact_uri",
                    "backend",
                    "backend_version",
                ],
                "additionalProperties": False,
            },
            tags=("graph", "construction", "composition"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        started = time.monotonic()
        try:
            validated = GraphCompositionRequest.model_validate(request.input)
        except ValidationError as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_COMPOSITION_REQUEST",
                    stage="request_validation",
                    message=("The complete graph-composition request is invalid."),
                    hint=(
                        "Provide operation, left_graph_uri, and "
                        "right_graph_uri (required for binary operations)."
                    ),
                )
            ) from exc

        left_graph = _load_graph(self.resources, validated.left_graph_uri)
        right_graph: nx.Graph[Any] | None = None
        if validated.right_graph_uri is not None:
            right_graph = _load_graph(self.resources, validated.right_graph_uri)

        operation = validated.operation
        backend = f"networkx.{_backend_suffix(operation)}"
        result_graph = _apply_composition(operation, left_graph, right_graph)
        result_payload = _graph_payload(result_graph)

        result_artifact = self.resources.artifacts.put(
            schema_uri=self.resources.graph_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload=result_payload,
            parents=_composition_parents(validated),
            summary=f"Graph composition: {operation}",
        )
        composition_artifact = self.resources.artifacts.put(
            schema_uri=self.resources.composition_result_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload=GraphCompositionResultArtifact(
                operation=operation,
                left_graph_uri=validated.left_graph_uri,
                right_graph_uri=validated.right_graph_uri,
                result_graph_uri=result_artifact.artifact_uri,
                backend=backend,
                backend_version=nx.__version__,
            ).model_dump(),
            parents=(result_artifact.artifact_uri,),
            summary=f"Composition record: {operation}",
        )

        relationship = CapabilityRelationship(
            relation_id="graph.relation.composed-from",
            source_artifact_uris=(result_artifact.artifact_uri,),
            target_artifact_uris=_composition_parents(validated),
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
                "operation": operation,
                "result_graph_uri": result_artifact.artifact_uri,
                "result_graph": result_payload,
                "composition_artifact_uri": composition_artifact.artifact_uri,
                "backend": backend,
                "backend_version": nx.__version__,
            },
            scope=CapabilityScope(
                description=(
                    f"deterministic {operation} of the supplied graph artifact(s)"
                ),
                parameters={
                    "operation": operation,
                    "left_graph_uri": validated.left_graph_uri,
                    "right_graph_uri": validated.right_graph_uri,
                },
                artifact_uri=result_artifact.artifact_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.COMPLETE,
                basis=(
                    "the deterministic composition was performed over the "
                    "supplied graph artifact(s); no mathematical conclusion "
                    "or independent verification is claimed"
                ),
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            relationships=(relationship,),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=(
                    "deterministic NetworkX graph composition; no independent "
                    "checker was invoked"
                ),
            ),
            artifact_uris=(
                *_composition_parents(validated),
                result_artifact.artifact_uri,
                composition_artifact.artifact_uri,
            ),
        )


# ---------------------------------------------------------------------------
# Bounded nonisomorphic enumeration
# ---------------------------------------------------------------------------


class GraphEnumerateNonisomorphicAdapter:
    """Enumerate nonisomorphic graphs from the bounded NetworkX Graph Atlas."""

    def __init__(self, resources: GraphCompositionResources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="graph.enumerate.nonisomorphic",
            version="1",
            title="Enumerate nonisomorphic graphs",
            description=(
                "Enumerate all nonisomorphic simple undirected graphs of one "
                "exact order (0-7) from the NetworkX Graph Atlas backend and "
                "materialize the catalog with an explicit backend boundary."
            ),
            provider="jacobian.networkx",
            provider_runtime=known_provider_runtime(
                "jacobian.networkx",
                features=(
                    "graph-atlas",
                    "nonisomorphic-enumeration",
                    "simple-undirected-graphs",
                ),
            ),
            modes=(CapabilityMode.EXPLORE,),
            input_schema=GraphEnumerationRequest.model_json_schema(),
            output_schema={
                "type": "object",
                "properties": {
                    "graphs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "graph_uri": {
                                    "type": "string",
                                    "pattern": _ARTIFACT_URI_PATTERN,
                                },
                                "graph": _GRAPH_PAYLOAD_SCHEMA,
                                "order": {"type": "integer", "minimum": 0},
                                "size": {"type": "integer", "minimum": 0},
                            },
                            "required": [
                                "graph_uri",
                                "graph",
                                "order",
                                "size",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "total_count": {"type": "integer", "minimum": 0},
                    "returned_count": {"type": "integer", "minimum": 0},
                    "truncated": {"type": "boolean"},
                    "scope_uri": {
                        "type": "string",
                        "pattern": _ARTIFACT_URI_PATTERN,
                    },
                    "backend": {"const": "networkx.graph_atlas_g"},
                    "backend_version": {"type": "string"},
                    "backend_boundary": {"type": "string"},
                },
                "required": [
                    "graphs",
                    "total_count",
                    "returned_count",
                    "truncated",
                    "scope_uri",
                    "backend",
                    "backend_version",
                    "backend_boundary",
                ],
                "additionalProperties": False,
            },
            tags=(
                "graph",
                "enumeration",
                "nonisomorphic",
                "bounded-search",
            ),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        started = time.monotonic()
        try:
            validated = GraphEnumerationRequest.model_validate(request.input)
        except ValidationError as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_ENUMERATION_REQUEST",
                    stage="request_validation",
                    message=("The complete graph-enumeration request is invalid."),
                    hint="Provide order (0-7), optional limit (1-1000), and offset (>=0).",
                )
            ) from exc

        order = validated.order
        limit = validated.limit
        offset = validated.offset

        atlas_graphs = graph_atlas_order(order)
        total_count = len(atlas_graphs)
        window = atlas_graphs[offset : offset + limit]
        truncated = (offset + limit) < total_count

        scope_artifact = self.resources.artifacts.put(
            schema_uri=self.resources.enumeration_scope_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload=GraphEnumerationScopeArtifact(
                source="networkx.graph_atlas_g",
                backend_version=nx.__version__,
                order=order,
                enumerated_count=total_count,
                backend_boundary=_ENUMERATION_BACKEND_BOUNDARY,
            ).model_dump(),
            summary=f"Nonisomorphic enumeration scope: order {order}",
        )

        graphs: list[dict[str, Any]] = []
        graph_uris: list[str] = []
        for graph in window:
            payload = _graph_payload(graph)
            graph_artifact = self.resources.artifacts.put(
                schema_uri=self.resources.graph_schema_uri,
                semantics_uri=self.resources.semantics_uri,
                payload=payload,
                parents=(scope_artifact.artifact_uri,),
                summary=f"Nonisomorphic graph of order {order}",
            )
            graph_uris.append(graph_artifact.artifact_uri)
            graphs.append(
                {
                    "graph_uri": graph_artifact.artifact_uri,
                    "graph": payload,
                    "order": graph.number_of_nodes(),
                    "size": graph.number_of_edges(),
                }
            )

        relationships = tuple(
            CapabilityRelationship(
                relation_id="graph.relation.enumerated-in",
                source_artifact_uris=(scope_artifact.artifact_uri,),
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
                "graphs": graphs,
                "total_count": total_count,
                "returned_count": len(graphs),
                "truncated": truncated,
                "scope_uri": scope_artifact.artifact_uri,
                "backend": "networkx.graph_atlas_g",
                "backend_version": nx.__version__,
                "backend_boundary": _ENUMERATION_BACKEND_BOUNDARY,
            },
            scope=CapabilityScope(
                description=(
                    "all NetworkX Graph Atlas representatives with exactly "
                    f"the requested order {order}"
                ),
                parameters={
                    "source": "networkx.graph_atlas_g",
                    "backend_version": nx.__version__,
                    "order": order,
                    "enumerated_count": total_count,
                    "backend_boundary": _ENUMERATION_BACKEND_BOUNDARY,
                },
                artifact_uri=scope_artifact.artifact_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.COMPLETE,
                basis=(
                    "the maintained Graph Atlas backend was scanned to "
                    "exhaustion for the requested order; the catalog covers "
                    "the Graph Atlas representative set, not all "
                    "nonisomorphic graphs of that order in existence; this "
                    "enumeration was not independently checked"
                ),
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            relationships=relationships,
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=(
                    "deterministic NetworkX Graph Atlas enumeration; "
                    "nonisomorphism is provided by the backend and was not "
                    "independently re-verified"
                ),
            ),
            artifact_uris=(scope_artifact.artifact_uri, *graph_uris),
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _backend_suffix(operation: str) -> str:
    if operation == "DISJOINT_UNION":
        return "disjoint_union"
    if operation == "JOIN":
        return "join"
    if operation == "COMPLEMENT":
        return "complement"
    if operation == "LEXICOGRAPHIC_PRODUCT":
        return "lexicographic_product"
    raise ValueError(f"unsupported composition operation: {operation}")


def _apply_composition(
    operation: str,
    left: nx.Graph[Any],
    right: nx.Graph[Any] | None,
) -> nx.Graph[Any]:
    if operation == "DISJOINT_UNION":
        assert right is not None
        return cast("nx.Graph[Any]", nx.disjoint_union(left, right))
    if operation == "JOIN":
        assert right is not None
        return _join(left, right)
    if operation == "COMPLEMENT":
        return cast("nx.Graph[Any]", nx.complement(left))
    if operation == "LEXICOGRAPHIC_PRODUCT":
        assert right is not None
        return cast("nx.Graph[Any]", nx.lexicographic_product(left, right))
    raise ValueError(f"unsupported composition operation: {operation}")


def _join(left: nx.Graph[Any], right: nx.Graph[Any]) -> nx.Graph[Any]:
    """Construct the graph join: disjoint union plus all cross edges.

    NetworkX does not expose ``nx.join`` directly.  The join of G and H is
    the disjoint union of G and H with every vertex of G adjacent to every
    vertex of H.
    """
    result = cast("nx.Graph[Any]", nx.disjoint_union(left, right))
    left_count = left.number_of_nodes()
    right_count = right.number_of_nodes()
    cross_edges = [
        (i, left_count + j) for i in range(left_count) for j in range(right_count)
    ]
    result.add_edges_from(cross_edges)
    return result


def _composition_parents(
    validated: GraphCompositionRequest,
) -> tuple[str, ...]:
    if validated.right_graph_uri is not None:
        return (validated.left_graph_uri, validated.right_graph_uri)
    return (validated.left_graph_uri,)


def _graph_payload(graph: nx.Graph[Any]) -> dict[str, Any]:
    """Convert a NetworkX graph to the simple-undirected-graph payload schema.

    Nodes are relabeled to ``v0, v1, ...`` in sorted order.  Edges are
    emitted as two-element arrays in ascending label order.
    """
    sorted_nodes = sorted(graph.nodes)
    labels = {node: f"v{index}" for index, node in enumerate(sorted_nodes)}
    edges = sorted(
        [labels[source], labels[target]]
        if labels[source] < labels[target]
        else [labels[target], labels[source]]
        for source, target in graph.edges
    )
    return {
        "graph_schema_version": "1",
        "vertices": [labels[node] for node in sorted_nodes],
        "edges": edges,
    }


def _load_graph(
    resources: GraphCompositionResources,
    graph_uri: str,
) -> nx.Graph[str]:
    """Load and validate a simple-undirected-graph artifact.

    Mirrors the validation in ``graph_capabilities._load_graph`` but is
    self-contained so this module does not depend on private helpers from
    another adapter module.
    """
    try:
        artifact = resources.store.get(graph_uri)
    except StoreError as exc:
        raise CapabilityInvocationError(
            CapabilityDiagnostic(
                code="GRAPH_ARTIFACT_NOT_FOUND",
                stage="graph_resolution",
                message="The requested graph artifact is unavailable.",
                path="graph_uri",
                hint="Use a graph URI returned by a graph capability.",
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
                message=("The artifact is not a compatible simple undirected graph."),
                path="graph_uri",
                schema_uri=resources.graph_schema_uri,
                hint="Use a graph URI returned by a graph capability.",
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


def _runtime_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
