"""NetworkX-backed capabilities for small simple undirected graphs."""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Literal, cast

import networkx as nx
from pydantic import ValidationError

from jacobian.artifacts import ArtifactService
from jacobian.canonical import canonicalize_json
from jacobian.capabilities import CapabilityInvocationError
from jacobian.checker_installation import CheckerInstaller
from jacobian.checker_operations import CheckerOperation
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
from jacobian.contracts.checkers import EvidenceKind
from jacobian.contracts.evidence import CertificateEnvelope, EvidenceBindings
from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.graph_degree_sequence import (
    GraphDegreeSequenceClaim,
    GraphDegreeSequenceObstruction,
    GraphDegreeSequenceOutput,
    GraphDegreeSequenceReplayPayload,
    GraphDegreeSequenceRequest,
    GraphDegreeSequenceResultArtifact,
)
from jacobian.contracts.graph_invariants import (
    GraphNeighborhoodIndependenceArtifact,
    GraphNeighborhoodIndependenceClaim,
    GraphNeighborhoodIndependenceOutput,
    GraphNeighborhoodIndependenceRecord,
    GraphNeighborhoodIndependenceReplayPayload,
    GraphNeighborhoodIndependenceRequest,
)
from jacobian.contracts.results import Execution, ExecutionStatus
from jacobian.provider_runtime import known_provider_runtime
from jacobian.registry import CheckerRegistry
from jacobian.schema_registry import SchemaRegistry, model_schema
from jacobian.store import ArtifactStore, StoreError

_ARTIFACT_URI_PATTERN = r"^artifact://sha256/[0-9a-f]{64}$"
_PROPERTY_NAMES = (
    "bipartite",
    "connected",
    "degree_sequence",
    "diameter",
    "eccentricities",
    "girth",
    "harmonic_index",
    "havel_hakimi_trace",
    "independence_number",
    "maximum_degree",
    "minimum_degree",
    "order",
    "radius",
    "residue",
    "size",
    "tree",
    "triangle_count",
    "triangle_frequencies",
    "average_eccentricity",
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
    degree_sequence_claim_schema_uri: str
    degree_sequence_result_schema_uri: str
    neighborhood_schema_uri: str
    neighborhood_claim_schema_uri: str
    certificate_schema_uri: str
    degree_sequence_checker_id: str | None
    neighborhood_checker_id: str | None


@dataclass(frozen=True, slots=True)
class GraphInstallation:
    semantics_uri: str
    graph_schema_uri: str
    scope_schema_uri: str
    property_schema_uri: str
    degree_sequence_claim_schema_uri: str
    degree_sequence_result_schema_uri: str
    neighborhood_schema_uri: str
    neighborhood_claim_schema_uri: str
    certificate_schema_uri: str
    degree_sequence_checker_id: str | None
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
        GraphDegreeSequenceAdapter,
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
    degree_sequence_claim_schema_uri = schemas.register(
        name="jacobian.graph-degree-sequence-claim",
        version="1",
        schema=GraphDegreeSequenceClaim.model_json_schema(),
    )
    degree_sequence_result_schema_uri = schemas.register(
        name="jacobian.graph-degree-sequence-result",
        version="1",
        schema=GraphDegreeSequenceResultArtifact.model_json_schema(),
    )
    neighborhood_schema_uri = schemas.register(
        name="jacobian.graph-neighborhood-independence",
        version="1",
        schema=model_schema(GraphNeighborhoodIndependenceArtifact),
    )
    neighborhood_claim_schema_uri = schemas.register(
        name="jacobian.graph-neighborhood-independence-claim",
        version="1",
        schema=model_schema(GraphNeighborhoodIndependenceClaim),
    )
    certificate_schema_uri = schemas.register(
        name="jacobian.certificate-envelope",
        version="1",
        schema=model_schema(CertificateEnvelope),
    )
    degree_sequence_checker_id = None
    neighborhood_checker_id = None
    if authorize_checker:
        degree_sequence_checker_id = (
            CheckerInstaller(checkers)
            .install(
                CheckerOperation(
                    name="exact simple-graph degree-sequence replay checker",
                    entrypoint=(
                        "jacobian_checkers.graph_degree_sequence:check_degree_sequence"
                    ),
                    evidence_kind=EvidenceKind.CERTIFICATE,
                    format_id="graph.degree_sequence",
                    format_version="1",
                    claim_schema_uris=(degree_sequence_claim_schema_uri,),
                    semantics_uris=(semantics_uri,),
                    candidate_schema_uris=(degree_sequence_result_schema_uri,),
                    reason="bundled independent degree-sequence checker",
                ),
                authorize=True,
            )
            .checker_id
        )
        neighborhood_checker_id = (
            CheckerInstaller(checkers)
            .install(
                CheckerOperation(
                    name="exact graph neighborhood-independence replay checker",
                    entrypoint=(
                        "jacobian_checkers.graph_invariants:check_neighborhood_independence"
                    ),
                    evidence_kind=EvidenceKind.CERTIFICATE,
                    format_id="graph.neighborhood_independence",
                    format_version="1",
                    claim_schema_uris=(neighborhood_claim_schema_uri,),
                    semantics_uris=(semantics_uri,),
                    candidate_schema_uris=(neighborhood_schema_uri,),
                    reason="bundled independent finite-graph invariant checker",
                ),
                authorize=True,
            )
            .checker_id
        )
    installation = GraphInstallation(
        semantics_uri=semantics_uri,
        graph_schema_uri=graph_schema_uri,
        scope_schema_uri=scope_schema_uri,
        property_schema_uri=property_schema_uri,
        degree_sequence_claim_schema_uri=degree_sequence_claim_schema_uri,
        degree_sequence_result_schema_uri=degree_sequence_result_schema_uri,
        neighborhood_schema_uri=neighborhood_schema_uri,
        neighborhood_claim_schema_uri=neighborhood_claim_schema_uri,
        certificate_schema_uri=certificate_schema_uri,
        degree_sequence_checker_id=degree_sequence_checker_id,
        neighborhood_checker_id=neighborhood_checker_id,
    )
    resources = GraphCapabilityResources(
        store=store,
        artifacts=artifacts,
        semantics_uri=semantics_uri,
        graph_schema_uri=graph_schema_uri,
        scope_schema_uri=scope_schema_uri,
        property_schema_uri=property_schema_uri,
        degree_sequence_claim_schema_uri=degree_sequence_claim_schema_uri,
        degree_sequence_result_schema_uri=degree_sequence_result_schema_uri,
        neighborhood_schema_uri=neighborhood_schema_uri,
        neighborhood_claim_schema_uri=neighborhood_claim_schema_uri,
        certificate_schema_uri=certificate_schema_uri,
        degree_sequence_checker_id=degree_sequence_checker_id,
        neighborhood_checker_id=neighborhood_checker_id,
    )
    return (
        (
            GraphAtlasSearchAdapter(resources),
            GraphPropertyAdapter(resources),
            GraphDegreeSequenceAdapter(resources),
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
            provider_runtime=known_provider_runtime(
                "jacobian.networkx",
                features=("graph-atlas", "simple-undirected-graphs"),
            ),
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
            provider_runtime=known_provider_runtime(
                "jacobian.networkx",
                features=("graph-properties", "simple-undirected-graphs"),
            ),
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
        names = sorted(str(item) for item in request.input["properties"])
        try:
            selected = {
                name: _property_result(name, _compute_property(graph, name))
                for name in names
            }
        except nx.NetworkXError as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="GRAPH_PROPERTY_NOT_APPLICABLE",
                    stage="graph_property_computation",
                    message=str(exc),
                    hint=(
                        "Distance-based properties require a nonempty connected "
                        "graph; request structural properties separately."
                    ),
                )
            ) from exc
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


class GraphDegreeSequenceAdapter:
    """Realize a simple-graph degree sequence or expose an exact obstruction."""

    def __init__(self, resources: GraphCapabilityResources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="graph.realize.degree_sequence",
            version="1",
            title="Realize a simple-graph degree sequence",
            description=(
                "Construct a simple graph with the requested degree multiset, or "
                "return an odd-sum, maximum-degree, or Erdos-Gallai obstruction."
            ),
            provider="jacobian.networkx",
            provider_runtime=known_provider_runtime(
                "jacobian.networkx",
                features=("degree-sequence", "simple-undirected-graphs"),
                checker_ids=(
                    (resources.degree_sequence_checker_id,)
                    if resources.degree_sequence_checker_id is not None
                    else ()
                ),
            ),
            modes=(CapabilityMode.EXPLORE,),
            input_schema=GraphDegreeSequenceRequest.model_json_schema(),
            output_schema=GraphDegreeSequenceOutput.model_json_schema(),
            tags=(
                "graph",
                "degree-sequence",
                "construction",
                "counterexample",
            ),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        try:
            validated = GraphDegreeSequenceRequest.model_validate(request.input)
        except ValidationError as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_DEGREE_SEQUENCE_REQUEST",
                    stage="request_validation",
                    message="The complete degree-sequence request is invalid.",
                    hint=("Provide between 1 and 512 nonnegative integer degrees."),
                )
            ) from exc
        started = time.monotonic()
        sequence = tuple(validated.degree_sequence)
        obstruction = _degree_sequence_obstruction(sequence)
        graph_payload: dict[str, Any] | None = None
        graph_uri: str | None = None
        graph_artifact = None
        conclusion: Literal["GRAPHICAL", "NON_GRAPHICAL"]
        method: Literal[
            "EXACT_DEGREE_REPLAY",
            "ODD_SUM_OBSTRUCTION",
            "MAX_DEGREE_OBSTRUCTION",
            "ERDOS_GALLAI_OBSTRUCTION",
        ]
        if obstruction is None:
            graph = nx.havel_hakimi_graph(sequence)
            graph_payload = _graph_payload(graph)
            graph_artifact = self.resources.artifacts.put(
                schema_uri=self.resources.graph_schema_uri,
                semantics_uri=self.resources.semantics_uri,
                payload=graph_payload,
                summary="simple graph realizing the requested degree sequence",
            )
            graph_uri = graph_artifact.artifact_uri
            conclusion = "GRAPHICAL"
            method = "EXACT_DEGREE_REPLAY"
        else:
            conclusion = "NON_GRAPHICAL"
            method = cast(
                Literal[
                    "ODD_SUM_OBSTRUCTION",
                    "MAX_DEGREE_OBSTRUCTION",
                    "ERDOS_GALLAI_OBSTRUCTION",
                ],
                {
                    "ODD_SUM": "ODD_SUM_OBSTRUCTION",
                    "MAX_DEGREE": "MAX_DEGREE_OBSTRUCTION",
                    "ERDOS_GALLAI": "ERDOS_GALLAI_OBSTRUCTION",
                }[obstruction.kind],
            )
        claim = GraphDegreeSequenceClaim(degree_sequence=sequence)
        claim_artifact = self.resources.artifacts.put(
            schema_uri=self.resources.degree_sequence_claim_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload=claim.model_dump(mode="json"),
            summary="simple-graph degree-sequence realizability claim",
        )
        result_artifact_payload = GraphDegreeSequenceResultArtifact(
            degree_sequence=sequence,
            conclusion=conclusion,
            graph_uri=graph_uri,
            graph=graph_payload,
            obstruction=obstruction,
        )
        result_parents = (
            (claim_artifact.artifact_uri, graph_uri)
            if graph_uri is not None
            else (claim_artifact.artifact_uri,)
        )
        result_artifact = self.resources.artifacts.put(
            schema_uri=self.resources.degree_sequence_result_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload=result_artifact_payload.model_dump(
                mode="json",
                exclude_none=True,
            ),
            parents=result_parents,
            summary=f"exact degree-sequence result: {conclusion.lower()}",
        )
        semantics = self.resources.store.get(self.resources.semantics_uri)
        certificate_payload = GraphDegreeSequenceReplayPayload(
            method=method,
            degree_sequence=sequence,
            conclusion=conclusion,
            graph_uri=graph_uri,
            obstruction=obstruction,
        ).model_dump(mode="json", exclude_none=True)
        certificate = CertificateEnvelope(
            certificate_type="graph.degree_sequence",
            format_version="1",
            bindings=EvidenceBindings(
                claim_digest=claim_artifact.object_digest,
                semantics_digest=semantics.manifest.object_digest,
                candidate_digest=result_artifact.object_digest,
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
                result_artifact.artifact_uri,
            ),
            summary="unverified exact degree-sequence replay certificate",
        )
        output = GraphDegreeSequenceOutput(
            degree_sequence=sequence,
            conclusion=conclusion,
            graph_uri=graph_uri,
            graph=graph_payload,
            obstruction=obstruction,
            result_uri=result_artifact.artifact_uri,
            claim_uri=claim_artifact.artifact_uri,
            certificate_uri=certificate_artifact.artifact_uri,
            checker_id=self.resources.degree_sequence_checker_id,
            backend_version=nx.__version__,
        )
        artifact_uris = [
            claim_artifact.artifact_uri,
            result_artifact.artifact_uri,
            certificate_artifact.artifact_uri,
        ]
        if graph_artifact is not None:
            artifact_uris.insert(0, graph_artifact.artifact_uri)
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(
                status=ExecutionStatus.COMPLETED,
                runtime_ms=_runtime_ms(started),
            ),
            output=output.model_dump(mode="json", exclude_none=True),
            scope=CapabilityScope(
                description="one finite nonnegative integer degree sequence",
                parameters={
                    "degree_sequence": list(sequence),
                    "graph_model": "finite simple undirected graph",
                },
                artifact_uri=claim_artifact.artifact_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.COMPLETE,
                basis=(
                    "the result carries either a full graph realization or one "
                    "necessary-condition obstruction; verification remains separate"
                ),
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            relationships=(
                CapabilityRelationship(
                    relation_id="graph.relation.degree-sequence-result",
                    source_artifact_uris=(claim_artifact.artifact_uri,),
                    target_artifact_uris=(result_artifact.artifact_uri,),
                ),
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=(
                    "deterministic NetworkX construction or exact integer "
                    "obstruction; the bundled certificate was not invoked"
                ),
            ),
            artifact_uris=tuple(artifact_uris),
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
            provider_runtime=known_provider_runtime(
                "jacobian.networkx",
                features=("neighborhood-independence", "simple-undirected-graphs"),
                checker_ids=(
                    (resources.neighborhood_checker_id,)
                    if resources.neighborhood_checker_id is not None
                    else ()
                ),
            ),
            modes=(CapabilityMode.EXPLORE,),
            input_schema=model_schema(GraphNeighborhoodIndependenceRequest),
            output_schema=model_schema(GraphNeighborhoodIndependenceOutput),
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


def _degree_sequence_obstruction(
    sequence: tuple[int, ...],
) -> GraphDegreeSequenceObstruction | None:
    order = len(sequence)
    for index, degree in enumerate(sequence):
        if degree >= order:
            return GraphDegreeSequenceObstruction(
                kind="MAX_DEGREE",
                index=index,
                degree=degree,
                order=order,
            )
    degree_sum = sum(sequence)
    if degree_sum % 2:
        return GraphDegreeSequenceObstruction(
            kind="ODD_SUM",
            degree_sum=degree_sum,
        )
    ordered = sorted(sequence, reverse=True)
    for k in range(1, order + 1):
        lhs = sum(ordered[:k])
        rhs = k * (k - 1) + sum(min(degree, k) for degree in ordered[k:])
        if lhs > rhs:
            return GraphDegreeSequenceObstruction(
                kind="ERDOS_GALLAI",
                k=k,
                lhs=lhs,
                rhs=rhs,
            )
    if not nx.is_graphical(sequence, method="eg"):
        raise RuntimeError(
            "NetworkX rejected a degree sequence without a replayable obstruction"
        )
    return None


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


def _compute_property(graph: nx.Graph[Any], name: str) -> Any:
    """Compute only the requested outcome instead of the full property portfolio."""

    if name == "order":
        return graph.number_of_nodes()
    if name == "size":
        return graph.number_of_edges()
    if name == "connected":
        return nx.is_connected(graph) if graph else False
    if name == "bipartite":
        return nx.is_bipartite(graph)
    if name == "tree":
        return nx.is_tree(graph) if graph else False
    if name in {"degree_sequence", "minimum_degree", "maximum_degree"}:
        degrees = sorted((degree for _, degree in graph.degree), reverse=True)
        if name == "degree_sequence":
            return degrees
        if name == "minimum_degree":
            return min(degrees) if degrees else None
        return max(degrees) if degrees else None
    if name == "triangle_count":
        return sum(cast(dict[Any, int], nx.triangles(graph)).values()) // 3
    if name == "independence_number":
        if not graph:
            return 0
        independent_set, independence_number = nx.max_weight_clique(
            nx.complement(graph),
            weight=None,
        )
        assert len(independent_set) == independence_number
        return independence_number
    if name == "girth":
        value = nx.girth(graph)
        return None if math.isinf(value) else int(value)
    if name in {"eccentricities", "diameter", "radius", "average_eccentricity"}:
        if not graph:
            raise nx.NetworkXPointlessConcept(
                "distance properties are undefined for the null graph"
            )
        eccentricities = cast(dict[Any, int], nx.eccentricity(graph))
        ordered = {
            str(vertex): eccentricities[vertex]
            for vertex in sorted(eccentricities, key=str)
        }
        if name == "eccentricities":
            return ordered
        if name == "diameter":
            return max(eccentricities.values(), default=0)
        if name == "radius":
            return min(eccentricities.values(), default=0)
        total = sum(eccentricities.values())
        return _rational_payload(Fraction(total, len(eccentricities)))
    if name == "triangle_frequencies":
        frequencies = cast(dict[Any, int], nx.triangles(graph))
        return {
            str(vertex): frequencies[vertex] for vertex in sorted(frequencies, key=str)
        }
    if name == "harmonic_index":
        harmonic_value = Fraction(0)
        for source, target in graph.edges:
            harmonic_value += Fraction(
                2,
                graph.degree[source] + graph.degree[target],
            )
        return _rational_payload(harmonic_value)
    if name in {"havel_hakimi_trace", "residue"}:
        trace = _havel_hakimi_trace(graph)
        return trace if name == "havel_hakimi_trace" else len(trace[-1])
    raise AssertionError(f"unsupported graph property: {name}")


def _havel_hakimi_trace(graph: nx.Graph[Any]) -> list[list[int]]:
    sequence = sorted((degree for _, degree in graph.degree), reverse=True)
    trace = [sequence.copy()]
    while sequence and sequence[0] > 0:
        degree = sequence.pop(0)
        if degree > len(sequence):
            raise nx.NetworkXError("degree sequence became non-graphical")
        for index in range(degree):
            sequence[index] -= 1
            if sequence[index] < 0:
                raise nx.NetworkXError("degree sequence became non-graphical")
        sequence.sort(reverse=True)
        trace.append(sequence.copy())
    return trace


def _rational_payload(value: Fraction) -> dict[str, str]:
    return {"num": str(value.numerator), "den": str(value.denominator)}


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
