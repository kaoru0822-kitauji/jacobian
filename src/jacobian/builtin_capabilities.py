"""Bundled adapters for memory, reference domains, and Lean."""

from __future__ import annotations

from typing import Any

from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityDescriptor,
    CapabilityMode,
    CapabilityRequest,
    CapabilityResult,
)
from jacobian.contracts.evaluation import EvaluationProfile
from jacobian.contracts.evidence import WitnessRole
from jacobian.contracts.lean import LeanEnvironment
from jacobian.contracts.results import Execution, ExecutionStatus, Verification
from jacobian.contracts.workflows import WitnessVerificationWorkflowResult
from jacobian.lean import LeanService
from jacobian.memory import ResearchMemory
from jacobian.workflows import VerificationWorkflowService

_OBJECT_SCHEMA: dict[str, Any] = {"type": "object"}


class KnowledgeSearchAdapter:
    def __init__(self, memory: ResearchMemory) -> None:
        self.memory = memory
        self._descriptor = CapabilityDescriptor(
            capability_id="knowledge.search",
            version="1",
            title="Search research memory",
            description=(
                "Retrieve trust-labeled prior capability episodes; retrieval does "
                "not promote their mathematical assurance."
            ),
            provider="jacobian.memory",
            modes=(CapabilityMode.EXPLORE,),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "maxLength": 512},
                    "capability_id": {"type": "string"},
                    "assurance_level": {"enum": ["HEURISTIC", "COMPUTED", "VERIFIED"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "additionalProperties": False,
            },
            output_schema=_OBJECT_SCHEMA,
            read_only=True,
            records_episode=False,
            tags=("memory", "retrieval"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        selected = request.input
        result = self.memory.search(
            query=str(selected.get("query", "")),
            capability_id=(
                str(selected["capability_id"]) if "capability_id" in selected else None
            ),
            assurance_level=selected.get("assurance_level"),
            limit=int(selected.get("limit", 10)),
        )
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            output=result.model_dump(mode="json"),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=(
                    "deterministic local index query; each hit retains its own "
                    "assurance label"
                ),
            ),
        )


class ReferenceSolveAdapter:
    def __init__(self, workflows: VerificationWorkflowService) -> None:
        self.workflows = workflows
        self._descriptor = CapabilityDescriptor(
            capability_id="reference.solve",
            version="1",
            title="Explore or verify a bundled reference domain",
            description=(
                "Evaluate one candidate and seek a witness; VERIFY additionally "
                "replays found evidence with the authorized checker."
            ),
            provider="jacobian.references",
            modes=(CapabilityMode.EXPLORE, CapabilityMode.VERIFY),
            input_schema={
                "type": "object",
                "properties": {
                    "reference_name": {"type": "string", "minLength": 1},
                    "predicate": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "minLength": 1},
                            "parameters": {"type": "object"},
                        },
                        "required": ["name"],
                        "additionalProperties": False,
                    },
                    "candidate": {"type": "object"},
                    "witness_role": {
                        "enum": [
                            "DEFEATS_CANDIDATE",
                            "RESCUES_CANDIDATE",
                            "SUPPORTS_CLAIM",
                            "REFUTES_CLAIM",
                        ]
                    },
                    "profile": {"enum": ["FAST", "EXACT_CANDIDATE"]},
                    "seed": {"type": "integer"},
                    "evaluation_wall_seconds": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 86400,
                    },
                    "witness_wall_seconds": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 86400,
                    },
                },
                "required": [
                    "reference_name",
                    "predicate",
                    "candidate",
                    "witness_role",
                ],
                "additionalProperties": False,
            },
            output_schema=_OBJECT_SCHEMA,
            tags=("reference", "search", "verification"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        payload = request.input
        reference_name = str(payload["reference_name"])
        try:
            reference = self.workflows.references[reference_name]
        except KeyError as exc:
            raise ValueError(f"unknown reference domain: {reference_name}") from exc
        claim_payload = {
            "claim_schema_version": "1",
            "domain_id": reference.domain_id,
            "domain_version": reference.domain_version,
            "semantics_uri": reference.semantics_uri,
            "quantifiers": [],
            "predicate": payload["predicate"],
            "bounds": {},
            "required_capabilities": list(reference.available_capabilities),
            "correspondence_status": "UNREVIEWED",
        }
        arguments = {
            "reference_name": reference_name,
            "claim_payload": claim_payload,
            "candidate_payload": payload["candidate"],
            "witness_role": WitnessRole(str(payload["witness_role"])),
            "profile": EvaluationProfile(str(payload.get("profile", "FAST"))),
            "seed": int(payload.get("seed", 0)),
            "evaluation_wall_seconds": int(payload.get("evaluation_wall_seconds", 60)),
            "witness_wall_seconds": int(payload.get("witness_wall_seconds", 300)),
        }
        workflow = (
            self.workflows.explore_witness(**arguments)
            if request.mode is CapabilityMode.EXPLORE
            else self.workflows.verify_witness(**arguments)
        )
        return _reference_result(
            request,
            self.descriptor,
            workflow,
            claim_payload=claim_payload,
        )


class LeanCheckAdapter:
    def __init__(self, lean: LeanService) -> None:
        self.lean = lean
        self._descriptor = CapabilityDescriptor(
            capability_id="lean.check",
            version="1",
            title="Check a Lean proof",
            description=(
                "Compile and replay one proposition with the pinned CORE or MATHLIB "
                "kernel profile."
            ),
            provider="jacobian.lean4",
            modes=(CapabilityMode.VERIFY,),
            input_schema={
                "type": "object",
                "properties": {
                    "statement": {"type": "string", "minLength": 1, "maxLength": 2000},
                    "proof": {"type": "string", "minLength": 1, "maxLength": 20000},
                    "environment": {"enum": ["CORE", "MATHLIB"]},
                },
                "required": ["statement", "proof"],
                "additionalProperties": False,
            },
            output_schema=_OBJECT_SCHEMA,
            tags=("lean", "proof", "verification"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        payload = request.input
        checked = self.lean.verify(
            statement=str(payload["statement"]),
            proof=str(payload["proof"]),
            environment=LeanEnvironment(str(payload.get("environment", "CORE"))),
        )
        verified = (
            checked.result.assurance.verification is Verification.VERIFIED
            and checked.result.verification_record_uri is not None
        )
        evidence = (checked.certificate_uri,)
        scope_uri = checked.result.assurance.scope_uri
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=checked.result.execution,
            output={
                "conclusion": checked.result.conclusion.value,
                "claim_uri": checked.claim_uri,
                "candidate_uri": checked.candidate_uri,
                "certificate_uri": checked.certificate_uri,
                "verification_record_uri": checked.result.verification_record_uri,
            },
            assurance=CapabilityAssurance(
                level=(
                    CapabilityAssuranceLevel.VERIFIED
                    if verified
                    else CapabilityAssuranceLevel.HEURISTIC
                ),
                basis=(
                    "accepted by the pinned Lean checker"
                    if verified
                    else "Lean checker did not accept the supplied proof"
                ),
                verification_record_uri=checked.result.verification_record_uri,
            ),
            artifact_uris=(
                checked.claim_uri,
                checked.candidate_uri,
                *evidence,
                *((scope_uri,) if scope_uri is not None else ()),
            ),
        )


def _reference_result(
    request: CapabilityRequest,
    descriptor: CapabilityDescriptor,
    workflow: WitnessVerificationWorkflowResult,
    *,
    claim_payload: dict[str, Any],
) -> CapabilityResult:
    evaluation = (
        workflow.evaluation.items[0]
        if workflow.evaluation is not None and workflow.evaluation.items
        else None
    )
    witness = workflow.witness_search
    verification = workflow.verification
    verification_record_uri = (
        verification.verification_record_uri if verification is not None else None
    )
    verified = (
        verification is not None
        and verification.assurance.verification is Verification.VERIFIED
        and verification_record_uri is not None
    )
    evidence_uri = (
        witness.witness_uri or witness.certificate_uri if witness is not None else None
    )
    scope_uri = verification.assurance.scope_uri if verification is not None else None
    artifacts = tuple(
        uri
        for uri in (
            workflow.claim_uri,
            workflow.candidate_uri,
            evidence_uri,
            scope_uri,
        )
        if uri is not None
    )
    execution = (
        verification.execution
        if verification is not None
        else (
            witness.result.execution
            if witness is not None
            else (
                workflow.evaluation.execution
                if workflow.evaluation is not None
                else Execution(
                    status=ExecutionStatus.ERROR,
                    detail="workflow stopped before evaluation",
                )
            )
        )
    )
    return CapabilityResult(
        capability_id=descriptor.capability_id,
        capability_version=descriptor.version,
        mode=request.mode,
        execution=execution,
        output={
            "claim_valid": workflow.claim_validation.valid,
            "conclusion": (
                verification.conclusion.value
                if verification is not None
                else (
                    evaluation.result.conclusion.value
                    if evaluation is not None
                    else "UNKNOWN"
                )
            ),
            "evaluation": (
                {
                    "conclusion": evaluation.result.conclusion.value,
                    "objectives": evaluation.objectives,
                    "features": evaluation.features,
                    "detail": evaluation.detail,
                }
                if evaluation is not None
                else None
            ),
            "witness_status": witness.status.value if witness is not None else None,
            "claim_uri": workflow.claim_uri,
            "candidate_uri": workflow.candidate_uri,
            "evidence_uri": evidence_uri,
            "verification_record_uri": (verification_record_uri),
        },
        scope=_scope_from_claim(claim_payload),
        assurance=CapabilityAssurance(
            level=(
                CapabilityAssuranceLevel.VERIFIED
                if verified
                else CapabilityAssuranceLevel.HEURISTIC
            ),
            basis=(
                "authorized independent checker accepted the discovered evidence"
                if verified
                else "plugin evaluation and witness search without checker promotion"
            ),
            verification_record_uri=verification_record_uri if verified else None,
        ),
        artifact_uris=artifacts,
    )


def _scope_from_claim(claim: object) -> dict[str, Any]:
    if not isinstance(claim, dict):
        return {}
    return {
        key: claim[key]
        for key in ("domain_id", "domain_version", "predicate", "bounds")
        if key in claim
    }
