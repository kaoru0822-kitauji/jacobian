"""Atomic capability adapters over the kernel's existing mathematical services.

The adapters intentionally expose individual materialization, evaluation,
search, and replay operations.  They do not compose those operations into a
verification workflow: search output remains computed evidence until an
explicit checker-backed capability accepts it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter

from jacobian.contracts.artifacts import ArtifactPutResult
from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityCompleteness,
    CapabilityCompletenessStatus,
    CapabilityDescriptor,
    CapabilityMode,
    CapabilityRequest,
    CapabilityResult,
    CapabilityScope,
)
from jacobian.contracts.claims import ClaimValidationResult
from jacobian.contracts.conjectures import ParameterRegion, ParameterRegionEvidence
from jacobian.contracts.discovery import (
    ExperimentCancelResult,
    ExperimentHandle,
    ExperimentSnapshot,
    StructureCanonicalizationResult,
)
from jacobian.contracts.evaluation import EvaluationBatchResult, EvaluationProfile
from jacobian.contracts.evidence import WitnessRole
from jacobian.contracts.polytope import PolytopeSeparateRequest, PolytopeSeparateResult
from jacobian.contracts.results import (
    Coverage,
    Execution,
    ExecutionStatus,
    ResultEnvelope,
    Verification,
)
from jacobian.contracts.search import ExperimentControlResult, SearchExperimentSnapshot
from jacobian.contracts.shrinking import ShrinkResult
from jacobian.contracts.transformations import (
    TransformationApplyResult,
    TransformationRelation,
)
from jacobian.contracts.witness_search import WitnessFindResult
from jacobian.experiments import ExperimentNotFoundError
from jacobian.store import ArtifactStore, StoreError

if TYPE_CHECKING:
    from jacobian.kernel import JacobianKernel


_ARTIFACT_URI_PATTERN = r"^artifact://sha256/[0-9a-f]{64}$"
_CHECKER_URI_PATTERN = r"^checker://sha256/[0-9a-f]{64}$"
_EXPERIMENT_URI_PATTERN = r"^experiment://[0-9a-f]{32}$"
_ARTIFACT_URI = {"type": "string", "pattern": _ARTIFACT_URI_PATTERN}
_CHECKER_URI = {"type": "string", "pattern": _CHECKER_URI_PATTERN}
_EXPERIMENT_URI = {"type": "string", "pattern": _EXPERIMENT_URI_PATTERN}


class AtomicServiceAdapter:
    """Project one service operation into the capability protocol.

    A service result may carry a nested :class:`ResultEnvelope`; only that
    envelope (or an explicitly promoted parameter region) can elevate the
    capability assurance.  This keeps evaluator, enumerator, and solver
    output from self-certifying merely because it found useful evidence.
    """

    def __init__(
        self,
        *,
        capability_id: str,
        title: str,
        description: str,
        modes: tuple[CapabilityMode, ...],
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        invoke: Callable[[dict[str, Any]], Any],
        store: ArtifactStore,
        unverified_assurance_level: CapabilityAssuranceLevel = (
            CapabilityAssuranceLevel.COMPUTED
        ),
        unverified_basis: str = "deterministic local service result",
        read_only: bool = False,
        tags: tuple[str, ...] = (),
    ) -> None:
        self._descriptor = CapabilityDescriptor(
            capability_id=capability_id,
            version="1",
            title=title,
            description=description,
            provider="jacobian.kernel",
            modes=modes,
            input_schema=input_schema,
            output_schema=output_schema,
            read_only=read_only,
            tags=tags,
        )
        self._invoke = invoke
        self._store = store
        self._unverified_assurance_level = unverified_assurance_level
        self._unverified_basis = unverified_basis

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        value = self._invoke(request.input)
        output = _dump(value)
        execution = _execution(value)
        record_uri = _verified_record_uri(value)
        artifact_uris = _artifact_uris(output)
        verification_artifacts: tuple[str, ...] | None = None
        if record_uri is not None:
            verification_artifacts = _verification_bindings(
                record_uri,
                artifact_uris,
                self._store,
            )
            if verification_artifacts is not None:
                artifact_uris = verification_artifacts
        verified = (
            execution.status is ExecutionStatus.COMPLETED
            and record_uri is not None
            and verification_artifacts is not None
            and _is_verified(value)
        )
        scope, completeness = _scope_and_completeness(
            value,
            request_input=request.input,
            verified=verified,
            assurance_level=(
                CapabilityAssuranceLevel.VERIFIED
                if verified
                else self._unverified_assurance_level
            ),
            verification_record_uri=record_uri if verified else None,
        )
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=execution,
            output=output,
            scope=scope,
            completeness=completeness,
            assurance=CapabilityAssurance(
                level=(
                    CapabilityAssuranceLevel.VERIFIED
                    if verified
                    else self._unverified_assurance_level
                ),
                basis=(
                    "accepted by an authorized independent checker"
                    if verified
                    else self._unverified_basis
                ),
                verification_record_uri=record_uri if verified else None,
            ),
            artifact_uris=artifact_uris,
        )


def install_atomic_capabilities(
    kernel: JacobianKernel,
) -> tuple[AtomicServiceAdapter, ...]:
    """Build the bundled atomic adapters without adding MCP-specific behavior."""

    def _adapter(**kwargs: Any) -> AtomicServiceAdapter:
        return AtomicServiceAdapter(store=kernel.store, **kwargs)

    adapters = (
        _adapter(
            capability_id="artifact.put",
            title="Store a schema-validated artifact",
            description="Materialize one immutable artifact with explicit lineage.",
            modes=(CapabilityMode.EXPLORE,),
            input_schema=_schema(
                {
                    "schema_uri": _ARTIFACT_URI,
                    "semantics_uri": _ARTIFACT_URI,
                    "payload": {},
                    "parents": {
                        "type": "array",
                        "items": _ARTIFACT_URI,
                        "maxItems": 1024,
                    },
                    "summary": {"type": "string", "maxLength": 512},
                },
                required=("schema_uri", "semantics_uri", "payload"),
            ),
            output_schema=ArtifactPutResult.model_json_schema(),
            invoke=lambda p: kernel.artifacts.put(
                schema_uri=p["schema_uri"],
                semantics_uri=p["semantics_uri"],
                payload=p["payload"],
                parents=tuple(p.get("parents", ())),
                summary=p.get("summary", ""),
            ),
            tags=("artifact", "storage"),
        ),
        _adapter(
            capability_id="claim.validate",
            title="Validate a claim against one plugin",
            description="Check claim schema, semantics, and declared plugin capabilities.",
            modes=(CapabilityMode.EXPLORE,),
            input_schema=_schema(
                {"claim_uri": _ARTIFACT_URI, "plugin_id": _ARTIFACT_URI},
                required=("claim_uri", "plugin_id"),
            ),
            output_schema=ClaimValidationResult.model_json_schema(),
            invoke=lambda p: kernel.claims.validate(**p),
            read_only=True,
            tags=("claim", "validation"),
        ),
        _adapter(
            capability_id="evaluate.batch",
            title="Evaluate candidates",
            description="Run a plugin evaluator over a bounded batch without verification.",
            modes=(CapabilityMode.EXPLORE,),
            input_schema=_schema(
                {
                    "claim_uri": _ARTIFACT_URI,
                    "candidate_uris": {
                        "type": "array",
                        "items": _ARTIFACT_URI,
                        "minItems": 1,
                        "maxItems": 256,
                    },
                    "plugin_id": _ARTIFACT_URI,
                    "profile": {"enum": ["FAST", "EXACT_CANDIDATE"]},
                    "seed": {"type": "integer"},
                    "wall_seconds": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "maximum": 86400,
                    },
                },
                required=(
                    "claim_uri",
                    "candidate_uris",
                    "plugin_id",
                    "profile",
                    "seed",
                    "wall_seconds",
                ),
            ),
            output_schema=EvaluationBatchResult.model_json_schema(),
            invoke=lambda p: kernel.evaluation.evaluate_batch(
                **{
                    **p,
                    "candidate_uris": tuple(p["candidate_uris"]),
                    "profile": EvaluationProfile(p["profile"]),
                }
            ),
            unverified_assurance_level=CapabilityAssuranceLevel.HEURISTIC,
            unverified_basis="untrusted plugin evaluation is not independently verified",
            tags=("evaluation",),
        ),
        _adapter(
            capability_id="witness.find",
            title="Find one witness",
            description="Search for a witness or a bounded no-witness certificate proposal.",
            modes=(CapabilityMode.EXPLORE,),
            input_schema=_schema(
                {
                    "claim_uri": _ARTIFACT_URI,
                    "candidate_uri": _ARTIFACT_URI,
                    "plugin_id": _ARTIFACT_URI,
                    "witness_role": {
                        "enum": [
                            "DEFEATS_CANDIDATE",
                            "RESCUES_CANDIDATE",
                            "SUPPORTS_CLAIM",
                            "REFUTES_CLAIM",
                        ]
                    },
                    "wall_seconds": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "maximum": 86400,
                    },
                },
                required=(
                    "claim_uri",
                    "candidate_uri",
                    "plugin_id",
                    "witness_role",
                    "wall_seconds",
                ),
            ),
            output_schema=WitnessFindResult.model_json_schema(),
            invoke=lambda p: kernel.witnesses.find(
                **{**p, "witness_role": WitnessRole(p["witness_role"])}
            ),
            unverified_assurance_level=CapabilityAssuranceLevel.HEURISTIC,
            unverified_basis="witness search output is evidence pending explicit replay",
            tags=("witness", "search"),
        ),
        _adapter(
            capability_id="witness.verify",
            title="Verify one witness",
            description="Replay one witness with an explicitly selected authorized checker.",
            modes=(CapabilityMode.VERIFY,),
            input_schema=_verification_schema(
                {
                    "claim_uri": _ARTIFACT_URI,
                    "candidate_uri": _ARTIFACT_URI,
                    "witness_uri": _ARTIFACT_URI,
                    "checker_id": _CHECKER_URI,
                },
                required=("claim_uri", "candidate_uri", "witness_uri", "checker_id"),
            ),
            output_schema=ResultEnvelope.model_json_schema(),
            invoke=lambda p: kernel.verification.verify_witness(**p),
            unverified_assurance_level=CapabilityAssuranceLevel.HEURISTIC,
            unverified_basis="the checker did not accept the supplied witness",
            tags=("witness", "verification"),
        ),
        _adapter(
            capability_id="certificate.verify",
            title="Verify one certificate",
            description="Replay one certificate with a compatible authorized checker.",
            modes=(CapabilityMode.VERIFY,),
            input_schema=_verification_schema(
                {"certificate_uri": _ARTIFACT_URI, "checker_id": _CHECKER_URI},
                required=("certificate_uri",),
            ),
            output_schema=ResultEnvelope.model_json_schema(),
            invoke=lambda p: kernel.verification.verify_certificate(**p),
            unverified_assurance_level=CapabilityAssuranceLevel.HEURISTIC,
            unverified_basis="the checker did not accept the supplied certificate",
            tags=("certificate", "verification"),
        ),
        _adapter(
            capability_id="shrink.run",
            title="Shrink a candidate or witness",
            description="Apply bounded reductions and replay each accepted preservation claim.",
            modes=(CapabilityMode.EXPLORE,),
            input_schema=_schema(
                {
                    "target_kind": {"enum": ["candidate", "witness"]},
                    "target_uri": _ARTIFACT_URI,
                    "claim_uri": _ARTIFACT_URI,
                    "plugin_id": _ARTIFACT_URI,
                    "preservation_checker_id": _CHECKER_URI,
                    "reducers": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1, "maxLength": 128},
                        "minItems": 1,
                        "maxItems": 128,
                    },
                    "objectives": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1, "maxLength": 128},
                        "maxItems": 128,
                    },
                    "evaluation_budget": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000000,
                    },
                },
                required=(
                    "target_kind",
                    "target_uri",
                    "claim_uri",
                    "plugin_id",
                    "preservation_checker_id",
                    "reducers",
                    "objectives",
                    "evaluation_budget",
                ),
            ),
            output_schema=ShrinkResult.model_json_schema(),
            invoke=lambda p: kernel.shrinking.run(
                **{
                    **p,
                    "reducers": tuple(p["reducers"]),
                    "objectives": tuple(p["objectives"]),
                }
            ),
            unverified_assurance_level=CapabilityAssuranceLevel.HEURISTIC,
            unverified_basis="plugin-proposed reductions are not a verified minimality claim",
            tags=("shrink",),
        ),
        _adapter(
            capability_id="structure.canonicalize",
            title="Canonicalize one structure",
            description="Compute a plugin-defined canonical representative without self-certification.",
            modes=(CapabilityMode.EXPLORE,),
            input_schema=_schema(
                {
                    "structure_uri": _ARTIFACT_URI,
                    "plugin_id": _ARTIFACT_URI,
                    "wall_seconds": {"type": "integer", "minimum": 1, "maximum": 86400},
                },
                required=("structure_uri", "plugin_id", "wall_seconds"),
            ),
            output_schema=StructureCanonicalizationResult.model_json_schema(),
            invoke=lambda p: kernel.structures.canonicalize(**p),
            unverified_assurance_level=CapabilityAssuranceLevel.HEURISTIC,
            unverified_basis="plugin canonicalization is not independently verified",
            tags=("structure", "canonicalization"),
        ),
        _adapter(
            capability_id="search.enumerate",
            title="Start a bounded enumeration",
            description="Start one durable candidate-enumeration experiment; it cannot self-certify.",
            modes=(CapabilityMode.EXPLORE,),
            input_schema=_schema(
                {
                    "claim_uri": _ARTIFACT_URI,
                    "plugin_id": _ARTIFACT_URI,
                    "bounds": {"type": "object"},
                    "quotient_by_isomorphism": {"type": "boolean"},
                    "profile": {"enum": ["FAST", "EXACT_CANDIDATE"]},
                    "seed": {"type": "integer"},
                    "budget": _enumeration_budget_schema(),
                },
                required=("claim_uri", "plugin_id", "bounds", "budget"),
            ),
            output_schema=ExperimentHandle.model_json_schema(),
            invoke=lambda p: kernel.experiments.start_enumeration(p),
            unverified_assurance_level=CapabilityAssuranceLevel.HEURISTIC,
            unverified_basis="enumeration lifecycle state cannot certify a mathematical conclusion",
            tags=("search", "enumeration", "experiment"),
        ),
        _adapter(
            capability_id="experiment.inspect",
            title="Inspect one experiment",
            description="Read the durable state and accounting of one enumeration or search experiment.",
            modes=(CapabilityMode.EXPLORE,),
            input_schema=_schema(
                {"experiment_uri": _EXPERIMENT_URI}, required=("experiment_uri",)
            ),
            output_schema=TypeAdapter(
                ExperimentSnapshot | SearchExperimentSnapshot
            ).json_schema(),
            invoke=lambda p: _inspect_experiment(kernel, p["experiment_uri"]),
            read_only=True,
            tags=("experiment",),
        ),
        _adapter(
            capability_id="experiment.wait",
            title="Wait for an experiment update",
            description="Wait for a bounded interval and return the latest experiment snapshot.",
            modes=(CapabilityMode.EXPLORE,),
            input_schema=_schema(
                {
                    "experiment_uri": _EXPERIMENT_URI,
                    "timeout_seconds": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "maximum": 86400,
                    },
                },
                required=("experiment_uri",),
            ),
            output_schema=TypeAdapter(
                ExperimentSnapshot | SearchExperimentSnapshot
            ).json_schema(),
            invoke=lambda p: _wait_experiment(
                kernel, p["experiment_uri"], p.get("timeout_seconds", 30)
            ),
            read_only=True,
            tags=("experiment",),
        ),
        _adapter(
            capability_id="experiment.cancel",
            title="Request experiment cancellation",
            description="Request cancellation of one running enumeration or search experiment.",
            modes=(CapabilityMode.EXPLORE,),
            input_schema=_schema(
                {"experiment_uri": _EXPERIMENT_URI}, required=("experiment_uri",)
            ),
            output_schema=TypeAdapter(
                ExperimentCancelResult | ExperimentControlResult
            ).json_schema(),
            invoke=lambda p: _cancel_experiment(kernel, p["experiment_uri"]),
            tags=("experiment", "control"),
        ),
        _adapter(
            capability_id="transform.apply",
            title="Apply one representation transformation",
            description="Materialize a plugin-proposed transformation and its verification obligation.",
            modes=(CapabilityMode.EXPLORE,),
            input_schema=_schema(
                {
                    "source_uri": _ARTIFACT_URI,
                    "plugin_id": _ARTIFACT_URI,
                    "target_schema_uri": _ARTIFACT_URI,
                    "target_semantics_uri": _ARTIFACT_URI,
                    "requested_relation": {
                        "enum": [
                            "EQUIVALENT",
                            "OVER_APPROXIMATION",
                            "UNDER_APPROXIMATION",
                            "HEURISTIC",
                        ]
                    },
                    "wall_seconds": {"type": "integer", "minimum": 1, "maximum": 86400},
                },
                required=(
                    "source_uri",
                    "plugin_id",
                    "target_schema_uri",
                    "target_semantics_uri",
                    "requested_relation",
                    "wall_seconds",
                ),
            ),
            output_schema=TransformationApplyResult.model_json_schema(),
            invoke=lambda p: kernel.transformations.apply(
                **{
                    **p,
                    "requested_relation": TransformationRelation(
                        p["requested_relation"]
                    ),
                }
            ),
            unverified_assurance_level=CapabilityAssuranceLevel.HEURISTIC,
            unverified_basis="plugin transformation output remains an open verification obligation",
            tags=("transform",),
        ),
        _adapter(
            capability_id="transform.verify",
            title="Verify one transformation",
            description="Replay one transformation relation with its compatible authorized checker.",
            modes=(CapabilityMode.VERIFY,),
            input_schema=_schema(
                {"transformation_uri": _ARTIFACT_URI}, required=("transformation_uri",)
            ),
            output_schema=ResultEnvelope.model_json_schema(),
            invoke=lambda p: kernel.verification.verify_transformation(**p),
            unverified_assurance_level=CapabilityAssuranceLevel.HEURISTIC,
            unverified_basis="the checker did not accept the transformation relation",
            tags=("transform", "verification"),
        ),
        _adapter(
            capability_id="polytope.separate",
            title="Separate a rational point from a convex hull",
            description="Compute exact membership evidence or a separator; replay is separate.",
            modes=(CapabilityMode.EXPLORE,),
            input_schema=_schema(
                {
                    "point_uri": _ARTIFACT_URI,
                    "generator_set_uri": _ARTIFACT_URI,
                    "projection": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 0},
                        "minItems": 1,
                        "maxItems": 256,
                        "uniqueItems": True,
                    },
                    "wall_seconds": {"type": "integer", "minimum": 1, "maximum": 86400},
                },
                required=("point_uri", "generator_set_uri"),
            ),
            output_schema=PolytopeSeparateResult.model_json_schema(),
            invoke=lambda p: kernel.polytope.separate(PolytopeSeparateRequest(**p)),
            tags=("polytope", "exact"),
        ),
        _adapter(
            capability_id="parameter.region.promote",
            title="Promote one verified parameter region",
            description="Replay a record bound to an immutable region before marking it verified.",
            modes=(CapabilityMode.VERIFY,),
            input_schema=_schema(
                {
                    "subject_uri": _ARTIFACT_URI,
                    "verification_record_uri": _ARTIFACT_URI,
                },
                required=("subject_uri", "verification_record_uri"),
            ),
            output_schema=ParameterRegion.model_json_schema(),
            invoke=lambda p: kernel.conjectures.promote_parameter_region(**p),
            read_only=True,
            tags=("parameter", "verification"),
        ),
    )
    return adapters


def _schema(properties: dict[str, Any], *, required: Iterable[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


def _verification_schema(
    properties: dict[str, Any], *, required: Iterable[str]
) -> dict[str, Any]:
    combined = dict(properties)
    combined["timeout_seconds"] = {
        "type": "number",
        "exclusiveMinimum": 0,
        "maximum": 86400,
    }
    return _schema(combined, required=required)


def _enumeration_budget_schema() -> dict[str, Any]:
    return _schema(
        {
            "candidates_max": {"type": "integer", "minimum": 1, "maximum": 10000000},
            "wall_seconds": {"type": "integer", "minimum": 1, "maximum": 86400},
            "page_size": {"type": "integer", "minimum": 1, "maximum": 4096},
        },
        required=("candidates_max", "wall_seconds"),
    )


def _dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
    elif isinstance(value, dict):
        dumped = value
    else:
        raise TypeError("atomic capability service returned an unsupported value")
    if not isinstance(dumped, dict):
        raise TypeError("atomic capability service returned a non-object value")
    return dumped


def _scope_and_completeness(
    value: Any,
    *,
    request_input: dict[str, Any],
    verified: bool,
    assurance_level: CapabilityAssuranceLevel,
    verification_record_uri: str | None,
) -> tuple[CapabilityScope | None, CapabilityCompleteness]:
    envelope = _result_envelope(value)
    if envelope is None or envelope.assurance.coverage is Coverage.NOT_APPLICABLE:
        return (
            None,
            CapabilityCompleteness(
                basis="the operation makes no completeness claim",
            ),
        )

    scope_parameters = {
        key: item
        for key, item in request_input.items()
        if key.endswith("_uri")
        or key
        in {
            "bounds",
            "candidate_uris",
            "profile",
            "projection",
            "seed",
        }
    }
    scope = (
        CapabilityScope(
            description=(
                f"scope reported with {envelope.assurance.coverage.value} coverage"
            ),
            parameters=scope_parameters,
            artifact_uri=envelope.assurance.scope_uri,
        )
        if scope_parameters or envelope.assurance.scope_uri is not None
        else None
    )
    complete = (
        envelope.execution.status is ExecutionStatus.COMPLETED
        and envelope.assurance.coverage is Coverage.EXHAUSTIVE
        and scope is not None
    )
    checker_bound_scope = (
        envelope.assurance.scope_uri is not None and complete and verified
    )
    completeness_level = (
        CapabilityAssuranceLevel.VERIFIED
        if checker_bound_scope
        else (
            CapabilityAssuranceLevel.COMPUTED
            if assurance_level is CapabilityAssuranceLevel.VERIFIED
            else assurance_level
        )
    )
    return (
        scope,
        CapabilityCompleteness(
            status=(
                CapabilityCompletenessStatus.COMPLETE
                if complete
                else CapabilityCompletenessStatus.PARTIAL
            ),
            basis=(
                f"underlying result reports {envelope.assurance.coverage.value} "
                "coverage over the declared scope"
            ),
            assurance_level=completeness_level,
            verification_record_uri=(
                verification_record_uri
                if completeness_level is CapabilityAssuranceLevel.VERIFIED
                else None
            ),
        ),
    )


def _result_envelope(value: Any) -> ResultEnvelope | None:
    if isinstance(value, ResultEnvelope):
        return value
    nested = getattr(value, "result", None)
    return nested if isinstance(nested, ResultEnvelope) else None


def _execution(value: Any) -> Execution:
    execution = getattr(value, "execution", None)
    if isinstance(execution, Execution):
        return execution
    nested = getattr(value, "result", None)
    if isinstance(nested, ResultEnvelope):
        return nested.execution
    return Execution(status=ExecutionStatus.COMPLETED)


def _verified_record_uri(value: Any) -> str | None:
    envelope = _result_envelope(value)
    if envelope is not None:
        return envelope.verification_record_uri
    if getattr(value, "evidence", None) in {
        ParameterRegionEvidence.VERIFIED_SUFFICIENT,
        ParameterRegionEvidence.VERIFIED_NECESSARY,
    }:
        return getattr(value, "verification_record_uri", None)
    return None


def _is_verified(value: Any) -> bool:
    envelope = _result_envelope(value)
    if isinstance(envelope, ResultEnvelope):
        return envelope.assurance.verification is Verification.VERIFIED
    return getattr(value, "evidence", None) in {
        ParameterRegionEvidence.VERIFIED_SUFFICIENT,
        ParameterRegionEvidence.VERIFIED_NECESSARY,
    }


def _artifact_uris(value: Any) -> tuple[str, ...]:
    found: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, str) and item.startswith("artifact://sha256/"):
            found.add(item)

    visit(value)
    return tuple(sorted(found))


def _verification_bindings(
    record_uri: str,
    artifact_uris: tuple[str, ...],
    store: ArtifactStore,
) -> tuple[str, ...] | None:
    try:
        record = store.get(record_uri)
    except StoreError:
        return None
    return tuple(sorted({*artifact_uris, record_uri, *record.manifest.parents}))


def _inspect_experiment(kernel: JacobianKernel, experiment_uri: str) -> Any:
    try:
        return kernel.experiments.inspect(experiment_uri)
    except ExperimentNotFoundError:
        return kernel.search.inspect(experiment_uri)


def _wait_experiment(
    kernel: JacobianKernel,
    experiment_uri: str,
    timeout_seconds: float,
) -> Any:
    try:
        return kernel.experiments.wait(experiment_uri, timeout_seconds=timeout_seconds)
    except ExperimentNotFoundError:
        return kernel.search.wait(experiment_uri, timeout_seconds=timeout_seconds)


def _cancel_experiment(kernel: JacobianKernel, experiment_uri: str) -> Any:
    try:
        return kernel.experiments.cancel(experiment_uri)
    except ExperimentNotFoundError:
        return kernel.search.cancel(experiment_uri)
