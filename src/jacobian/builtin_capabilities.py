"""Bundled adapters for research memory and Lean."""

from __future__ import annotations

from typing import Any

from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityDescriptor,
    CapabilityMode,
    CapabilityProviderRuntime,
    CapabilityRequest,
    CapabilityResult,
)
from jacobian.contracts.lean import LeanEnvironment
from jacobian.contracts.results import (
    Execution,
    ExecutionStatus,
    Verification,
)
from jacobian.lean import LeanService
from jacobian.memory import ResearchMemory
from jacobian.provider_runtime import known_provider_runtime

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
            provider_runtime=known_provider_runtime(
                "jacobian.memory",
                features=("memory", "retrieval"),
            ),
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


class LeanCheckAdapter:
    def __init__(
        self,
        lean: LeanService,
        provider_runtime: CapabilityProviderRuntime,
    ) -> None:
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
            provider_runtime=provider_runtime,
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
                "execution": checked.result.execution.model_dump(mode="json"),
                "input": checked.result.input.model_dump(mode="json"),
                "diagnostics": list(checked.result.input.errors),
                "claim_uri": checked.claim_uri,
                "candidate_uri": checked.candidate_uri,
                "certificate_uri": checked.certificate_uri,
                "verification_record_uri": checked.result.verification_record_uri,
                "cache_hit": checked.cache_hit,
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
