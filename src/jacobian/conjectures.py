"""Hypothesis-producing workflows built on the durable search boundary."""

from __future__ import annotations

import hashlib
import time
from typing import Any

from pydantic import ValidationError

from jacobian.canonical import canonicalize_json
from jacobian.claims import ClaimValidationService
from jacobian.contracts.checkers import EvidenceKind
from jacobian.contracts.conjectures import (
    ConjectureOperation,
    ConjectureWorkflowRequest,
    ConjectureWorkflowResult,
    HypothesisRecord,
    HypothesisTransformationRecord,
    NoveltyAssessment,
    PluginHypothesisResponse,
)
from jacobian.contracts.evidence import WitnessEnvelope, WitnessRole
from jacobian.contracts.plugins import CapabilityName, PluginManifest
from jacobian.contracts.results import (
    Conclusion,
    Execution,
    ExecutionStatus,
    InputStatus,
    InputValidation,
    Verification,
)
from jacobian.contracts.search import SearchRunRequest
from jacobian.contracts.verification import VerificationRecord
from jacobian.plugin_execution import PluginExecutor
from jacobian.plugins.registry import (
    PluginRegistry,
    PluginRegistryError,
    ResolvedCapability,
)
from jacobian.schema_registry import SchemaRegistry, SchemaRegistryError
from jacobian.search import SearchError, SearchService
from jacobian.store import ArtifactStore, StoredArtifact, StoreError
from jacobian.verification import VerificationService


class ConjectureError(RuntimeError):
    """A conjecture workflow request or plugin response is invalid."""


class ConjectureService:
    """Create unverified hypotheses and optionally route them through M3."""

    def __init__(
        self,
        store: ArtifactStore,
        schemas: SchemaRegistry,
        plugins: PluginRegistry,
        claims: ClaimValidationService,
        executor: PluginExecutor,
        search: SearchService,
        verification: VerificationService,
    ) -> None:
        self.store = store
        self.schemas = schemas
        self.plugins = plugins
        self.claims = claims
        self.executor = executor
        self.search = search
        self.verification = verification
        self.semantics_uri = store.register_descriptor(
            kind="semantics",
            name="jacobian.hypothesis-transformation",
            version="1",
            definition={
                "description": ("unverified conjecture edits and exact source lineage")
            },
        )
        self.transformation_schema_uri = schemas.register(
            name="jacobian.hypothesis-transformation",
            version="1",
            schema=HypothesisTransformationRecord.model_json_schema(),
        )

    def run(
        self,
        request: ConjectureWorkflowRequest | dict[str, Any],
    ) -> ConjectureWorkflowResult:
        """Run one bounded hypothesis transformation and optional falsification."""

        started = time.monotonic()
        try:
            selected = ConjectureWorkflowRequest.model_validate(request)
        except ValidationError as exc:
            return self._rejected(
                operation=None,
                plugin_id=None,
                request_digest=_digest_untrusted_request(request),
                detail=str(exc),
                started=started,
            )
        request_digest = _digest(selected.model_dump(mode="json"))
        try:
            manifest, capability, source, evidence = self._prepare(selected)
        except (
            ConjectureError,
            PluginRegistryError,
            SchemaRegistryError,
            StoreError,
            ValidationError,
            ValueError,
        ) as exc:
            return self._rejected(
                operation=selected.operation,
                plugin_id=selected.plugin_id,
                request_digest=request_digest,
                detail=str(exc),
                started=started,
            )

        plugin_request = {
            "request_version": "1",
            "operation": selected.operation.value,
            "source": (_artifact_view(source) if source is not None else None),
            "evidence": [_artifact_view(artifact) for artifact in evidence],
            "constraints": selected.constraints,
            "reference_claim_uris": list(selected.reference_claim_uris),
            "seed": selected.seed,
            "max_hypotheses": selected.max_hypotheses,
            "bindings": {
                "plugin_id": selected.plugin_id,
                "registry_snapshot_uri": capability.registry_snapshot_uri,
                "implementation_digest": capability.implementation_digest,
                "request_digest": request_digest,
            },
        }
        execution = self.executor.run(
            entrypoint=capability.descriptor.entrypoint,
            implementation_digest=capability.implementation_digest,
            request=plugin_request,
            timeout_seconds=selected.wall_seconds,
        )
        if execution.status is not ExecutionStatus.COMPLETED:
            return ConjectureWorkflowResult(
                operation=selected.operation,
                execution=Execution(
                    status=execution.status,
                    runtime_ms=execution.runtime_ms,
                    detail=execution.detail,
                ),
                input=InputValidation(status=InputStatus.ACCEPTED),
                request_digest=request_digest,
                plugin_id=selected.plugin_id,
                registry_snapshot_uri=capability.registry_snapshot_uri,
                implementation_digest=capability.implementation_digest,
                detail=execution.detail or "hypothesis transformer failed",
            )
        try:
            response = PluginHypothesisResponse.model_validate(execution.output)
            if len(response.proposals) > selected.max_hypotheses:
                raise ConjectureError(
                    "hypothesis transformer returned more proposals than authorized"
                )
            hypotheses = self._commit_hypotheses(
                selected=selected,
                request_digest=request_digest,
                manifest=manifest,
                capability=capability,
                source=source,
                evidence=evidence,
                response=response,
            )
        except (
            ConjectureError,
            PluginRegistryError,
            SchemaRegistryError,
            SearchError,
            StoreError,
            ValidationError,
            ValueError,
        ) as exc:
            return ConjectureWorkflowResult(
                operation=selected.operation,
                execution=Execution(
                    status=ExecutionStatus.ERROR,
                    runtime_ms=_elapsed_ms(started),
                    detail=str(exc),
                ),
                input=InputValidation(status=InputStatus.ACCEPTED),
                request_digest=request_digest,
                plugin_id=selected.plugin_id,
                registry_snapshot_uri=capability.registry_snapshot_uri,
                implementation_digest=capability.implementation_digest,
                detail=str(exc),
            )
        return ConjectureWorkflowResult(
            operation=selected.operation,
            execution=Execution(
                status=ExecutionStatus.COMPLETED,
                runtime_ms=_elapsed_ms(started),
            ),
            input=InputValidation(status=InputStatus.ACCEPTED),
            request_digest=request_digest,
            plugin_id=selected.plugin_id,
            registry_snapshot_uri=capability.registry_snapshot_uri,
            implementation_digest=capability.implementation_digest,
            hypotheses=hypotheses,
            verification=Verification.UNVERIFIED,
            detail=response.detail,
        )

    def _prepare(
        self,
        request: ConjectureWorkflowRequest,
    ) -> tuple[
        PluginManifest,
        ResolvedCapability,
        StoredArtifact | None,
        tuple[StoredArtifact, ...],
    ]:
        manifest = self.plugins.get(request.plugin_id)
        capability = self.plugins.resolve(
            request.plugin_id,
            CapabilityName.HYPOTHESIS_TRANSFORMER,
        )
        source = (
            self.store.get(request.source_uri)
            if request.source_uri is not None
            else None
        )
        if source is not None and (
            source.manifest.semantics_uri != manifest.semantics_uri
        ):
            raise ConjectureError("source semantics do not match the hypothesis plugin")
        evidence: list[StoredArtifact] = []
        if request.verification_record_uri is not None:
            record_artifact = self.store.get(request.verification_record_uri)
            self._validate_verified_source(
                request=request,
                source=source,
                record_artifact=record_artifact,
            )
            evidence.append(record_artifact)
            record = VerificationRecord.model_validate(record_artifact.payload)
            evidence.append(self.store.get(record.evidence_uri))
        for claim_uri in request.reference_claim_uris:
            reference = self.store.get(claim_uri)
            if (
                reference.manifest.schema_uri != manifest.claim_schema_uri
                or reference.manifest.semantics_uri != manifest.semantics_uri
            ):
                raise ConjectureError(
                    "reference claim does not match the plugin claim contract"
                )
            self.schemas.validate(reference.manifest.schema_uri, reference.payload)
        known_evidence_uris = {artifact.artifact_uri for artifact in evidence}
        for evidence_uri in request.evidence_uris:
            if evidence_uri not in known_evidence_uris:
                evidence.append(self.store.get(evidence_uri))
                known_evidence_uris.add(evidence_uri)
        if request.operation is ConjectureOperation.REPAIR:
            if source is None:
                raise ConjectureError("repair source is missing")
            if source.manifest.schema_uri != manifest.claim_schema_uri:
                raise ConjectureError(
                    "repair source does not use the plugin claim schema"
                )
            validation = self.claims.validate(
                claim_uri=source.artifact_uri,
                plugin_id=request.plugin_id,
            )
            if not validation.valid:
                raise ConjectureError("; ".join(validation.input.errors))
        if request.falsification is not None:
            search_capabilities = [
                self.plugins.resolve(request.plugin_id, CapabilityName.PROPOSER),
                self.plugins.resolve(request.plugin_id, CapabilityName.REFINER),
                self.plugins.resolve(request.plugin_id, CapabilityName.EVALUATOR),
            ]
            if request.falsification.witness_role is not None:
                search_capabilities.append(
                    self.plugins.resolve(
                        request.plugin_id,
                        CapabilityName.WITNESS_ORACLE,
                    )
                )
            if {
                resolved.registry_snapshot_uri
                for resolved in (capability, *search_capabilities)
            } != {capability.registry_snapshot_uri}:
                raise ConjectureError(
                    "hypothesis and falsification capabilities use different "
                    "registry snapshots"
                )
        return manifest, capability, source, tuple(evidence)

    def _validate_verified_source(
        self,
        *,
        request: ConjectureWorkflowRequest,
        source: StoredArtifact | None,
        record_artifact: StoredArtifact,
    ) -> None:
        if source is None:
            raise ConjectureError("verified source record requires a source")
        if record_artifact.manifest.schema_uri != self.verification.record_schema_uri:
            raise ConjectureError(
                "source verification record was not produced by the verifier"
            )
        record = VerificationRecord.model_validate(record_artifact.payload)
        if source.artifact_uri not in record_artifact.manifest.parents:
            raise ConjectureError(
                "source verification record does not bind the source artifact"
            )
        source_digest = source.manifest.object_digest
        semantics_digest = self.store.get(
            source.manifest.semantics_uri
        ).manifest.object_digest
        if record.bindings.semantics_digest != semantics_digest:
            raise ConjectureError(
                "source verification record does not bind the source semantics"
            )
        if request.operation is ConjectureOperation.REPAIR:
            witness = WitnessEnvelope.model_validate(
                self.store.get(record.evidence_uri).payload
            )
            if (
                record.evidence_kind is not EvidenceKind.WITNESS
                or record.conclusion is not Conclusion.FALSE
                or record.bindings.claim_digest != source_digest
                or witness.role is not WitnessRole.REFUTES_CLAIM
            ):
                raise ConjectureError(
                    "repair requires a verified counterexample for the source claim"
                )
            return
        manifest = self.plugins.get(request.plugin_id)
        if (
            source.manifest.schema_uri != manifest.candidate_schema_uri
            or record.evidence_kind
            not in {EvidenceKind.WITNESS, EvidenceKind.CERTIFICATE}
            or record.conclusion is not Conclusion.TRUE
            or record.bindings.candidate_digest != source_digest
        ):
            raise ConjectureError(
                "parameter generalization requires a verified construction candidate"
            )
        if record.evidence_kind is EvidenceKind.WITNESS:
            witness = WitnessEnvelope.model_validate(
                self.store.get(record.evidence_uri).payload
            )
            if witness.role is not WitnessRole.RESCUES_CANDIDATE:
                raise ConjectureError(
                    "parameter generalization witness must rescue the construction"
                )

    def _commit_hypotheses(
        self,
        *,
        selected: ConjectureWorkflowRequest,
        request_digest: str,
        manifest: PluginManifest,
        capability: ResolvedCapability,
        source: StoredArtifact | None,
        evidence: tuple[StoredArtifact, ...],
        response: PluginHypothesisResponse,
    ) -> tuple[HypothesisRecord, ...]:
        reference_digests = {
            self.store.get(uri).manifest.object_digest
            for uri in selected.reference_claim_uris
        }
        authorized_sample_uris = {artifact.artifact_uri for artifact in evidence}
        seen_digests: set[str] = set()
        records: list[HypothesisRecord] = []
        for proposal in response.proposals:
            for sample_uri in (
                proposal.parameter_region.sample_uris
                if proposal.parameter_region is not None
                else ()
            ):
                if sample_uri not in authorized_sample_uris:
                    raise ConjectureError(
                        "parameter-region samples must be supplied as workflow evidence"
                    )
            normalized_claim = self.schemas.validate(
                manifest.claim_schema_uri,
                proposal.claim,
            )
            parents = (
                *((source.artifact_uri,) if source is not None else ()),
                *(artifact.artifact_uri for artifact in evidence),
                selected.plugin_id,
                capability.registry_snapshot_uri,
            )
            claim = self.store.put(
                schema_uri=manifest.claim_schema_uri,
                semantics_uri=manifest.semantics_uri,
                payload=normalized_claim,
                parents=parents,
                summary="unverified generated hypothesis",
            )
            if (
                claim.object_digest in seen_digests
                or claim.object_digest in reference_digests
            ):
                continue
            validation = self.claims.validate(
                claim_uri=claim.artifact_uri,
                plugin_id=selected.plugin_id,
            )
            if not validation.valid:
                raise ConjectureError(
                    "generated claim is invalid: " + "; ".join(validation.input.errors)
                )
            seen_digests.add(claim.object_digest)
            transformation = HypothesisTransformationRecord(
                operation=selected.operation,
                source_uri=source.artifact_uri if source is not None else None,
                target_claim_uri=claim.artifact_uri,
                edit=proposal.edit,
                metrics=proposal.metrics,
                parameter_region=proposal.parameter_region,
                evidence_uris=tuple(artifact.artifact_uri for artifact in evidence),
                plugin_id=selected.plugin_id,
                registry_snapshot_uri=capability.registry_snapshot_uri,
                implementation_digest=capability.implementation_digest,
                request_digest=request_digest,
            )
            transformation_parents = (
                claim.artifact_uri,
                *parents,
                *(
                    proposal.parameter_region.sample_uris
                    if proposal.parameter_region is not None
                    else ()
                ),
            )
            stored_transformation = self.store.put(
                schema_uri=self.transformation_schema_uri,
                semantics_uri=self.semantics_uri,
                payload=self.schemas.validate(
                    self.transformation_schema_uri,
                    transformation.model_dump(mode="json"),
                ),
                parents=_deduplicate_uris(transformation_parents),
                summary="hypothesis transformation lineage",
            )
            record = HypothesisRecord(
                claim_uri=claim.artifact_uri,
                transformation_uri=stored_transformation.artifact_uri,
                novelty=NoveltyAssessment.UNKNOWN,
                parameter_region=proposal.parameter_region,
                detail=proposal.detail,
            )
            if selected.falsification is not None:
                record = self._falsify(
                    selected=selected,
                    request_digest=request_digest,
                    record=record,
                )
            records.append(record)
        return tuple(records)

    def _falsify(
        self,
        *,
        selected: ConjectureWorkflowRequest,
        request_digest: str,
        record: HypothesisRecord,
    ) -> HypothesisRecord:
        plan = selected.falsification
        if plan is None:
            raise ConjectureError("falsification plan is missing")
        idempotency_digest = hashlib.sha256(
            canonicalize_json(
                {
                    "workflow_request_digest": request_digest,
                    "claim_uri": record.claim_uri,
                    "operation": selected.operation.value,
                }
            )
        ).hexdigest()
        handle = self.search.start(
            SearchRunRequest(
                idempotency_key=f"m4:{idempotency_digest}",
                claim_uri=record.claim_uri,
                plugin_id=selected.plugin_id,
                initial_state=plan.initial_state,
                seed=selected.seed,
                witness_role=plan.witness_role,
                counterexample_checker_id=plan.counterexample_checker_id,
                budget=plan.budget,
            )
        )
        try:
            snapshot = self.search.wait(
                handle.experiment_uri,
                timeout_seconds=plan.budget.wall_seconds + 5,
            )
        except TimeoutError:
            self.search.cancel(handle.experiment_uri)
            try:
                snapshot = self.search.wait(
                    handle.experiment_uri,
                    timeout_seconds=5,
                )
            except TimeoutError:
                snapshot = self.search.inspect(handle.experiment_uri)
        return HypothesisRecord.model_validate(
            {
                **record.model_dump(mode="json"),
                "search_experiment_uri": snapshot.experiment_uri,
                "verified_counterexamples": (
                    snapshot.accounting.verified_counterexamples
                ),
                "detail": (
                    f"{record.detail}; falsification={snapshot.state.value}"
                ).strip("; "),
            }
        )

    @staticmethod
    def _rejected(
        *,
        operation: ConjectureOperation | None,
        plugin_id: str | None,
        request_digest: str,
        detail: str,
        started: float,
    ) -> ConjectureWorkflowResult:
        return ConjectureWorkflowResult(
            operation=operation,
            execution=Execution(
                status=ExecutionStatus.COMPLETED,
                runtime_ms=_elapsed_ms(started),
            ),
            input=InputValidation(
                status=InputStatus.REJECTED,
                errors=(detail,),
            ),
            request_digest=request_digest,
            plugin_id=plugin_id,
            detail=detail,
        )


def _artifact_view(artifact: StoredArtifact) -> dict[str, Any]:
    return {
        "artifact_uri": artifact.artifact_uri,
        "object_digest": artifact.manifest.object_digest,
        "schema_uri": artifact.manifest.schema_uri,
        "semantics_uri": artifact.manifest.semantics_uri,
        "payload": artifact.payload,
    }


def _digest(payload: object) -> str:
    return "sha256:" + hashlib.sha256(canonicalize_json(payload)).hexdigest()


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _deduplicate_uris(uris: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(uris))


def _digest_untrusted_request(
    request: ConjectureWorkflowRequest | dict[str, Any],
) -> str:
    try:
        payload = (
            request.model_dump(mode="json")
            if isinstance(request, ConjectureWorkflowRequest)
            else request
        )
        return _digest(payload)
    except ValueError:
        return _digest({"invalid_request": True})
