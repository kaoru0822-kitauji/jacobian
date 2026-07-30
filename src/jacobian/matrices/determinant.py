"""Independent verification capability for exact rational determinants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from jacobian.artifacts import ArtifactService
from jacobian.capabilities import CapabilityAdapter, CapabilityInvocationError
from jacobian.checker_artifacts import put_witness_envelope
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
    CapabilityRequest,
    CapabilityResult,
    CapabilityScope,
)
from jacobian.contracts.checkers import EvidenceKind
from jacobian.contracts.evidence import WitnessEnvelope
from jacobian.contracts.matrices import (
    ExactRationalMatrix,
    MatrixDeterminantArtifact,
    MatrixDeterminantVerificationOutput,
    MatrixDeterminantVerificationRequest,
)
from jacobian.contracts.results import Conclusion, ExecutionStatus, Verification
from jacobian.matrices.capabilities import MatrixInstallation
from jacobian.provider_runtime import known_provider_runtime
from jacobian.registry import CheckerRegistry
from jacobian.schema_registry import (
    SchemaRegistry,
    SchemaRegistryError,
    model_schema,
)
from jacobian.store import ArtifactStore, StoredArtifact, StoreError
from jacobian.verification import VerificationService


class MatrixDeterminantArtifactError(ValueError):
    """A stored determinant candidate is invalid or incompletely bound."""


@dataclass(frozen=True, slots=True)
class ResolvedMatrixDeterminant:
    matrix_artifact: StoredArtifact
    matrix: ExactRationalMatrix
    artifact: StoredArtifact
    candidate: MatrixDeterminantArtifact


@dataclass(frozen=True, slots=True)
class MatrixDeterminantCheckerInstallation:
    witness_schema_uri: str
    checker_id: str | None


def install_matrix_determinant_checker(
    store: ArtifactStore,
    schemas: SchemaRegistry,
    artifacts: ArtifactService,
    matrices: MatrixInstallation,
    verification: VerificationService,
    checkers: CheckerRegistry,
    *,
    authorize_checker: bool,
) -> tuple[CapabilityAdapter | None, MatrixDeterminantCheckerInstallation]:
    """Install the determinant witness schema and optionally authorize replay."""

    witness_schema_uri = schemas.register_model(
        name="jacobian.witness-envelope",
        version="1",
        model=WitnessEnvelope,
    )
    checker_id = (
        CheckerInstaller(checkers)
        .install(
            CheckerOperation(
                name="exact rational determinant recomputation checker",
                entrypoint=(
                    "jacobian_checkers.rational_determinants:check_rational_determinant"
                ),
                evidence_kind=EvidenceKind.WITNESS,
                format_id="matrix.rational_determinant",
                format_version="1",
                claim_schema_uris=(matrices.matrix_schema_uri,),
                semantics_uris=(matrices.semantics_uri,),
                candidate_schema_uris=(matrices.determinant_schema_uri,),
                reason=(
                    "bundled independent standard-library exact rational "
                    "determinant recomputation"
                ),
            ),
            authorize=authorize_checker,
        )
        .checker_id
    )
    installation = MatrixDeterminantCheckerInstallation(
        witness_schema_uri=witness_schema_uri,
        checker_id=checker_id,
    )
    adapter: CapabilityAdapter | None = None
    if checker_id is not None:
        adapter = MatrixDeterminantVerificationAdapter(
            store=store,
            schemas=schemas,
            artifacts=artifacts,
            matrices=matrices,
            verification=verification,
            installation=installation,
        )
    return adapter, installation


class MatrixDeterminantVerificationAdapter:
    """Independently recompute one stored exact rational determinant."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        schemas: SchemaRegistry,
        artifacts: ArtifactService,
        matrices: MatrixInstallation,
        verification: VerificationService,
        installation: MatrixDeterminantCheckerInstallation,
    ) -> None:
        checker_id = installation.checker_id
        if checker_id is None:
            raise ValueError("matrix determinant checker is not authorized")
        self.store = store
        self.schemas = schemas
        self.artifacts = artifacts
        self.matrices = matrices
        self.verification = verification
        self.installation = installation
        self._descriptor = CapabilityDescriptor(
            capability_id="matrix.determinant.verify",
            version="1",
            title="Verify an exact rational matrix determinant",
            description=(
                "Independently recompute and check the exact determinant of one "
                "bound stored square rational matrix."
            ),
            provider="jacobian.rational-matrix",
            provider_runtime=known_provider_runtime(
                "jacobian.rational-matrix",
                features=(
                    "exact-rational-recomputation",
                    "gaussian-elimination",
                    "clean-process-checker",
                ),
                checker_ids=(checker_id,),
            ),
            modes=(CapabilityMode.VERIFY,),
            input_schema=model_schema(MatrixDeterminantVerificationRequest),
            output_schema=model_schema(MatrixDeterminantVerificationOutput),
            tags=(
                "linear-algebra",
                "rational",
                "matrix",
                "determinant",
                "verification",
            ),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        validated = MatrixDeterminantVerificationRequest.model_validate(request.input)
        try:
            resolved = self._resolve(validated.determinant_uri)
            semantics = self.store.get(self.matrices.semantics_uri)
        except (MatrixDeterminantArtifactError, StoreError) as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_MATRIX_DETERMINANT",
                    stage="artifact_resolution",
                    message=str(exc),
                    path="determinant_uri",
                    schema_uri=self.matrices.determinant_schema_uri,
                    expected=(
                        "a valid exact determinant bound by payload and lineage "
                        "to one square rational matrix"
                    ),
                    hint=(
                        "Use matrix.determinant.compute or materialize a candidate "
                        "with the registered determinant schema."
                    ),
                )
            ) from exc

        checker_id = self.installation.checker_id
        assert checker_id is not None
        witness_artifact = put_witness_envelope(
            self.artifacts,
            witness_schema_uri=self.installation.witness_schema_uri,
            witness_format="matrix.rational_determinant",
            claim_artifact=resolved.matrix_artifact,
            semantics_artifact=semantics,
            candidate_artifact=resolved.artifact,
            payload={
                "matrix_uri": resolved.matrix_artifact.artifact_uri,
                "determinant_uri": resolved.artifact.artifact_uri,
            },
            summary="exact rational determinant verification witness",
        )
        checked = self.verification.verify_witness(
            claim_uri=resolved.matrix_artifact.artifact_uri,
            candidate_uri=resolved.artifact.artifact_uri,
            witness_uri=witness_artifact.artifact_uri,
            checker_id=checker_id,
            include_artifact_metadata=True,
        )
        verified = (
            checked.execution.status is ExecutionStatus.COMPLETED
            and checked.conclusion is Conclusion.TRUE
            and checked.assurance.verification is Verification.VERIFIED
            and checked.verification_record_uri is not None
        )
        status: Literal[
            "VERIFIED_DETERMINANT",
            "REJECTED",
            "TIMEOUT",
            "CANCELLED",
            "ERROR",
        ]
        if verified:
            status = "VERIFIED_DETERMINANT"
        elif checked.execution.status is ExecutionStatus.COMPLETED:
            status = "REJECTED"
        elif checked.execution.status is ExecutionStatus.TIMEOUT:
            status = "TIMEOUT"
        elif checked.execution.status is ExecutionStatus.CANCELLED:
            status = "CANCELLED"
        else:
            status = "ERROR"
        detail = checked.execution.detail
        if detail is None and checked.input.errors:
            detail = checked.input.errors[0]
        if detail is None:
            detail = (
                "the authorized checker accepted the exact determinant"
                if verified
                else "the determinant was not independently accepted"
            )
        output = MatrixDeterminantVerificationOutput(
            status=status,
            conclusion="TRUE" if verified else "UNKNOWN",
            matrix_uri=resolved.matrix_artifact.artifact_uri,
            determinant_uri=resolved.artifact.artifact_uri,
            witness_uri=witness_artifact.artifact_uri,
            checker_id=checker_id,
            verification_record_uri=(
                checked.verification_record_uri if verified else None
            ),
            detail=detail,
        )
        record_uri = checked.verification_record_uri if verified else None
        artifact_uris = [
            resolved.matrix_artifact.artifact_uri,
            resolved.artifact.artifact_uri,
            witness_artifact.artifact_uri,
        ]
        if record_uri is not None:
            artifact_uris.append(record_uri)
        assurance_level = (
            CapabilityAssuranceLevel.VERIFIED
            if verified
            else (
                CapabilityAssuranceLevel.COMPUTED
                if checked.execution.status is ExecutionStatus.COMPLETED
                else CapabilityAssuranceLevel.HEURISTIC
            )
        )
        dimension = len(resolved.matrix.entries)
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=checked.execution,
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description="the full exact square rational matrix",
                parameters={
                    "declared_scope": "FULL_MATRIX",
                    "row_count": dimension,
                    "column_count": dimension,
                    "arithmetic": "EXACT_RATIONAL",
                    "method": "GAUSSIAN_ELIMINATION",
                },
                artifact_uri=resolved.matrix_artifact.artifact_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.NOT_APPLICABLE,
                basis=(
                    "direct exact recomputation checks the full finite matrix; "
                    "no search or enumeration claim is made"
                ),
                assurance_level=(
                    CapabilityAssuranceLevel.COMPUTED
                    if checked.execution.status is ExecutionStatus.COMPLETED
                    else CapabilityAssuranceLevel.HEURISTIC
                ),
            ),
            assurance=CapabilityAssurance(
                level=assurance_level,
                basis=(
                    "accepted in a clean process by the operator-authorized "
                    "independent exact rational determinant checker"
                    if verified
                    else (
                        "checker recomputation completed without accepting the "
                        "candidate; no opposite conclusion follows"
                        if checked.execution.status is ExecutionStatus.COMPLETED
                        else "checker execution did not complete; no mathematical "
                        "conclusion follows"
                    )
                ),
                verification_record_uri=record_uri,
            ),
            artifact_uris=tuple(artifact_uris),
        )

    def _resolve(self, determinant_uri: str) -> ResolvedMatrixDeterminant:
        try:
            artifact = self.store.get(determinant_uri)
        except StoreError as exc:
            raise MatrixDeterminantArtifactError(
                "candidate is not an available determinant artifact"
            ) from exc
        if (
            artifact.manifest.schema_uri != self.matrices.determinant_schema_uri
            or artifact.manifest.semantics_uri != self.matrices.semantics_uri
        ):
            raise MatrixDeterminantArtifactError(
                "candidate is not an exact rational determinant artifact"
            )
        try:
            normalized = self.schemas.validate(
                self.matrices.determinant_schema_uri,
                artifact.payload,
            )
            candidate = MatrixDeterminantArtifact.model_validate(normalized)
        except (SchemaRegistryError, ValidationError, ValueError) as exc:
            raise MatrixDeterminantArtifactError(
                "candidate is not a valid determinant artifact"
            ) from exc
        try:
            matrix_artifact = self.store.get(candidate.matrix_uri)
        except StoreError as exc:
            raise MatrixDeterminantArtifactError(
                "candidate source matrix is unavailable"
            ) from exc
        if (
            matrix_artifact.manifest.schema_uri != self.matrices.matrix_schema_uri
            or matrix_artifact.manifest.semantics_uri != self.matrices.semantics_uri
        ):
            raise MatrixDeterminantArtifactError(
                "candidate source is not an exact rational matrix"
            )
        if artifact.manifest.parents != (matrix_artifact.artifact_uri,):
            raise MatrixDeterminantArtifactError(
                "candidate lineage does not exactly identify its source matrix"
            )
        try:
            normalized_matrix = self.schemas.validate(
                self.matrices.matrix_schema_uri,
                matrix_artifact.payload,
            )
            matrix = ExactRationalMatrix.model_validate(normalized_matrix)
        except (SchemaRegistryError, ValidationError, ValueError) as exc:
            raise MatrixDeterminantArtifactError(
                "candidate source is not a valid rational matrix"
            ) from exc
        if len(matrix.entries) != len(matrix.entries[0]):
            raise MatrixDeterminantArtifactError(
                "candidate source matrix is not square"
            )
        return ResolvedMatrixDeterminant(
            matrix_artifact=matrix_artifact,
            matrix=matrix,
            artifact=artifact,
            candidate=candidate,
        )
