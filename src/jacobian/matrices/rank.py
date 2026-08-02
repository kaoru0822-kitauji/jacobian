"""Independent verification of one stored exact rational matrix rank."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from jacobian.artifacts import ArtifactService
from jacobian.capability_service import CapabilityInvocationError
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
from jacobian.contracts.evidence import EvidenceBindings, WitnessEnvelope, WitnessRole
from jacobian.contracts.matrices import (
    ExactRationalMatrix,
    MatrixRankArtifact,
    MatrixRankVerificationOutput,
    MatrixRankVerificationRequest,
)
from jacobian.contracts.results import Conclusion, ExecutionStatus, Verification
from jacobian.matrices.capabilities import MatrixInstallation
from jacobian.provider_runtime import known_provider_runtime
from jacobian.registry import CheckerRegistry
from jacobian.schema_registry import SchemaRegistry, SchemaRegistryError, model_schema
from jacobian.storage.errors import StorageError
from jacobian.storage.repository import ArtifactRepository
from jacobian.verification import VerificationService


@dataclass(frozen=True, slots=True)
class MatrixRankCheckerInstallation:
    witness_schema_uri: str
    checker_id: str | None


def install_matrix_rank_checker(
    store: ArtifactRepository,
    schemas: SchemaRegistry,
    artifacts: ArtifactService,
    matrices: MatrixInstallation,
    verification: VerificationService,
    checkers: CheckerRegistry,
    *,
    authorize_checker: bool,
) -> tuple[MatrixRankVerificationAdapter | None, MatrixRankCheckerInstallation]:
    witness_schema_uri = schemas.register_model(
        name="jacobian.witness-envelope", version="1", model=WitnessEnvelope
    )
    checker_id = (
        CheckerInstaller(checkers)
        .install(
            CheckerOperation(
                name="exact rational rank recomputation checker",
                entrypoint=(
                    "jacobian_checkers.rational_determinants:check_rational_rank"
                ),
                evidence_kind=EvidenceKind.WITNESS,
                format_id="matrix.rational_rank",
                format_version="1",
                claim_schema_uris=(matrices.matrix_schema_uri,),
                semantics_uris=(matrices.semantics_uri,),
                candidate_schema_uris=(matrices.rank_schema_uri,),
                reason="bundled standard-library exact rational row reduction",
            ),
            authorize=authorize_checker,
        )
        .checker_id
    )
    installation = MatrixRankCheckerInstallation(witness_schema_uri, checker_id)
    if checker_id is None:
        return None, installation
    return (
        MatrixRankVerificationAdapter(
            store, schemas, artifacts, matrices, verification, installation
        ),
        installation,
    )


class MatrixRankVerificationAdapter:
    def __init__(
        self,
        store: ArtifactRepository,
        schemas: SchemaRegistry,
        artifacts: ArtifactService,
        matrices: MatrixInstallation,
        verification: VerificationService,
        installation: MatrixRankCheckerInstallation,
    ) -> None:
        self.store, self.schemas, self.artifacts = store, schemas, artifacts
        self.matrices, self.verification, self.installation = (
            matrices,
            verification,
            installation,
        )
        assert installation.checker_id is not None
        self._descriptor = CapabilityDescriptor(
            capability_id="matrix.rank.verify",
            version="1",
            title="Verify exact rational matrix rank",
            description="Independently recompute and verify one stored rank over QQ.",
            provider="jacobian.rational-matrix",
            provider_runtime=known_provider_runtime(
                "jacobian.rational-matrix",
                features=("rank", "exact-rational-recomputation"),
                checker_ids=(installation.checker_id,),
            ),
            modes=(CapabilityMode.VERIFY,),
            input_schema=model_schema(MatrixRankVerificationRequest),
            output_schema=model_schema(MatrixRankVerificationOutput),
            tags=("matrix", "rank", "verification"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        rank_uri = MatrixRankVerificationRequest.model_validate(request.input).rank_uri
        try:
            candidate_artifact = self.store.get(rank_uri)
            candidate = MatrixRankArtifact.model_validate(
                self.schemas.validate(
                    self.matrices.rank_schema_uri, candidate_artifact.payload
                )
            )
            matrix_artifact = self.store.get(candidate.matrix_uri)
            matrix = ExactRationalMatrix.model_validate(
                self.schemas.validate(
                    self.matrices.matrix_schema_uri, matrix_artifact.payload
                )
            )
            if (
                candidate_artifact.manifest.schema_uri != self.matrices.rank_schema_uri
                or candidate_artifact.manifest.semantics_uri
                != self.matrices.semantics_uri
                or matrix_artifact.manifest.schema_uri
                != self.matrices.matrix_schema_uri
                or candidate_artifact.manifest.parents
                != (matrix_artifact.artifact_uri,)
            ):
                raise ValueError("rank candidate is not exactly bound to its matrix")
        except (StorageError, SchemaRegistryError, ValidationError, ValueError) as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_MATRIX_RANK",
                    stage="artifact_resolution",
                    message=str(exc),
                    path="rank_uri",
                    hint="Use an artifact returned by matrix.rank.compute.",
                )
            ) from exc
        checker_id = self.installation.checker_id
        assert checker_id is not None
        semantics = self.store.get(self.matrices.semantics_uri)
        witness = WitnessEnvelope(
            witness_format="matrix.rational_rank",
            format_version="1",
            role=WitnessRole.SUPPORTS_CLAIM,
            bindings=EvidenceBindings(
                claim_digest=matrix_artifact.manifest.object_digest,
                semantics_digest=semantics.manifest.object_digest,
                candidate_digest=candidate_artifact.manifest.object_digest,
            ),
            payload={
                "matrix_uri": matrix_artifact.artifact_uri,
                "rank_uri": candidate_artifact.artifact_uri,
            },
        )
        evidence = self.artifacts.put(
            schema_uri=self.installation.witness_schema_uri,
            semantics_uri=self.matrices.semantics_uri,
            payload=witness.model_dump(mode="json"),
            parents=(matrix_artifact.artifact_uri, candidate_artifact.artifact_uri),
            summary="exact rational rank verification witness",
        )
        checked = self.verification.verify_witness(
            claim_uri=matrix_artifact.artifact_uri,
            candidate_uri=candidate_artifact.artifact_uri,
            witness_uri=evidence.artifact_uri,
            checker_id=checker_id,
            include_artifact_metadata=True,
        )
        verified = (
            checked.execution.status is ExecutionStatus.COMPLETED
            and checked.conclusion is Conclusion.TRUE
            and checked.assurance.verification is Verification.VERIFIED
            and checked.verification_record_uri is not None
        )
        status: Literal["VERIFIED_RANK", "REJECTED", "TIMEOUT", "CANCELLED", "ERROR"]
        if verified:
            status = "VERIFIED_RANK"
        elif checked.execution.status is ExecutionStatus.COMPLETED:
            status = "REJECTED"
        elif checked.execution.status is ExecutionStatus.TIMEOUT:
            status = "TIMEOUT"
        elif checked.execution.status is ExecutionStatus.CANCELLED:
            status = "CANCELLED"
        else:
            status = "ERROR"
        detail = checked.execution.detail or (
            checked.input.errors[0]
            if checked.input.errors
            else (
                "rank verified" if verified else "rank was not independently accepted"
            )
        )
        output = MatrixRankVerificationOutput(
            status=status,
            conclusion="TRUE" if verified else "UNKNOWN",
            matrix_uri=matrix_artifact.artifact_uri,
            rank_uri=candidate_artifact.artifact_uri,
            witness_uri=evidence.artifact_uri,
            checker_id=checker_id,
            verification_record_uri=checked.verification_record_uri
            if verified
            else None,
            detail=detail,
        )
        uris = [
            matrix_artifact.artifact_uri,
            candidate_artifact.artifact_uri,
            evidence.artifact_uri,
        ]
        if verified:
            assert checked.verification_record_uri is not None
            uris.append(checked.verification_record_uri)
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=checked.execution,
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description="the full rectangular exact rational matrix",
                parameters={
                    "row_count": len(matrix.entries),
                    "column_count": len(matrix.entries[0]),
                },
                artifact_uri=matrix_artifact.artifact_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.NOT_APPLICABLE,
                basis="direct exact row reduction makes no search claim",
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.VERIFIED
                if verified
                else CapabilityAssuranceLevel.COMPUTED,
                basis="independent exact rational row reduction"
                if verified
                else "checker did not accept the candidate",
                verification_record_uri=checked.verification_record_uri
                if verified
                else None,
            ),
            artifact_uris=tuple(uris),
        )
