"""Install domain operations into Jacobian's runtime protocol."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from jacobian.artifacts import ArtifactService
from jacobian.capabilities import CapabilityAdapter, CapabilityInvocationError
from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityCompleteness,
    CapabilityCompletenessStatus,
    CapabilityDescriptor,
    CapabilityMode,
    CapabilityRelationship,
    CapabilityRequest,
    CapabilityResult,
    CapabilityScope,
)
from jacobian.contracts.domain_operations import ComputedOperationOutput
from jacobian.contracts.results import ContractModel, Execution, ExecutionStatus
from jacobian.operations import (
    BoundedSearchNotApplicable,
    BoundedSearchOperation,
    BoundedSearchWitness,
    ComputedNotApplicable,
    ComputedOperation,
    DomainBundle,
    DomainOperation,
)
from jacobian.schema_registry import SchemaRegistry, model_schema
from jacobian.store import ArtifactStore


@dataclass(frozen=True, slots=True)
class InstalledDomainBundle:
    """Resources and adapters created for one installed domain bundle."""

    adapters: tuple[CapabilityAdapter, ...]
    semantics_uri: str
    input_schema_uris: dict[type[ContractModel], str]
    result_schema_uris: dict[str, str]


@dataclass(frozen=True, slots=True)
class _OperationResources:
    artifacts: ArtifactService
    semantics_uri: str
    input_schema_uris: dict[type[ContractModel], str]
    result_schema_uris: dict[str, str]


class OperationInstaller:
    """Own schema, semantics, artifact, and result-envelope mechanics."""

    def __init__(
        self,
        store: ArtifactStore,
        schemas: SchemaRegistry,
        artifacts: ArtifactService,
    ) -> None:
        self.store = store
        self.schemas = schemas
        self.artifacts = artifacts

    def install(self, bundle: DomainBundle) -> InstalledDomainBundle:
        self._validate_bundle(bundle)
        semantics_uri = self.store.register_descriptor(
            kind="semantics",
            name=bundle.semantics.name,
            version=bundle.semantics.version,
            definition=bundle.semantics.definition,
        )
        request_models = {operation.request_model for operation in bundle.capabilities}
        input_schema_uris = {
            model: self.schemas.register_model(
                name=(f"{bundle.schema_namespace}-input.{model.__name__}"),
                version="1",
                model=model,
            )
            for model in request_models
        }
        result_schema_uris = {
            operation.capability_id: self.schemas.register_model(
                name=(f"{bundle.schema_namespace}-result.{operation.capability_id}"),
                version=operation.version,
                model=operation.result_model,
            )
            for operation in bundle.capabilities
        }
        resources = _OperationResources(
            artifacts=self.artifacts,
            semantics_uri=semantics_uri,
            input_schema_uris=input_schema_uris,
            result_schema_uris=result_schema_uris,
        )
        adapters = tuple(
            self._adapter(operation, bundle, resources)
            for operation in bundle.capabilities
        )
        return InstalledDomainBundle(
            adapters=adapters,
            semantics_uri=semantics_uri,
            input_schema_uris=input_schema_uris,
            result_schema_uris=result_schema_uris,
        )

    @staticmethod
    def _adapter(
        operation: DomainOperation,
        bundle: DomainBundle,
        resources: _OperationResources,
    ) -> CapabilityAdapter:
        if isinstance(operation, ComputedOperation):
            return ComputedOperationAdapter(operation, bundle, resources)
        if isinstance(operation, BoundedSearchOperation):
            return BoundedSearchOperationAdapter(operation, bundle, resources)
        raise TypeError(f"unsupported domain operation: {type(operation).__name__}")

    @staticmethod
    def _validate_bundle(bundle: DomainBundle) -> None:
        if not bundle.capabilities:
            raise ValueError("capability bundle must not be empty")
        ids = tuple(operation.capability_id for operation in bundle.capabilities)
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate capability ID in bundle {bundle.domain_id}")
        if bundle.provider_runtime.provider == "":
            raise ValueError("capability bundle provider must not be empty")


class ComputedOperationAdapter:
    """Run one typed finite producer without granting verification authority."""

    def __init__(
        self,
        operation: ComputedOperation[Any, Any],
        bundle: DomainBundle,
        resources: _OperationResources,
    ) -> None:
        self.operation = operation
        self.bundle = bundle
        self.resources = resources
        # Pydantic supports runtime specialization of generic response models.
        # Static type checkers cannot resolve a model class held in a value.
        self.output_model = ComputedOperationOutput[operation.result_model]  # type: ignore[name-defined]
        self._descriptor = CapabilityDescriptor(
            capability_id=operation.capability_id,
            version=operation.version,
            title=operation.title,
            description=operation.description,
            provider=bundle.provider_runtime.provider,
            provider_runtime=bundle.provider_runtime,
            modes=(CapabilityMode.EXPLORE,),
            input_schema=model_schema(operation.request_model),
            output_schema=model_schema(self.output_model),
            tags=operation.tags,
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        try:
            validated_request = self.operation.request_model.model_validate(
                request.input
            )
        except ValidationError as exc:
            raise CapabilityInvocationError(
                self.bundle.diagnostics.invalid_request
            ) from exc

        started = time.monotonic()
        outcome = self.operation.implementation(validated_request)
        if isinstance(outcome, ComputedNotApplicable):
            raise CapabilityInvocationError(outcome.diagnostic)
        validated_result = self.operation.result_model.model_validate(outcome.value)
        request_payload = validated_request.model_dump(mode="json")
        result_payload = validated_result.model_dump(mode="json")

        input_uri = self.resources.artifacts.put(
            schema_uri=self.resources.input_schema_uris[self.operation.request_model],
            semantics_uri=self.resources.semantics_uri,
            payload=request_payload,
            summary=f"{self.operation.capability_id} exact input",
        ).artifact_uri
        result_uri = self.resources.artifacts.put(
            schema_uri=self.resources.result_schema_uris[self.operation.capability_id],
            semantics_uri=self.resources.semantics_uri,
            payload=result_payload,
            parents=(input_uri,),
            summary=f"{self.operation.capability_id} exact result",
        ).artifact_uri

        output = self.output_model(
            input_uri=input_uri,
            result_uri=result_uri,
            result=validated_result,
            backend_version=self.bundle.backend_version,
        )
        return CapabilityResult(
            capability_id=self.operation.capability_id,
            capability_version=self.operation.version,
            mode=request.mode,
            execution=Execution(
                status=ExecutionStatus.COMPLETED,
                runtime_ms=max(0, round((time.monotonic() - started) * 1000)),
            ),
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description=self.bundle.scope_description,
                parameters={"input_uri": input_uri},
                artifact_uri=input_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.COMPLETE,
                basis=self.bundle.completeness_basis,
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            relationships=(
                CapabilityRelationship(
                    relation_id=self.operation.relation_id,
                    source_artifact_uris=(input_uri,),
                    target_artifact_uris=(result_uri,),
                ),
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=self.bundle.assurance_basis,
            ),
            artifact_uris=(input_uri, result_uri),
        )


class BoundedSearchOperationAdapter:
    """Run one budgeted producer without granting verification authority."""

    def __init__(
        self,
        operation: BoundedSearchOperation[Any, Any],
        bundle: DomainBundle,
        resources: _OperationResources,
    ) -> None:
        self.operation = operation
        self.bundle = bundle
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id=operation.capability_id,
            version=operation.version,
            title=operation.title,
            description=operation.description,
            provider=bundle.provider_runtime.provider,
            provider_runtime=bundle.provider_runtime,
            modes=(CapabilityMode.EXPLORE,),
            input_schema=model_schema(operation.request_model),
            output_schema=model_schema(operation.result_model),
            tags=operation.tags,
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        try:
            validated_request = self.operation.request_model.model_validate(
                request.input
            )
        except ValidationError as exc:
            raise CapabilityInvocationError(
                self.bundle.diagnostics.invalid_request
            ) from exc

        started = time.monotonic()
        outcome = self.operation.implementation(validated_request)
        if isinstance(outcome, BoundedSearchNotApplicable):
            raise CapabilityInvocationError(outcome.diagnostic)
        validated_result = self.operation.result_model.model_validate(outcome.value)
        witness_outcome = isinstance(outcome, BoundedSearchWitness)
        complete = self.operation.is_complete(validated_result)
        if complete != witness_outcome:
            raise ValueError(
                "bounded-search outcome contradicts its completion predicate"
            )
        request_payload = validated_request.model_dump(mode="json")
        result_payload = validated_result.model_dump(mode="json")
        input_uri = self.resources.artifacts.put(
            schema_uri=self.resources.input_schema_uris[self.operation.request_model],
            semantics_uri=self.resources.semantics_uri,
            payload=request_payload,
            summary=f"{self.operation.capability_id} bounded-search input",
        ).artifact_uri
        result_uri = self.resources.artifacts.put(
            schema_uri=self.resources.result_schema_uris[self.operation.capability_id],
            semantics_uri=self.resources.semantics_uri,
            payload=result_payload,
            parents=(input_uri,),
            summary=f"{self.operation.capability_id} bounded-search result",
        ).artifact_uri
        return CapabilityResult(
            capability_id=self.operation.capability_id,
            capability_version=self.operation.version,
            mode=request.mode,
            execution=Execution(
                status=ExecutionStatus.COMPLETED,
                runtime_ms=max(0, round((time.monotonic() - started) * 1000)),
            ),
            output=result_payload,
            scope=CapabilityScope(
                description=self.bundle.scope_description,
                parameters=self.operation.scope_parameters(
                    validated_request,
                    validated_result,
                ),
                artifact_uri=input_uri,
            ),
            completeness=CapabilityCompleteness(
                status=(
                    CapabilityCompletenessStatus.COMPLETE
                    if complete
                    else CapabilityCompletenessStatus.UNKNOWN
                ),
                basis=(
                    self.bundle.completeness_basis
                    if complete
                    else self.operation.incomplete_basis
                ),
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            relationships=(
                CapabilityRelationship(
                    relation_id=self.operation.relation_id,
                    source_artifact_uris=(input_uri,),
                    target_artifact_uris=(result_uri,),
                ),
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=self.bundle.assurance_basis,
            ),
            artifact_uris=(input_uri, result_uri),
        )
