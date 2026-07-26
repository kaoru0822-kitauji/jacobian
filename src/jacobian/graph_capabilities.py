"""NetworkX-backed capabilities for small simple undirected graphs."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, cast

import networkx as nx
from pydantic import ValidationError

from jacobian.artifacts import ArtifactService
from jacobian.canonical import canonicalize_json
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
from jacobian.contracts.evidence import CertificateEnvelope, EvidenceBindings
from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.graph_invariants import (
    GraphNeighborhoodIndependenceArtifact,
    GraphNeighborhoodIndependenceClaim,
    GraphNeighborhoodIndependenceOutput,
    GraphNeighborhoodIndependenceRecord,
    GraphNeighborhoodIndependenceReplayPayload,
    GraphNeighborhoodIndependenceRequest,
)
from jacobian.contracts.results import Execution, ExecutionStatus
from jacobian.registry import CheckerRegistry
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
    neighborhood_schema_uri: str
    neighborhood_claim_schema_uri: str
    certificate_schema_uri: str
    neighborhood_checker_id: str | None


@dataclass(frozen=True, slots=True)
class GraphInstallation:
    semantics_uri: str
    graph_schema_uri: str
    scope_schema_uri: str
    property_schema_uri: str
    neighborhood_schema_uri: str
    neighborhood_claim_schema_uri: str
    certificate_schema_uri: str
    neighborhood_checker_id: str | None


def install_graph_capabilities(
    store: ArtifactStore,
    schemas: SchemaRegistry,
    artifacts: ArtifactService,
    checkers: CheckerRegistry,
    *,
    authorize_checker: bool,
) -> tuple[
    tuple[
        GraphAtlasSearchAdapter,
        GraphPropertyAdapter,
        GraphNeighborhoodIndependenceAdapter,
    ],
    GraphInstallation,
]:
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
    neighborhood_schema_uri = schemas.register(
        name="jacobian.graph-neighborhood-independence",
        version="1",
        schema=GraphNeighborhoodIndependenceArtifact.model_json_schema(),
    )
    neighborhood_claim_schema_uri = schemas.register(
        name="jacobian.graph-neighborhood-independence-claim",
        version="1",
        schema=GraphNeighborhoodIndependenceClaim.model_json_schema(),
    )
    certificate_schema_uri = schemas.register(
        name="jacobian.certificate-envelope",
        version="1",
        schema=CertificateEnvelope.model_json_schema(),
    )
    neighborhood_checker_id = None
    if authorize_checker:
        neighborhood_checker_id = checkers.authorize(
            name="exact graph neighborhood-independence replay checker",
            entrypoint=(
                "jacobian_checkers.graph_invariants:check_neighborhood_independence"
            ),
            evidence_kind="CERTIFICATE",
            format_id="graph.neighborhood_independence",
            format_version="1",
            claim_schema_uris=(neighborhood_claim_schema_uri,),
            semantics_uris=(semantics_uri,),
            candidate_schema_uris=(neighborhood_schema_uri,),
            reason="bundled independent finite-graph invariant checker",
        ).checker_id
    installation = GraphInstallation(
        semantics_uri=semantics_uri,
        graph_schema_uri=graph_schema_uri,
        scope_schema_uri=scope_schema_uri,
        property_schema_uri=property_schema_uri,
        neighborhood_schema_uri=neighborhood_schema_uri,
        neighborhood_claim_schema_uri=neighborhood_claim_schema_uri,
        certificate_schema_uri=certificate_schema_uri,
        neighborhood_checker_id=neighborhood_checker_id,
    )
    resources = GraphCapabilityResources(
        store=store,
        artifacts=artifacts,
        semantics_uri=semantics_uri,
        graph_schema_uri=graph_schema_uri,
        scope_schema_uri=scope_schema_uri,
        property_schema_uri=property_schema_uri,
        neighborhood_schema_uri=neighborhood_schema_uri,
        neighborhood_claim_schema_uri=neighborhood_claim_schema_uri,
        certificate_schema_uri=certificate_schema_uri,
        neighborhood_checker_id=neighborhood_checker_id,
    )
    return (
        (
            GraphAtlasSearchAdapter(resources),
            GraphPropertyAdapter(resources),
            GraphNeighborhoodIndependenceAdapter(resources),
        ),
        installation,
    )


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


class GraphNeighborhoodIndependenceAdapter:
    """Compute every exact neighborhood independence number for one graph."""

    def __init__(self, resources: GraphCapabilityResources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="graph.compute.neighborhood_independence",
            version="1",
            title="Compute neighborhood independence",
            description=(
                "Compute an exact maximum independent set in every open "
                "neighborhood, their sum, and their rational average. "
                "Neighborhoods are limited to 24 vertices."
            ),
            provider="jacobian.networkx",
            modes=(CapabilityMode.EXPLORE,),
            input_schema=GraphNeighborhoodIndependenceRequest.model_json_schema(),
            output_schema=GraphNeighborhoodIndependenceOutput.model_json_schema(),
            tags=(
                "graph",
                "neighborhood",
                "independence-number",
                "exact-computation",
            ),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        try:
            validated = GraphNeighborhoodIndependenceRequest.model_validate(
                request.input
            )
        except ValidationError as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_NEIGHBORHOOD_INDEPENDENCE_REQUEST",
                    stage="request_validation",
                    message=(
                        "The complete neighborhood-independence request is invalid."
                    ),
                )
            ) from exc
        started = time.monotonic()
        graph = _load_graph(self.resources, validated.graph_uri)
        if graph.number_of_nodes() > 256:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="GRAPH_ORDER_LIMIT_EXCEEDED",
                    stage="invariant_computation",
                    message=("The graph exceeds the exact 256-vertex profile limit."),
                )
            )
        records: list[GraphNeighborhoodIndependenceRecord] = []
        for vertex in sorted(graph):
            neighborhood = tuple(sorted(graph.neighbors(vertex)))
            if len(neighborhood) > 24:
                raise CapabilityInvocationError(
                    CapabilityDiagnostic(
                        code="NEIGHBORHOOD_ORDER_LIMIT_EXCEEDED",
                        stage="invariant_computation",
                        message=(
                            "At least one open neighborhood exceeds the exact "
                            "24-vertex operation limit."
                        ),
                        hint=(
                            "Use a structurally certified bound or a separately "
                            "budgeted solver-backed capability."
                        ),
                    )
                )
            neighborhood_graph: nx.Graph[str] = nx.Graph()
            neighborhood_graph.add_nodes_from(neighborhood)
            neighborhood_graph.add_edges_from(graph.subgraph(neighborhood).edges())
            independent_set, independence_number = nx.max_weight_clique(
                nx.complement(neighborhood_graph),
                weight=None,
            )
            records.append(
                GraphNeighborhoodIndependenceRecord(
                    vertex=vertex,
                    neighborhood=neighborhood,
                    independent_set=tuple(sorted(independent_set)),
                    independence_number=independence_number,
                )
            )
        total = sum(record.independence_number for record in records)
        average = Fraction(total, len(records)) if records else Fraction(0)
        average_wire = CanonicalRational(
            num=str(average.numerator),
            den=str(average.denominator),
        )
        invariant = GraphNeighborhoodIndependenceArtifact(
            graph_uri=validated.graph_uri,
            records=tuple(records),
            total=total,
            average=average_wire,
            backend_version=nx.__version__,
        )
        invariant_artifact = self.resources.artifacts.put(
            schema_uri=self.resources.neighborhood_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload=invariant.model_dump(mode="json"),
            parents=(validated.graph_uri,),
            summary="exact graph neighborhood-independence profile",
        )
        claim = GraphNeighborhoodIndependenceClaim(source_graph_uri=validated.graph_uri)
        claim_artifact = self.resources.artifacts.put(
            schema_uri=self.resources.neighborhood_claim_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload=claim.model_dump(mode="json"),
            parents=(validated.graph_uri, invariant_artifact.artifact_uri),
            summary="exact neighborhood-independence profile claim",
        )
        semantics = self.resources.store.get(self.resources.semantics_uri)
        source_graph = self.resources.store.get(validated.graph_uri)
        certificate_payload = GraphNeighborhoodIndependenceReplayPayload(
            source_graph_uri=validated.graph_uri,
            invariant_uri=invariant_artifact.artifact_uri,
        ).model_dump(mode="json")
        certificate = CertificateEnvelope(
            certificate_type="graph.neighborhood_independence",
            format_version="1",
            bindings=EvidenceBindings(
                claim_digest=claim_artifact.object_digest,
                semantics_digest=semantics.manifest.object_digest,
                candidate_digest=invariant_artifact.object_digest,
                scope_digest=source_graph.manifest.object_digest,
            ),
            payload_digest=(
                "sha256:"
                + hashlib.sha256(canonicalize_json(certificate_payload)).hexdigest()
            ),
            payload=certificate_payload,
        )
        certificate_artifact = self.resources.artifacts.put(
            schema_uri=self.resources.certificate_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload=certificate.model_dump(mode="json"),
            parents=(
                claim_artifact.artifact_uri,
                invariant_artifact.artifact_uri,
                validated.graph_uri,
            ),
            summary="unverified graph neighborhood-independence certificate",
        )
        output = GraphNeighborhoodIndependenceOutput(
            graph_uri=validated.graph_uri,
            invariant_uri=invariant_artifact.artifact_uri,
            claim_uri=claim_artifact.artifact_uri,
            certificate_uri=certificate_artifact.artifact_uri,
            checker_id=self.resources.neighborhood_checker_id,
            records=tuple(records),
            total=total,
            average=average_wire,
            backend_version=nx.__version__,
        )
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(
                status=ExecutionStatus.COMPLETED,
                runtime_ms=_runtime_ms(started),
            ),
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description=(
                    "all open neighborhoods of one finite simple undirected graph"
                ),
                parameters={
                    "graph_uri": validated.graph_uri,
                    "graph_order": graph.number_of_nodes(),
                    "maximum_neighborhood_order": 24,
                },
                artifact_uri=validated.graph_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.COMPLETE,
                basis=(
                    "every open neighborhood was solved exactly within the "
                    "advertised 24-vertex limit; verification remains separate"
                ),
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            relationships=(
                CapabilityRelationship(
                    relation_id=("graph.relation.neighborhood-independence-profile-of"),
                    source_artifact_uris=(validated.graph_uri,),
                    target_artifact_uris=(invariant_artifact.artifact_uri,),
                ),
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=(
                    "NetworkX exact maximum-clique computations on complement "
                    "neighborhoods; the bundled certificate was not invoked"
                ),
            ),
            artifact_uris=(
                validated.graph_uri,
                invariant_artifact.artifact_uri,
                claim_artifact.artifact_uri,
                certificate_artifact.artifact_uri,
            ),
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
