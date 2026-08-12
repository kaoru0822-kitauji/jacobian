"""Bundled adapters for Lean capabilities."""

from __future__ import annotations

from typing import Any

from jacobian.artifacts import ArtifactService
from jacobian.capability_service import CapabilityInvocationError
from jacobian.contracts.capabilities import (
    CapabilityDescriptor,
    CapabilityDiagnostic,
    CapabilityInvocationExample,
    CapabilityProviderRuntime,
    CapabilityRequest,
    CapabilityResult,
)
from jacobian.contracts.lean import (
    LeanDeclarationInspectOutput,
    LeanDeclarationInspectRequest,
    LeanDeclarationSearchOutput,
    LeanDeclarationSearchRequest,
    LeanDependencyGraphOutput,
    LeanDependencyGraphRequest,
    LeanEnvironment,
)
from jacobian.contracts.results import (
    Execution,
    ExecutionStatus,
    Verification,
)
from jacobian.lean_frontend.declarations import (
    LeanDeclarationBackendError,
    LeanDeclarationService,
)
from jacobian.lean_frontend.service import LeanService
from jacobian.schema_registry import model_schema

_OBJECT_SCHEMA: dict[str, Any] = {"type": "object"}


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
                "kernel profile. Statements are single Lean expressions, including "
                "finite-witness let expressions; declarations and trust escapes are "
                "forbidden."
            ),
            provider="jacobian.lean4",
            provider_runtime=provider_runtime,
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
            tags=("lean", "proof", "verification", "finite-witness"),
            invocation_examples=(
                CapabilityInvocationExample(
                    name="finite-witness-let",
                    description=(
                        "Check a finite witness encoded as one let expression without "
                        "adding declarations."
                    ),
                    input={
                        "environment": "CORE",
                        "statement": "let n : Nat := 2; n + n = 4",
                        "proof": "rfl",
                    },
                ),
            ),
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
            checked.result.verification is Verification.VERIFIED
            and checked.result.verification_record_uri is not None
        )
        evidence = (checked.certificate_uri,)
        scope_uri = checked.result.scope_uri
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
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
            verification_record_uri=(
                checked.result.verification_record_uri if verified else None
            ),
            artifact_uris=(
                checked.claim_uri,
                checked.candidate_uri,
                *evidence,
                *((scope_uri,) if scope_uri is not None else ()),
                *(
                    (checked.result.verification_record_uri,)
                    if checked.result.verification_record_uri is not None
                    else ()
                ),
            ),
        )


class LeanDeclarationSearchAdapter:
    def __init__(
        self,
        declarations: LeanDeclarationService,
        provider_runtime: CapabilityProviderRuntime,
    ) -> None:
        self.declarations = declarations
        self._descriptor = CapabilityDescriptor(
            capability_id="lean.declaration.search",
            version="1",
            title="Search Lean declarations",
            description=(
                "Search a pinned Lean environment by a case-sensitive name substring "
                "and/or exact constants occurring in elaborated declaration types."
            ),
            provider="jacobian.lean4",
            provider_runtime=provider_runtime,
            input_schema=model_schema(LeanDeclarationSearchRequest),
            output_schema=model_schema(LeanDeclarationSearchOutput),
            read_only=True,
            tags=("lean", "declaration", "retrieval", "premise-discovery"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        query = LeanDeclarationSearchRequest.model_validate(request.input)
        try:
            searched = self.declarations.search(query)
        except LeanDeclarationBackendError as exc:
            raise _declaration_invocation_error(exc) from exc
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            output=searched.model_dump(mode="json"),
        )


class LeanDeclarationInspectAdapter:
    def __init__(
        self,
        declarations: LeanDeclarationService,
        provider_runtime: CapabilityProviderRuntime,
    ) -> None:
        self.declarations = declarations
        self._descriptor = CapabilityDescriptor(
            capability_id="lean.declaration.inspect",
            version="1",
            title="Inspect a Lean declaration",
            description=(
                "Resolve one exact declaration in a pinned Lean environment and "
                "return its elaborated type, kind, docs, source metadata, and "
                "environment digest."
            ),
            provider="jacobian.lean4",
            provider_runtime=provider_runtime,
            input_schema=model_schema(LeanDeclarationInspectRequest),
            output_schema=model_schema(LeanDeclarationInspectOutput),
            read_only=True,
            tags=("lean", "declaration", "retrieval", "inspection"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        query = LeanDeclarationInspectRequest.model_validate(request.input)
        try:
            inspected = self.declarations.inspect(query)
        except LeanDeclarationBackendError as exc:
            raise _declaration_invocation_error(exc) from exc
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            output=inspected.model_dump(mode="json"),
        )


class LeanDependencyGraphAdapter:
    def __init__(
        self,
        declarations: LeanDeclarationService,
        provider_runtime: CapabilityProviderRuntime,
        artifacts: ArtifactService,
        *,
        semantics_uri: str,
        dependency_graph_schema_uri: str,
    ) -> None:
        self.declarations = declarations
        self.artifacts = artifacts
        self.semantics_uri = semantics_uri
        self.dependency_graph_schema_uri = dependency_graph_schema_uri
        self._descriptor = CapabilityDescriptor(
            capability_id="lean.declaration.dependencies",
            version="1",
            title="Extract Lean declaration dependencies",
            description=(
                "Extract a bounded dependency subgraph from elaborated declaration "
                "types and values in a pinned Lean environment."
            ),
            provider="jacobian.lean4",
            provider_runtime=provider_runtime,
            input_schema=model_schema(LeanDependencyGraphRequest),
            output_schema=model_schema(LeanDependencyGraphOutput),
            read_only=True,
            tags=("lean", "declaration", "dependency-graph", "formal-artifact"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        query = LeanDependencyGraphRequest.model_validate(request.input)
        try:
            graph = self.declarations.dependencies(query)
        except LeanDeclarationBackendError as exc:
            raise _declaration_invocation_error(exc) from exc
        graph_artifact = self.artifacts.put(
            schema_uri=self.dependency_graph_schema_uri,
            semantics_uri=self.semantics_uri,
            payload=graph.model_dump(mode="json"),
            summary=(
                f"bounded Lean dependency subgraph rooted at {query.root_declaration}"
            ),
        )
        output = LeanDependencyGraphOutput(
            **graph.model_dump(mode="python"),
            dependency_graph_uri=graph_artifact.artifact_uri,
        )
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            output=output.model_dump(mode="json"),
            artifact_uris=(graph_artifact.artifact_uri,),
        )


def _declaration_invocation_error(
    error: LeanDeclarationBackendError,
) -> CapabilityInvocationError:
    return CapabilityInvocationError(
        CapabilityDiagnostic(
            code=error.code,
            stage="lean_declaration_query",
            message=error.message,
            hint=(
                "Call math.find for the exact query contract and verify "
                "that the requested pinned environment is installed."
            ),
        )
    )
