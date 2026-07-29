"""Deterministic MiniF2F and ProofNet row materialization."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

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
    CapabilityRequest,
    CapabilityResult,
    CapabilityScope,
)
from jacobian.contracts.formal_datasets import (
    FormalDatasetArtifact,
    FormalDatasetDiagnostic,
    FormalDatasetMaterializeOutput,
    FormalDatasetMaterializeRequest,
    FormalPreprocessingDecision,
)
from jacobian.contracts.results import Execution, ExecutionStatus
from jacobian.domains._examples import example
from jacobian.provider_runtime import jacobian_provider_runtime
from jacobian.schema_registry import SchemaRegistry
from jacobian.store import ArtifactStore
from jacobian_checkers.lean4 import LEAN_VERSION, MATHLIB_COMMIT


def _json_digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonicalize_json(value)).hexdigest()


def _text_digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_text(value: str) -> str:
    lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip("\n") + "\n"


def _diagnostics(
    request: FormalDatasetMaterializeRequest,
) -> tuple[FormalDatasetDiagnostic, ...]:
    diagnostics = [
        FormalDatasetDiagnostic(
            code="EXECUTION_NOT_REQUESTED",
            message=(
                "The row was materialized but not executed; submit the normalized "
                "source to a compatible Lean project or verification capability."
            ),
        )
    ]
    environment = request.environment
    if environment.lean_version != LEAN_VERSION:
        diagnostics.append(
            FormalDatasetDiagnostic(
                code="LEAN_VERSION_NOT_PINNED_RUNTIME",
                message=(
                    f"The row requires Lean {environment.lean_version}; Jacobian's "
                    f"pinned runtime is Lean {LEAN_VERSION}."
                ),
            )
        )
    if (
        environment.mathlib_revision is not None
        and environment.mathlib_revision != MATHLIB_COMMIT
    ):
        diagnostics.append(
            FormalDatasetDiagnostic(
                code="MATHLIB_REVISION_NOT_PINNED_RUNTIME",
                message=(
                    "The declared Mathlib revision differs from Jacobian's pinned "
                    "runtime; execution requires the declared project checkout."
                ),
            )
        )
    if not environment.project_files:
        diagnostics.append(
            FormalDatasetDiagnostic(
                code="PROJECT_FILES_UNDECLARED",
                message=(
                    "No project-file digests were supplied; materialization is "
                    "deterministic, but project compatibility is not established."
                ),
            )
        )
    return tuple(diagnostics)


@dataclass(frozen=True, slots=True)
class FormalDatasetInstallation:
    semantics_uri: str
    artifact_schema_uri: str


class FormalDatasetMaterializeAdapter:
    """Materialize one pinned formal-dataset row into a replayable artifact."""

    def __init__(
        self,
        store: ArtifactStore,
        artifacts: ArtifactService,
        *,
        semantics_uri: str,
        artifact_schema_uri: str,
    ) -> None:
        self.store = store
        self.artifacts = artifacts
        self.semantics_uri = semantics_uri
        self.artifact_schema_uri = artifact_schema_uri
        self._descriptor = CapabilityDescriptor(
            capability_id="dataset.formal.materialize",
            version="1",
            title="Materialize one pinned formal-dataset row",
            description=(
                "Normalize one MiniF2F or ProofNet row and bind its dataset, "
                "source, Lean-project, preprocessing, and execution provenance."
            ),
            provider="jacobian.formal-datasets",
            provider_runtime=jacobian_provider_runtime(
                "jacobian.formal-datasets",
                features=("MINIF2F", "PROOFNET", "deterministic-materialization"),
            ),
            modes=(CapabilityMode.EXPLORE,),
            input_schema=FormalDatasetMaterializeRequest.model_json_schema(),
            output_schema=FormalDatasetMaterializeOutput.model_json_schema(),
            tags=("dataset", "formal-mathematics", "lean", "provenance"),
            invocation_examples=(
                example(
                    "minif2f_core_true",
                    "Materialize a pinned MiniF2F-style CORE fixture.",
                    {
                        "dataset_revision": "fixture-revision-1",
                        "sample_id": "core_true",
                        "source_url": "https://example.invalid/minif2f/core_true",
                        "row": {
                            "dataset_id": "MINIF2F",
                            "name": "core_true",
                            "split": "test",
                            "formal_statement": "theorem core_true : True := by trivial",
                            "informal_statement": "True holds.",
                            "header": "",
                        },
                        "environment": {
                            "lean_version": LEAN_VERSION,
                            "project_revision": "fixture-project-1",
                            "imports": [],
                            "project_files": [],
                        },
                    },
                ),
            ),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        try:
            validated = FormalDatasetMaterializeRequest.model_validate(request.input)
        except ValidationError as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_FORMAL_DATASET_ROW",
                    stage="request_validation",
                    message="The formal-dataset materialization request is invalid.",
                    hint="Provide a supported row with pinned dataset and environment data.",
                )
            ) from exc

        row_payload = validated.row.model_dump(mode="json")
        row_digest = _json_digest(row_payload)
        if (
            validated.expected_row_digest is not None
            and validated.expected_row_digest != row_digest
        ):
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="FORMAL_DATASET_ROW_DIGEST_MISMATCH",
                    stage="source_binding",
                    message="The supplied row does not match expected_row_digest.",
                    hint="Re-fetch the pinned row or update the expected digest explicitly.",
                )
            )

        header = _normalize_text(validated.row.header) if validated.row.header else ""
        formal_statement = _normalize_text(validated.row.formal_statement)
        normalized_source = f"{header}{formal_statement}"
        preprocessing = (
            FormalPreprocessingDecision(
                operation="NORMALIZE_NEWLINES",
                applied=True,
            ),
            FormalPreprocessingDecision(
                operation="TRIM_TRAILING_WHITESPACE",
                applied=True,
            ),
            FormalPreprocessingDecision(
                operation="ENSURE_FINAL_NEWLINE",
                applied=True,
            ),
        )
        environment_payload = validated.environment.model_dump(mode="json")
        artifact_payload = FormalDatasetArtifact(
            dataset_id=validated.row.dataset_id,
            dataset_revision=validated.dataset_revision,
            sample_id=validated.sample_id,
            source_url=validated.source_url,
            row_digest=row_digest,
            normalized_source_digest=_text_digest(normalized_source),
            normalized_source=normalized_source,
            formal_statement=formal_statement,
            informal_statement=(
                _normalize_text(validated.row.informal_statement)
                if validated.row.informal_statement is not None
                else None
            ),
            informal_proof=(
                _normalize_text(validated.row.informal_proof)
                if validated.row.informal_proof is not None
                else None
            ),
            header=header,
            environment=validated.environment,
            environment_digest=_json_digest(environment_payload),
            preprocessing=preprocessing,
            diagnostics=_diagnostics(validated),
        )
        artifact = self.artifacts.put(
            schema_uri=self.artifact_schema_uri,
            semantics_uri=self.semantics_uri,
            payload=artifact_payload.model_dump(mode="json"),
            summary=(
                f"pinned {validated.row.dataset_id} row {validated.sample_id} "
                "materialized without execution"
            ),
        )
        output = FormalDatasetMaterializeOutput(
            **artifact_payload.model_dump(mode="python"),
            artifact_uri=artifact.artifact_uri,
        )
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description="one pinned formal-dataset row",
                parameters={
                    "dataset_id": validated.row.dataset_id,
                    "dataset_revision": validated.dataset_revision,
                    "sample_id": validated.sample_id,
                    "row_digest": row_digest,
                },
                artifact_uri=artifact.artifact_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.COMPLETE,
                basis="the complete declared row was normalized and provenance-bound",
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=(
                    "deterministic materialization only; no theorem truth, proof "
                    "validity, or informal-formal correspondence was assessed"
                ),
            ),
            artifact_uris=(artifact.artifact_uri,),
        )


def install_formal_dataset_capability(
    store: ArtifactStore,
    schemas: SchemaRegistry,
    artifacts: ArtifactService,
) -> tuple[FormalDatasetMaterializeAdapter, FormalDatasetInstallation]:
    """Install the formal-dataset materialization contract."""

    semantics_uri = store.register_descriptor(
        kind="semantics",
        name="jacobian.formal-dataset-materialization",
        version="1",
        definition={
            "description": (
                "deterministic formal-dataset row normalization and environment "
                "provenance binding"
            ),
            "verification": "none; materialization never establishes theorem truth",
        },
    )
    artifact_schema_uri = schemas.register(
        name="jacobian.formal-dataset-row",
        version="1",
        schema=FormalDatasetArtifact.model_json_schema(),
    )
    return (
        FormalDatasetMaterializeAdapter(
            store,
            artifacts,
            semantics_uri=semantics_uri,
            artifact_schema_uri=artifact_schema_uri,
        ),
        FormalDatasetInstallation(
            semantics_uri=semantics_uri,
            artifact_schema_uri=artifact_schema_uri,
        ),
    )
