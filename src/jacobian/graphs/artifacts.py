"""Canonical graph artifacts and the shared graph storage boundary."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from jacobian.artifacts import ArtifactService
from jacobian.capabilities import CapabilityInvocationError
from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.graphs.atlas import networkx_loader
from jacobian.store import ArtifactStore, StoreError

if TYPE_CHECKING:
    import networkx as nx_type


ARTIFACT_URI_PATTERN = r"^artifact://sha256/[0-9a-f]{64}$"

GRAPH_PAYLOAD_SCHEMA: dict[str, Any] = {
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


@dataclass(frozen=True, slots=True)
class GraphArtifactResources:
    """The common storage and semantics needed by graph outcomes."""

    store: ArtifactStore
    artifacts: ArtifactService
    semantics_uri: str
    graph_schema_uri: str


def nx() -> Any:
    """Load NetworkX only when a graph capability is invoked."""

    return networkx_loader.get()


def graph_payload(graph: nx_type.Graph[Any]) -> dict[str, Any]:
    """Serialize a backend graph into the canonical graph artifact payload."""

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


def load_graph(resources: GraphArtifactResources, graph_uri: str) -> nx_type.Graph[str]:
    """Load and validate one graph artifact against the installed graph contract."""

    try:
        artifact = resources.store.get(graph_uri)
    except StoreError as exc:
        raise CapabilityInvocationError(
            CapabilityDiagnostic(
                code="GRAPH_ARTIFACT_NOT_FOUND",
                stage="graph_resolution",
                message="The requested graph artifact is unavailable.",
                path="graph_uri",
                hint=(
                    "Use a graph URI returned by graph.construct.explicit, "
                    "graph.search.atlas, or another graph-domain producer."
                ),
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
                hint=(
                    "Use a graph URI returned by graph.construct.explicit, "
                    "graph.search.atlas, or another graph-domain producer."
                ),
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
    graph: nx_type.Graph[str] = nx().Graph()
    graph.add_nodes_from(vertices)
    graph.add_edges_from(normalized_edges)
    return graph


def runtime_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))


__all__ = [
    "ARTIFACT_URI_PATTERN",
    "GRAPH_PAYLOAD_SCHEMA",
    "GraphArtifactResources",
    "graph_payload",
    "load_graph",
    "nx",
    "runtime_ms",
]
