"""Operator-controlled declarations for independent exact-operation replay."""

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
from jacobian.contracts.exact_domain_verification import (
    ExactDomainResultVerificationOutput,
    ExactDomainResultVerificationRequest,
)
from jacobian.contracts.matrix_operations import (
    IntegerMatrixRequest,
    RationalMatrixRequest,
    SquareRationalMatrixRequest,
)
from jacobian.contracts.polynomial_operations import (
    PolynomialDiscriminantRequest,
    PolynomialGcdRequest,
    PolynomialResultantRequest,
    PolynomialSquareFreeRequest,
)
from jacobian.contracts.results import (
    Conclusion,
    ContractModel,
    ExecutionStatus,
    Verification,
)
from jacobian.operation_installation import InstalledDomainBundle
from jacobian.provider_runtime import known_provider_runtime
from jacobian.registry import CheckerRegistry
from jacobian.schema_registry import SchemaRegistry, SchemaRegistryError, model_schema
from jacobian.store import ArtifactStore, StoredArtifact, StoreError
from jacobian.verification import VerificationService


@dataclass(frozen=True, slots=True)
class ExactDomainCheckerInstallation:
    """Authorized checker identities keyed by producer capability ID."""

    checker_ids: dict[str, str | None]
    witness_schema_uri: str | None = None


@dataclass(frozen=True, slots=True)
class _Declaration:
    capability_id: str
    request_model: type[ContractModel]
    function: str
    format_id: str


@dataclass(frozen=True, slots=True)
class _InstalledDeclaration:
    declaration: _Declaration
    input_schema_uri: str
    result_schema_uri: str
    semantics_uri: str
    checker_id: str


_POLYNOMIAL_DECLARATIONS = (
    _Declaration(
        "polynomial.compute.gcd",
        PolynomialGcdRequest,
        "check_polynomial_gcd",
        "polynomial.gcd.flint-replay",
    ),
    _Declaration(
        "polynomial.compute.resultant",
        PolynomialResultantRequest,
        "check_polynomial_resultant",
        "polynomial.resultant.flint-replay",
    ),
    _Declaration(
        "polynomial.compute.discriminant",
        PolynomialDiscriminantRequest,
        "check_polynomial_discriminant",
        "polynomial.discriminant.flint-replay",
    ),
    _Declaration(
        "polynomial.compute.square_free_decomposition",
        PolynomialSquareFreeRequest,
        "check_polynomial_square_free",
        "polynomial.square-free.flint-replay",
    ),
)

_MATRIX_DECLARATIONS = (
    _Declaration(
        "matrix.normal_form.rref.compute",
        RationalMatrixRequest,
        "check_matrix_rref",
        "matrix.rref.flint-replay",
    ),
    _Declaration(
        "matrix.nullspace.compute",
        RationalMatrixRequest,
        "check_matrix_nullspace",
        "matrix.nullspace.flint-replay",
    ),
    _Declaration(
        "matrix.characteristic_polynomial.compute",
        SquareRationalMatrixRequest,
        "check_matrix_characteristic_polynomial",
        "matrix.characteristic-polynomial.flint-replay",
    ),
    _Declaration(
        "matrix.normal_form.smith.compute",
        IntegerMatrixRequest,
        "check_matrix_smith_normal_form",
        "matrix.smith-normal-form.flint-replay",
    ),
)


def install_exact_domain_checkers(
    checkers: CheckerRegistry,
    *,
    polynomial: InstalledDomainBundle,
    matrix: InstalledDomainBundle,
    authorize: bool,
) -> ExactDomainCheckerInstallation:
    """Install independent FLINT replay against dynamically registered schemas."""

    installer = CheckerInstaller(checkers)
    checker_ids: dict[str, str | None] = {}
    for installed, declaration in (
        *((polynomial, item) for item in _POLYNOMIAL_DECLARATIONS),
        *((matrix, item) for item in _MATRIX_DECLARATIONS),
    ):
        operation = CheckerOperation(
            name=f"{declaration.capability_id} independent FLINT replay",
            entrypoint=(
                "jacobian_checkers.exact_domain_operations:"
                f"{declaration.function}"
            ),
            evidence_kind=EvidenceKind.WITNESS,
            format_id=declaration.format_id,
            format_version="1",
            claim_schema_uris=(
                installed.input_schema_uris[declaration.request_model],
            ),
            semantics_uris=(installed.semantics_uri,),
            candidate_schema_uris=(
                installed.result_schema_uris[declaration.capability_id],
            ),
            reason=(
                "operator-authorized Python-FLINT exact replay independent "
                "of the SymPy producer"
            ),
        )
        checker_ids[declaration.capability_id] = installer.install(
            operation,
            authorize=authorize,
        ).checker_id
    return ExactDomainCheckerInstallation(checker_ids=checker_ids)


def install_exact_domain_verification(
    store: ArtifactStore,
    schemas: SchemaRegistry,
    artifacts: ArtifactService,
    verification: VerificationService,
    checkers: CheckerRegistry,
    *,
    polynomial: InstalledDomainBundle,
    matrix: InstalledDomainBundle,
    authorize: bool,
) -> tuple[tuple[CapabilityAdapter, ...], ExactDomainCheckerInstallation]:
    """Authorize exact replay and expose domain-owned verification capabilities."""

    installed = install_exact_domain_checkers(
        checkers,
        polynomial=polynomial,
        matrix=matrix,
        authorize=authorize,
    )
    witness_schema_uri = schemas.register_model(
        name="jacobian.witness-envelope",
        version="1",
        model=WitnessEnvelope,
    )
    installation = ExactDomainCheckerInstallation(
        checker_ids=installed.checker_ids,
        witness_schema_uri=witness_schema_uri,
    )
    if not authorize:
        return (), installation
    polynomial_declarations = tuple(
        _installed_declaration(polynomial, declaration, installation)
        for declaration in _POLYNOMIAL_DECLARATIONS
    )
    matrix_declarations = tuple(
        _installed_declaration(matrix, declaration, installation)
        for declaration in _MATRIX_DECLARATIONS
    )
    return (
        (
            ExactDomainResultVerificationAdapter(
                capability_id="polynomial.result.verify",
                title="Verify an exact polynomial result",
                description=(
                    "Independently replay one supported stored polynomial result "
                    "against its exact input lineage."
                ),
                tags=("verification", "exact", "polynomial"),
                store=store,
                schemas=schemas,
                artifacts=artifacts,
                verification=verification,
                declarations=polynomial_declarations,
                witness_schema_uri=witness_schema_uri,
            ),
            ExactDomainResultVerificationAdapter(
                capability_id="matrix.result.verify",
                title="Verify an exact matrix result",
                description=(
                    "Independently replay one supported stored matrix result "
                    "against its exact input lineage."
                ),
                tags=("verification", "exact", "matrix"),
                store=store,
                schemas=schemas,
                artifacts=artifacts,
                verification=verification,
                declarations=matrix_declarations,
                witness_schema_uri=witness_schema_uri,
            ),
        ),
        installation,
    )


def _installed_declaration(
    bundle: InstalledDomainBundle,
    declaration: _Declaration,
    installation: ExactDomainCheckerInstallation,
) -> _InstalledDeclaration:
    checker_id = installation.checker_ids[declaration.capability_id]
    if checker_id is None:
        raise ValueError("exact-domain checker is not authorized")
    return _InstalledDeclaration(
        declaration=declaration,
        input_schema_uri=bundle.input_schema_uris[declaration.request_model],
        result_schema_uri=bundle.result_schema_uris[declaration.capability_id],
        semantics_uri=bundle.semantics_uri,
        checker_id=checker_id,
    )


class ExactDomainArtifactError(ValueError):
    """A result is not one of the exactly bound supported producer artifacts."""


class ExactDomainResultVerificationAdapter:
    """Verify one stored exact producer result using independent FLINT replay."""

    def __init__(
        self,
        *,
        capability_id: str,
        title: str,
        description: str,
        tags: tuple[str, ...],
        store: ArtifactStore,
        schemas: SchemaRegistry,
        artifacts: ArtifactService,
        verification: VerificationService,
        declarations: tuple[_InstalledDeclaration, ...],
        witness_schema_uri: str,
    ) -> None:
        self.store = store
        self.schemas = schemas
        self.artifacts = artifacts
        self.verification = verification
        self.declarations_by_schema = {
            declaration.result_schema_uri: declaration
            for declaration in declarations
        }
        checker_ids = tuple(
            declaration.checker_id for declaration in declarations
        )
        self.witness_schema_uri = witness_schema_uri
        self._descriptor = CapabilityDescriptor(
            capability_id=capability_id,
            version="1",
            title=title,
            description=description,
            provider="jacobian.exact-domain-checkers",
            provider_runtime=known_provider_runtime(
                "jacobian.exact-domain-checkers",
                features=("clean-process-replay", "python-flint"),
                checker_ids=checker_ids,
            ),
            modes=(CapabilityMode.VERIFY,),
            input_schema=model_schema(ExactDomainResultVerificationRequest),
            output_schema=model_schema(ExactDomainResultVerificationOutput),
            tags=tags,
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        validated = ExactDomainResultVerificationRequest.model_validate(request.input)
        try:
            declaration, input_artifact, result_artifact, semantics_artifact = (
                self._resolve(validated.result_uri)
            )
        except (ExactDomainArtifactError, StoreError) as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_EXACT_DOMAIN_RESULT",
                    stage="artifact_resolution",
                    message=str(exc),
                    path="result_uri",
                    hint=(
                        "Pass a result_uri returned by one supported exact "
                        "polynomial or matrix producer."
                    ),
                )
            ) from exc

        witness = put_witness_envelope(
            self.artifacts,
            witness_schema_uri=self.witness_schema_uri,
            witness_format=declaration.declaration.format_id,
            claim_artifact=input_artifact,
            semantics_artifact=semantics_artifact,
            candidate_artifact=result_artifact,
            payload={
                "operation_id": declaration.declaration.capability_id,
                "input_uri": input_artifact.artifact_uri,
                "result_uri": result_artifact.artifact_uri,
            },
            summary=(
                f"{declaration.declaration.capability_id} independent replay witness"
            ),
        )
        checked = self.verification.verify_witness(
            claim_uri=input_artifact.artifact_uri,
            candidate_uri=result_artifact.artifact_uri,
            witness_uri=witness.artifact_uri,
            checker_id=declaration.checker_id,
            include_artifact_metadata=True,
        )
        verified = (
            checked.execution.status is ExecutionStatus.COMPLETED
            and checked.conclusion is Conclusion.TRUE
            and checked.assurance.verification is Verification.VERIFIED
            and checked.verification_record_uri is not None
        )
        status: Literal["VERIFIED", "REJECTED", "TIMEOUT", "CANCELLED", "ERROR"]
        if verified:
            status = "VERIFIED"
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
                "the authorized independent checker accepted the exact result"
                if verified
                else "the exact result was not independently accepted"
            )
        output = ExactDomainResultVerificationOutput(
            status=status,
            conclusion="TRUE" if verified else "UNKNOWN",
            operation_id=declaration.declaration.capability_id,
            input_uri=input_artifact.artifact_uri,
            result_uri=result_artifact.artifact_uri,
            witness_uri=witness.artifact_uri,
            checker_id=declaration.checker_id,
            verification_record_uri=(
                checked.verification_record_uri if verified else None
            ),
            detail=detail,
        )
        record_uri = checked.verification_record_uri if verified else None
        artifact_uris = [
            input_artifact.artifact_uri,
            result_artifact.artifact_uri,
            witness.artifact_uri,
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
                description="the complete stored exact operation input and result",
                parameters={
                    "operation_id": declaration.declaration.capability_id,
                    "input_uri": input_artifact.artifact_uri,
                    "result_uri": result_artifact.artifact_uri,
                },
                artifact_uri=input_artifact.artifact_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.NOT_APPLICABLE,
                basis="direct exact replay makes no search-completeness claim",
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
                    "independent Python-FLINT checker"
                    if verified
                    else (
                        "checker replay completed without accepting the candidate; "
                        "no opposite conclusion follows"
                        if checked.execution.status is ExecutionStatus.COMPLETED
                        else "checker replay did not complete; no conclusion follows"
                    )
                ),
                verification_record_uri=record_uri,
            ),
            artifact_uris=tuple(artifact_uris),
        )

    def _resolve(
        self, result_uri: str
    ) -> tuple[
        _InstalledDeclaration,
        StoredArtifact,
        StoredArtifact,
        StoredArtifact,
    ]:
        result = self.store.get(result_uri)
        declaration = self.declarations_by_schema.get(result.manifest.schema_uri)
        if declaration is None:
            raise ExactDomainArtifactError(
                "artifact schema is not a supported exact-domain result"
            )
        if result.manifest.semantics_uri != declaration.semantics_uri:
            raise ExactDomainArtifactError(
                "result semantics do not match the declared producer"
            )
        if len(result.manifest.parents) != 1:
            raise ExactDomainArtifactError(
                "result lineage must identify exactly one producer input"
            )
        input_artifact = self.store.get(result.manifest.parents[0])
        if (
            input_artifact.manifest.schema_uri != declaration.input_schema_uri
            or input_artifact.manifest.semantics_uri != declaration.semantics_uri
        ):
            raise ExactDomainArtifactError(
                "result parent is not the exact declared producer input"
            )
        try:
            self.schemas.validate(declaration.result_schema_uri, result.payload)
            self.schemas.validate(
                declaration.input_schema_uri,
                input_artifact.payload,
            )
        except (SchemaRegistryError, ValidationError, ValueError) as exc:
            raise ExactDomainArtifactError(
                "stored operation artifacts do not satisfy their contracts"
            ) from exc
        semantics = self.store.get(declaration.semantics_uri)
        return declaration, input_artifact, result, semantics


__all__ = [
    "ExactDomainArtifactError",
    "ExactDomainCheckerInstallation",
    "ExactDomainResultVerificationAdapter",
    "install_exact_domain_checkers",
    "install_exact_domain_verification",
]
