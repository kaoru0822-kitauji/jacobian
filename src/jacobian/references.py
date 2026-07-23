"""Operator bootstrap for the two v0.1 reference domains."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from jacobian.artifacts import ArtifactService
from jacobian.contracts.claims import ClaimSpec
from jacobian.contracts.evidence import (
    CertificateEnvelope,
    WitnessEnvelope,
)
from jacobian.contracts.plugins import PluginManifest
from jacobian.plugins.registry import PluginRegistry
from jacobian.registry import CheckerRegistry
from jacobian.schema_registry import SchemaRegistry
from jacobian.store import ArtifactStore


@dataclass(frozen=True, slots=True)
class ReferenceInstallation:
    name: str
    plugin_id: str
    semantics_uri: str
    claim_schema_uri: str
    candidate_schema_uri: str
    witness_schema_uri: str
    certificate_schema_uri: str
    witness_checker_ids: dict[str, str]
    certificate_checker_ids: dict[str, str]
    preservation_checker_ids: dict[str, str]


class ReferenceInstaller:
    def __init__(
        self,
        store: ArtifactStore,
        schemas: SchemaRegistry,
        artifacts: ArtifactService,
        plugins: PluginRegistry,
        checkers: CheckerRegistry,
    ) -> None:
        self.store = store
        self.schemas = schemas
        self.artifacts = artifacts
        self.plugins = plugins
        self.checkers = checkers
        self.manifest_schema_uri = schemas.register(
            name="jacobian.plugin-manifest",
            version="1",
            schema=PluginManifest.model_json_schema(),
        )
        self.witness_schema_uri = schemas.register(
            name="jacobian.witness-envelope",
            version="1",
            schema=WitnessEnvelope.model_json_schema(),
        )
        self.certificate_schema_uri = schemas.register(
            name="jacobian.certificate-envelope",
            version="1",
            schema=CertificateEnvelope.model_json_schema(),
        )
        self.manifest_semantics_uri = store.register_descriptor(
            kind="semantics",
            name="jacobian.plugin-manifest",
            version="1",
            definition={"description": "untrusted domain capability metadata"},
        )

    def install_all(self) -> dict[str, ReferenceInstallation]:
        graph = self.install_graph_paths()
        matrix = self.install_matrices()
        return {graph.name: graph, matrix.name: matrix}

    def install_graph_paths(self) -> ReferenceInstallation:
        domain = "jacobian.graph-paths"
        semantics = self.store.register_descriptor(
            kind="semantics",
            name=domain,
            version="1",
            definition={
                "description": (
                    "finite directed graphs, underlying-edge bipartiteness, "
                    "and all simple source-terminal paths"
                ),
                "path_semantics": "all simple paths induced by graph arcs",
                "bipartite_semantics": "underlying undirected graph",
            },
        )
        claim_schema = self.schemas.register(
            name=f"{domain}.claim",
            version="1",
            schema=_claim_schema(
                predicate_parameters={
                    "intended_paths_complete": {
                        "type": "object",
                        "properties": {
                            "simple": {"const": True},
                            "max_path_length": {
                                "type": "integer",
                                "minimum": 1,
                            },
                        },
                        "required": ["simple"],
                        "additionalProperties": False,
                    },
                    "is_bipartite": {
                        "type": "object",
                        "maxProperties": 0,
                    },
                }
            ),
        )
        candidate_schema = self.schemas.register(
            name=f"{domain}.candidate",
            version="1",
            schema=_graph_candidate_schema(),
        )
        capabilities = self._capabilities(
            {
                "Evaluator": ("jacobian.plugins.graph_paths:evaluate_capability"),
                "WitnessOracle": (
                    "jacobian.plugins.graph_paths:find_witness_capability"
                ),
                "Reducer": ("jacobian.plugins.graph_paths:reductions_capability"),
                "SemanticEnumerator": ("jacobian.plugins.graph_paths:materialize"),
            }
        )
        plugin_id = self._install_manifest(
            domain=domain,
            semantics_uri=semantics,
            claim_schema_uri=claim_schema,
            candidate_schema_uri=candidate_schema,
            capabilities=capabilities,
        )
        witness_checkers = {
            "graph.omitted_path": self._authorize_checker(
                name="graph omitted-path witness checker",
                entrypoint=("jacobian_checkers.graph_paths:check_omitted_path"),
                evidence_kind="WITNESS",
                format_id="graph.omitted_path",
                claim_schema=claim_schema,
                semantics=semantics,
                candidate_schema=candidate_schema,
            ),
            "graph.odd_cycle": self._authorize_checker(
                name="graph odd-cycle witness checker",
                entrypoint="jacobian_checkers.graph_paths:check_odd_cycle",
                evidence_kind="WITNESS",
                format_id="graph.odd_cycle",
                claim_schema=claim_schema,
                semantics=semantics,
                candidate_schema=candidate_schema,
            ),
            "graph.2coloring": self._authorize_checker(
                name="graph two-coloring witness checker",
                entrypoint="jacobian_checkers.graph_paths:check_two_coloring",
                evidence_kind="WITNESS",
                format_id="graph.2coloring",
                claim_schema=claim_schema,
                semantics=semantics,
                candidate_schema=candidate_schema,
            ),
        }
        certificate_checkers = {
            "graph.path_enumeration": self._authorize_checker(
                name="graph path-enumeration certificate checker",
                entrypoint=("jacobian_checkers.graph_paths:check_path_enumeration"),
                evidence_kind="CERTIFICATE",
                format_id="graph.path_enumeration",
                claim_schema=claim_schema,
                semantics=semantics,
                candidate_schema=candidate_schema,
            )
        }
        preservation_checkers = {
            "graph.counterexample_preservation": self._authorize_checker(
                name="graph counterexample preservation checker",
                entrypoint=(
                    "jacobian_checkers.graph_paths:check_counterexample_preservation"
                ),
                evidence_kind="PRESERVATION",
                format_id="graph.counterexample_preservation",
                claim_schema=claim_schema,
                semantics=semantics,
                candidate_schema=candidate_schema,
            )
        }
        return ReferenceInstallation(
            name="graph_paths",
            plugin_id=plugin_id,
            semantics_uri=semantics,
            claim_schema_uri=claim_schema,
            candidate_schema_uri=candidate_schema,
            witness_schema_uri=self.witness_schema_uri,
            certificate_schema_uri=self.certificate_schema_uri,
            witness_checker_ids=witness_checkers,
            certificate_checker_ids=certificate_checkers,
            preservation_checker_ids=preservation_checkers,
        )

    def install_matrices(self) -> ReferenceInstallation:
        domain = "jacobian.integer-matrices"
        semantics = self.store.register_descriptor(
            kind="semantics",
            name=domain,
            version="1",
            definition={
                "description": (
                    "finite rectangular integer matrices with exact rational "
                    "kernel witnesses and bounded determinant scopes"
                )
            },
        )
        claim_schema = self.schemas.register(
            name=f"{domain}.claim",
            version="1",
            schema=_claim_schema(
                predicate_parameters={
                    "is_nonsingular": {
                        "type": "object",
                        "maxProperties": 0,
                    },
                    "maximize_absolute_determinant": {
                        "type": "object",
                        "properties": {
                            "scope": _matrix_scope_schema(),
                        },
                        "required": ["scope"],
                        "additionalProperties": False,
                    },
                }
            ),
        )
        candidate_schema = self.schemas.register(
            name=f"{domain}.candidate",
            version="1",
            schema=_matrix_candidate_schema(),
        )
        capabilities = self._capabilities(
            {
                "Evaluator": ("jacobian.plugins.matrices:evaluate_capability"),
                "WitnessOracle": ("jacobian.plugins.matrices:find_witness_capability"),
                "Reducer": "jacobian.plugins.matrices:reductions_capability",
                "SemanticEnumerator": ("jacobian.plugins.matrices:materialize"),
            }
        )
        plugin_id = self._install_manifest(
            domain=domain,
            semantics_uri=semantics,
            claim_schema_uri=claim_schema,
            candidate_schema_uri=candidate_schema,
            capabilities=capabilities,
        )
        witness_checkers = {
            "matrix.kernel_vector": self._authorize_checker(
                name="matrix rational-kernel witness checker",
                entrypoint=("jacobian_checkers.matrices:check_kernel_vector"),
                evidence_kind="WITNESS",
                format_id="matrix.kernel_vector",
                claim_schema=claim_schema,
                semantics=semantics,
                candidate_schema=candidate_schema,
            ),
            "matrix.maximizer": self._authorize_checker(
                name="matrix maximum-determinant witness checker",
                entrypoint=("jacobian_checkers.matrices:check_maximizer_witness"),
                evidence_kind="WITNESS",
                format_id="matrix.maximizer",
                claim_schema=claim_schema,
                semantics=semantics,
                candidate_schema=candidate_schema,
            ),
        }
        certificate_checkers = {
            "matrix.maxdet_enumeration": self._authorize_checker(
                name="matrix max-determinant enumeration checker",
                entrypoint=("jacobian_checkers.matrices:check_maxdet_enumeration"),
                evidence_kind="CERTIFICATE",
                format_id="matrix.maxdet_enumeration",
                claim_schema=claim_schema,
                semantics=semantics,
                candidate_schema=candidate_schema,
            )
        }
        preservation_checkers = {
            "matrix.singular_preservation": self._authorize_checker(
                name="matrix singularity preservation checker",
                entrypoint=("jacobian_checkers.matrices:check_singular_preservation"),
                evidence_kind="PRESERVATION",
                format_id="matrix.singular_preservation",
                claim_schema=claim_schema,
                semantics=semantics,
                candidate_schema=candidate_schema,
            )
        }
        return ReferenceInstallation(
            name="matrices",
            plugin_id=plugin_id,
            semantics_uri=semantics,
            claim_schema_uri=claim_schema,
            candidate_schema_uri=candidate_schema,
            witness_schema_uri=self.witness_schema_uri,
            certificate_schema_uri=self.certificate_schema_uri,
            witness_checker_ids=witness_checkers,
            certificate_checker_ids=certificate_checkers,
            preservation_checker_ids=preservation_checkers,
        )

    def _capabilities(
        self,
        entrypoints: dict[str, str],
    ) -> dict[str, dict[str, str]]:
        capabilities: dict[str, dict[str, str]] = {}
        for name, entrypoint in entrypoints.items():
            implementation = self.plugins.register_implementation(entrypoint)
            capabilities[name] = {
                "implementation_uri": implementation,
                "entrypoint": entrypoint,
                "version": "1",
            }
        return capabilities

    def _install_manifest(
        self,
        *,
        domain: str,
        semantics_uri: str,
        claim_schema_uri: str,
        candidate_schema_uri: str,
        capabilities: dict[str, dict[str, str]],
    ) -> str:
        manifest = self.artifacts.put(
            schema_uri=self.manifest_schema_uri,
            semantics_uri=self.manifest_semantics_uri,
            payload={
                "plugin_schema_version": "1",
                "domain_id": domain,
                "domain_version": "1",
                "semantics_uri": semantics_uri,
                "claim_schema_uri": claim_schema_uri,
                "candidate_schema_uri": candidate_schema_uri,
                "witness_schema_uris": [self.witness_schema_uri],
                "certificate_schema_uris": [self.certificate_schema_uri],
                "capabilities": capabilities,
            },
            summary=f"reference plugin: {domain}",
        )
        self.plugins.install(manifest.artifact_uri)
        return manifest.artifact_uri

    def _authorize_checker(
        self,
        *,
        name: str,
        entrypoint: str,
        evidence_kind: str,
        format_id: str,
        claim_schema: str,
        semantics: str,
        candidate_schema: str,
    ) -> str:
        registration = self.checkers.authorize(
            name=name,
            entrypoint=entrypoint,
            evidence_kind=evidence_kind,
            format_id=format_id,
            format_version="1",
            claim_schema_uris=(claim_schema,),
            semantics_uris=(semantics,),
            candidate_schema_uris=(candidate_schema,),
            reason="bundled v0.1 reference checker",
        )
        return registration.checker_id


def reference_catalog(
    references: dict[str, ReferenceInstallation],
) -> dict[str, Any]:
    """Return stable operator-facing identifiers for installed references."""

    return {
        name: {
            "plugin_id": reference.plugin_id,
            "semantics_uri": reference.semantics_uri,
            "claim_schema_uri": reference.claim_schema_uri,
            "candidate_schema_uri": reference.candidate_schema_uri,
            "witness_schema_uri": reference.witness_schema_uri,
            "certificate_schema_uri": reference.certificate_schema_uri,
            "witness_checker_ids": reference.witness_checker_ids,
            "certificate_checker_ids": reference.certificate_checker_ids,
            "preservation_checker_ids": reference.preservation_checker_ids,
        }
        for name, reference in sorted(references.items())
    }


def _claim_schema(
    *,
    predicate_parameters: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    schema = deepcopy(ClaimSpec.model_json_schema())
    predicate = schema["$defs"]["PredicateSpec"]
    predicate["properties"]["name"]["enum"] = list(predicate_parameters)
    schema["allOf"] = [
        {
            "if": {
                "properties": {
                    "predicate": {
                        "properties": {"name": {"const": name}},
                        "required": ["name"],
                    }
                },
                "required": ["predicate"],
            },
            "then": {
                "properties": {
                    "predicate": {"properties": {"parameters": parameter_schema}}
                }
            },
        }
        for name, parameter_schema in predicate_parameters.items()
    ]
    return schema


def _matrix_scope_schema() -> dict[str, Any]:
    exact_integer = {
        "oneOf": [
            {"type": "integer"},
            {"type": "string", "pattern": r"^-?(?:0|[1-9][0-9]*)$"},
        ]
    }
    return {
        "type": "object",
        "properties": {
            "rows": {"type": "integer", "minimum": 1, "maximum": 64},
            "cols": {"type": "integer", "minimum": 1, "maximum": 64},
            "entries": {
                "type": "array",
                "minItems": 1,
                "maxItems": 64,
                "uniqueItems": True,
                "items": exact_integer,
            },
        },
        "required": ["rows", "cols", "entries"],
        "additionalProperties": False,
    }


def _graph_candidate_schema() -> dict[str, Any]:
    vertex = {"type": "string", "minLength": 1, "maxLength": 128}
    path = {
        "type": "array",
        "minItems": 2,
        "uniqueItems": True,
        "items": vertex,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "vertices": {
                "type": "array",
                "minItems": 1,
                "maxItems": 128,
                "uniqueItems": True,
                "items": vertex,
            },
            "arcs": {
                "type": "array",
                "maxItems": 4096,
                "uniqueItems": True,
                "items": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 2,
                    "prefixItems": [vertex, vertex],
                    "items": False,
                },
            },
            "source": vertex,
            "terminals": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": vertex,
            },
            "intended_paths": {
                "type": "array",
                "uniqueItems": True,
                "items": path,
            },
        },
        "required": ["vertices", "arcs"],
        "additionalProperties": False,
    }


def _matrix_candidate_schema() -> dict[str, Any]:
    exact_integer = {
        "oneOf": [
            {"type": "integer"},
            {"type": "string", "pattern": r"^-?(?:0|[1-9][0-9]*)$"},
        ]
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "rows": {"type": "integer", "minimum": 1, "maximum": 64},
            "cols": {"type": "integer", "minimum": 1, "maximum": 64},
            "entries": {
                "type": "array",
                "minItems": 1,
                "maxItems": 64,
                "items": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 64,
                    "items": exact_integer,
                },
            },
        },
        "required": ["rows", "cols", "entries"],
        "additionalProperties": False,
    }
