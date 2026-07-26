"""Model-facing verification for exact SAT assignment artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from jacobian.artifacts import ArtifactService
from jacobian.capabilities import CapabilityAdapter, CapabilityInvocationError
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
from jacobian.contracts.evidence import (
    EvidenceBindings,
    WitnessEnvelope,
    WitnessRole,
)
from jacobian.contracts.results import (
    Conclusion,
    ExecutionStatus,
    Verification,
)
from jacobian.contracts.sat import (
    SatAssignmentVerificationOutput,
    SatAssignmentVerificationRequest,
)
from jacobian.provider_runtime import known_provider_runtime
from jacobian.registry import CheckerRegistry
from jacobian.sat import SatArtifactError, SatArtifactService
from jacobian.schema_registry import SchemaRegistry, model_schema
from jacobian.store import ArtifactStore, StoreError
from jacobian.verification import VerificationService


@dataclass(frozen=True, slots=True)
class SatAssignmentCheckerInstallation:
    witness_schema_uri: str
    checker_id: str | None


def install_sat_assignment_checker(
    store: ArtifactStore,
    schemas: SchemaRegistry,
    artifacts: ArtifactService,
    sat: SatArtifactService,
    verification: VerificationService,
    checkers: CheckerRegistry,
    *,
    authorize_checker: bool,
) -> tuple[CapabilityAdapter | None, SatAssignmentCheckerInstallation]:
    """Install the assignment evidence schema and optionally authorize replay."""

    witness_schema_uri = schemas.register_model(
        name="jacobian.witness-envelope",
        version="1",
        model=WitnessEnvelope,
    )
    checker_id = None
    if authorize_checker:
        checker_id = checkers.authorize(
            name="exact total SAT assignment replay checker",
            entrypoint="jacobian_checkers.sat:check_assignment",
            evidence_kind="WITNESS",
            format_id="sat.assignment",
            format_version="1",
            claim_schema_uris=(sat.installation.cnf_schema_uri,),
            semantics_uris=(sat.installation.semantics_uri,),
            candidate_schema_uris=(sat.installation.assignment_schema_uri,),
            reason="bundled independent SAT assignment checker",
        ).checker_id
    installation = SatAssignmentCheckerInstallation(
        witness_schema_uri=witness_schema_uri,
        checker_id=checker_id,
    )
    adapter: CapabilityAdapter | None = None
    if checker_id is not None:
        adapter = SatAssignmentVerificationAdapter(
            store=store,
            artifacts=artifacts,
            sat=sat,
            verification=verification,
            installation=installation,
        )
    return adapter, installation


class SatAssignmentVerificationAdapter:
    """Verify one assignment; never infer UNSAT from assignment rejection."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        artifacts: ArtifactService,
        sat: SatArtifactService,
        verification: VerificationService,
        installation: SatAssignmentCheckerInstallation,
    ) -> None:
        checker_id = installation.checker_id
        if checker_id is None:
            raise ValueError("SAT assignment checker is not authorized")
        self.store = store
        self.artifacts = artifacts
        self.sat = sat
        self.verification = verification
        self.installation = installation
        self._descriptor = CapabilityDescriptor(
            capability_id="sat.model.verify",
            version="1",
            title="Verify a SAT assignment",
            description=(
                "Independently replay one total assignment against every clause "
                "of its exact bound canonical CNF."
            ),
            provider="jacobian.sat",
            provider_runtime=known_provider_runtime(
                "jacobian.sat",
                features=("total-assignment-replay", "canonical-cnf"),
                checker_ids=(checker_id,),
            ),
            modes=(CapabilityMode.VERIFY,),
            input_schema=model_schema(SatAssignmentVerificationRequest),
            output_schema=model_schema(SatAssignmentVerificationOutput),
            tags=("sat", "cnf", "assignment", "verification"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        validated = SatAssignmentVerificationRequest.model_validate(request.input)
        try:
            resolved = self.sat.resolve_assignment(validated.assignment_uri)
            semantics = self.store.get(self.sat.installation.semantics_uri)
        except (SatArtifactError, StoreError) as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_SAT_ASSIGNMENT",
                    stage="artifact_resolution",
                    message=str(exc),
                    path="assignment_uri",
                    schema_uri=self.sat.installation.assignment_schema_uri,
                    expected=(
                        "a valid SAT assignment artifact bound by payload and lineage "
                        "to one canonical CNF"
                    ),
                    hint=(
                        "Create the assignment with SatArtifactService.put_assignment "
                        "against the intended canonical CNF."
                    ),
                )
            ) from exc

        checker_id = self.installation.checker_id
        assert checker_id is not None
        bindings = EvidenceBindings(
            claim_digest=resolved.cnf_artifact.manifest.object_digest,
            semantics_digest=semantics.manifest.object_digest,
            candidate_digest=resolved.artifact.manifest.object_digest,
        )
        witness = WitnessEnvelope(
            witness_format="sat.assignment",
            format_version="1",
            role=WitnessRole.SUPPORTS_CLAIM,
            bindings=bindings,
            payload={
                "cnf_uri": resolved.cnf_artifact.artifact_uri,
                "assignment_uri": resolved.artifact.artifact_uri,
            },
        )
        witness_artifact = self.artifacts.put(
            schema_uri=self.installation.witness_schema_uri,
            semantics_uri=self.sat.installation.semantics_uri,
            payload=witness.model_dump(mode="json"),
            parents=(
                resolved.cnf_artifact.artifact_uri,
                resolved.artifact.artifact_uri,
            ),
            summary="SAT assignment verification witness",
        )
        checked = self.verification.verify_witness(
            claim_uri=resolved.cnf_artifact.artifact_uri,
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
            "VERIFIED_SATISFYING",
            "REJECTED",
            "TIMEOUT",
            "CANCELLED",
            "ERROR",
        ]
        if verified:
            status = "VERIFIED_SATISFYING"
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
                "the authorized checker accepted the total assignment"
                if verified
                else "the assignment was not independently accepted"
            )
        output = SatAssignmentVerificationOutput(
            status=status,
            conclusion="TRUE" if verified else "UNKNOWN",
            cnf_uri=resolved.cnf_artifact.artifact_uri,
            assignment_uri=resolved.artifact.artifact_uri,
            witness_uri=witness_artifact.artifact_uri,
            checker_id=checker_id,
            verification_record_uri=(
                checked.verification_record_uri if verified else None
            ),
            detail=detail,
        )
        record_uri = checked.verification_record_uri if verified else None
        artifact_uris = [
            resolved.cnf_artifact.artifact_uri,
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
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=checked.execution,
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description="the full exact canonical CNF bound by the assignment",
                parameters={
                    "declared_scope": "FULL_CNF",
                    "variable_count": resolved.assignment.cnf.variable_count,
                    "clause_count": resolved.assignment.cnf.clause_count,
                },
                artifact_uri=resolved.cnf_artifact.artifact_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.NOT_APPLICABLE,
                basis=(
                    "direct assignment replay checks one witness and makes no "
                    "enumeration or UNSAT completeness claim"
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
                    "accepted by the operator-authorized independent SAT "
                    "assignment checker"
                    if verified
                    else (
                        "checker replay completed without accepting the assignment; "
                        "no opposite conclusion follows"
                        if checked.execution.status is ExecutionStatus.COMPLETED
                        else "checker execution did not complete; no mathematical "
                        "conclusion follows"
                    )
                ),
                verification_record_uri=record_uri,
            ),
            artifact_uris=tuple(artifact_uris),
        )
