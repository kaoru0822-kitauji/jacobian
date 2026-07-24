"""Thin MCP 2.0.0b2 adapter over the tested Python kernel."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, cast

from mcp_types import ToolAnnotations
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from jacobian import __version__
from jacobian.contracts.artifacts import ArtifactPutResult
from jacobian.contracts.capabilities import (
    CapabilityMode,
    CapabilityRequest,
    CapabilityResult,
)
from jacobian.contracts.claims import ClaimValidationResult
from jacobian.contracts.conjectures import (
    ConjectureOperation,
    ConjectureWorkflowRequest,
    ConjectureWorkflowResult,
    FalsificationPlan,
    ParameterRegion,
)
from jacobian.contracts.discovery import (
    EnumerationBudget,
    ExperimentHandle,
    SearchEnumerateRequest,
    StructureCanonicalizationResult,
)
from jacobian.contracts.evaluation import (
    EvaluationBatchResult,
    EvaluationProfile,
)
from jacobian.contracts.evidence import WitnessRole
from jacobian.contracts.lean import LeanEnvironment, LeanVerifyResult
from jacobian.contracts.polytope import (
    PolytopeSeparateRequest,
    PolytopeSeparateResult,
)
from jacobian.contracts.results import (
    ResultEnvelope,
    validate_result_envelope,
)
from jacobian.contracts.search import (
    ExperimentControlResult,
    SearchBudget,
    SearchRunRequest,
)
from jacobian.contracts.shrinking import ShrinkResult
from jacobian.contracts.transformations import (
    TransformationApplyResult,
    TransformationRelation,
)
from jacobian.contracts.witness_search import WitnessFindResult
from jacobian.contracts.workflows import WitnessVerificationWorkflowResult

if TYPE_CHECKING:
    from mcp.server import MCPServer
    from mcp.server.mcpserver import Context

    from jacobian.adapters.mcp.remote import TenantKernelRouter
    from jacobian.kernel import JacobianKernel
    from jacobian.workflows import VerificationWorkflowService


SERVER_INSTRUCTIONS = (
    "When a capability ID and input are known, invoke it directly; otherwise start "
    "with capability://catalog. Use "
    "EXPLORE for low-friction search and VERIFY only when a durable checked conclusion "
    "is needed. Advanced clients may inspect reference://catalog for lower-level domain "
    "contracts and assurance.verification details. Retrieved memory, search, evaluation, "
    "generated witnesses, conjectures, "
    "transformations, and polytope evidence are not proof. Only assurance level VERIFIED "
    "with a local verification record is verified. Operational completion, failure to "
    "find a witness, and exhausted or bounded search are not mathematical conclusions. "
    "Follow returned artifact:// and experiment:// resources instead of requesting "
    "large payloads inline."
)

CAPABILITY_TOOL_NAMES = frozenset({"capability.invoke"})
VERIFICATION_TOOL_NAMES = frozenset(
    {
        "artifact.put",
        "claim.validate",
        "evaluate.batch",
        "lean.verify",
        "verification.run",
        "witness.find",
        "witness.verify",
        "certificate.verify",
    }
)
NON_VERIFICATION_TOOL_NAMES = frozenset(
    {
        "conjecture.generate",
        "conjecture.repair",
        "experiment.cancel",
        "experiment.pause",
        "experiment.resume",
        "parameter.generalize",
        "parameter.region.promote",
        "polytope.separate",
        "search.enumerate",
        "search.run",
        "shrink.run",
        "structure.canonicalize",
        "transform.apply",
        "transform.verify",
    }
)


class ToolProfile(StrEnum):
    FULL = "full"
    CAPABILITIES = "capabilities"
    VERIFICATION = "verification"


def _tool_annotations(
    *,
    read_only: bool = False,
    destructive: bool = False,
    idempotent: bool = False,
) -> ToolAnnotations:
    return ToolAnnotations(
        read_only_hint=read_only,
        destructive_hint=destructive,
        idempotent_hint=idempotent,
        open_world_hint=False,
    )


class AdapterModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvaluationBudget(AdapterModel):
    wall_seconds: int = Field(default=60, ge=1, le=86_400)


class WitnessBudget(AdapterModel):
    wall_seconds: int = Field(default=300, ge=1, le=86_400)


class ShrinkBudget(AdapterModel):
    evaluations: int = Field(default=10_000, ge=1, le=10_000_000)


class EnumerationBudgetInput(AdapterModel):
    candidates_max: int = Field(default=100_000, ge=1, le=10_000_000)
    wall_seconds: int = Field(default=300, ge=1, le=86_400)
    page_size: int = Field(default=128, ge=1, le=4096)


class SearchBudgetInput(AdapterModel):
    candidates_max: int = Field(default=100_000, ge=1, le=10_000_000)
    iterations_max: int = Field(default=10_000, ge=1, le=10_000_000)
    wall_seconds: int = Field(default=300, ge=1, le=86_400)
    batch_size: int = Field(default=32, ge=1, le=4096)
    workers: int = Field(default=1, ge=1, le=1)


class FalsificationPlanInput(AdapterModel):
    initial_state: dict[str, Any] = Field(default_factory=dict)
    witness_role: WitnessRole | None = None
    counterexample_checker_id: str | None = None
    budget: SearchBudgetInput = Field(default_factory=SearchBudgetInput)


class OperationBudget(AdapterModel):
    wall_seconds: int = Field(default=30, ge=1, le=86_400)


@dataclass(frozen=True, slots=True)
class AppState:
    kernel: JacobianKernel | None
    tenant_router: TenantKernelRouter | None = None


def create_server(  # noqa: C901
    state_dir: str | Path | None = None,
    *,
    install_references: bool = True,
    tool_profile: ToolProfile | str = ToolProfile.FULL,
    tenant_isolation: bool = False,
    allow_anonymous: bool = False,
    token_verifier: Any | None = None,
    auth: Any | None = None,
    capability_adapter_entrypoints: tuple[str, ...] = (),
) -> MCPServer[AppState]:
    """Create a local or tenant-routed adapter over the Jacobian kernel."""

    # Keep ``--help`` and ``--version`` independent of the MCP runtime's
    # heavier imports and shutdown hooks.
    from mcp.server import MCPServer
    from mcp.server.mcpserver import Context

    from jacobian.adapters.mcp.remote import TenantKernelRouter
    from jacobian.kernel import JacobianKernel
    from jacobian.references import reference_catalog

    globals().update(
        {
            "Context": Context,
            "JacobianKernel": JacobianKernel,
        }
    )
    selected_profile = ToolProfile(tool_profile)
    structured_output = selected_profile is ToolProfile.FULL
    configured_root = _configured_root(state_dir)
    kernel = (
        None
        if tenant_isolation
        else JacobianKernel(
            configured_root,
            install_references=install_references,
            capability_adapter_entrypoints=capability_adapter_entrypoints,
        )
    )
    tenant_router = (
        TenantKernelRouter(
            configured_root,
            install_references=install_references,
            allow_anonymous=allow_anonymous,
            capability_adapter_entrypoints=capability_adapter_entrypoints,
        )
        if tenant_isolation
        else None
    )

    @asynccontextmanager
    async def lifespan(_server: MCPServer[AppState]) -> AsyncIterator[AppState]:
        yield AppState(kernel=kernel, tenant_router=tenant_router)

    server: MCPServer[AppState] = MCPServer(
        name="jacobian",
        title="Jacobian Mathematical Workbench",
        description=(
            "Capability-first mathematical tools, research memory, and optional "
            "verification"
        ),
        instructions=SERVER_INSTRUCTIONS,
        version=__version__,
        lifespan=lifespan,
        token_verifier=token_verifier,
        auth=auth,
    )

    @server.tool(
        name="capability.invoke",
        description=(
            "Invoke an installed mathematical capability in the fast EXPLORE or "
            "checker-backed VERIFY lane. Read capability://catalog first."
        ),
        annotations=_tool_annotations(),
        structured_output=structured_output,
    )
    async def capability_invoke(
        capability_id: str,
        payload: dict[str, Any],
        mode: CapabilityMode = CapabilityMode.EXPLORE,
        ctx: Context[AppState, Any] | None = None,
    ) -> CapabilityResult:
        active_kernel = _kernel(ctx)
        return await asyncio.to_thread(
            active_kernel.capabilities.invoke,
            CapabilityRequest(
                capability_id=capability_id,
                mode=mode,
                input=payload,
            ),
        )

    @server.tool(
        name="artifact.put",
        description=(
            "Store schema-validated immutable content and return its address."
        ),
        annotations=_tool_annotations(idempotent=True),
        structured_output=structured_output,
    )
    async def artifact_put(
        schema_uri: str,
        semantics_uri: str,
        payload: dict[str, Any] | list[Any],
        parents: list[str] | None = None,
        summary: str = "",
        ctx: Context[AppState, Any] | None = None,
    ) -> ArtifactPutResult:
        kernel = _kernel(ctx)
        return await asyncio.to_thread(
            kernel.artifacts.put,
            schema_uri=schema_uri,
            semantics_uri=semantics_uri,
            payload=payload,
            parents=_optional_tuple(parents),
            summary=summary,
        )

    @server.tool(
        name="claim.validate",
        description=(
            "Validate claim structure and installed semantic capabilities; "
            "this does not prove correspondence or truth."
        ),
        annotations=_tool_annotations(read_only=True, idempotent=True),
        structured_output=structured_output,
    )
    async def claim_validate(
        claim_uri: str,
        plugin_id: str,
        ctx: Context[AppState, Any] | None = None,
    ) -> ClaimValidationResult:
        kernel = _kernel(ctx)
        return await asyncio.to_thread(
            kernel.claims.validate,
            claim_uri=claim_uri,
            plugin_id=plugin_id,
        )

    @server.tool(
        name="evaluate.batch",
        description=(
            "Evaluate candidates with an installed plugin. Results are always "
            "unverified, even for exact exhaustive evaluation."
        ),
        annotations=_tool_annotations(read_only=True, idempotent=True),
        structured_output=structured_output,
    )
    async def evaluate_batch(
        claim_uri: str,
        candidate_uris: list[str],
        plugin_id: str,
        profile: EvaluationProfile = EvaluationProfile.FAST,
        seed: int = 0,
        budget: EvaluationBudget | None = None,
        ctx: Context[AppState, Any] | None = None,
    ) -> EvaluationBatchResult:
        kernel = _kernel(ctx)
        active_budget = budget or EvaluationBudget()
        result = await asyncio.to_thread(
            kernel.evaluation.evaluate_batch,
            claim_uri=claim_uri,
            candidate_uris=tuple(candidate_uris),
            plugin_id=plugin_id,
            profile=profile,
            seed=seed,
            wall_seconds=active_budget.wall_seconds,
        )
        return EvaluationBatchResult.model_validate(result.model_dump(mode="json"))

    @server.tool(
        name="witness.find",
        description=(
            "Search adversarially for a concrete witness. Found evidence "
            "remains unverified until witness.verify accepts it."
        ),
        annotations=_tool_annotations(),
        structured_output=structured_output,
    )
    async def witness_find(
        claim_uri: str,
        candidate_uri: str,
        plugin_id: str,
        witness_role: WitnessRole = WitnessRole.DEFEATS_CANDIDATE,
        budget: WitnessBudget | None = None,
        ctx: Context[AppState, Any] | None = None,
    ) -> WitnessFindResult:
        kernel = _kernel(ctx)
        active_budget = budget or WitnessBudget()
        result = await asyncio.to_thread(
            kernel.witnesses.find,
            claim_uri=claim_uri,
            candidate_uri=candidate_uri,
            plugin_id=plugin_id,
            witness_role=witness_role,
            wall_seconds=active_budget.wall_seconds,
        )
        return WitnessFindResult.model_validate(result.model_dump(mode="json"))

    @server.tool(
        name="witness.verify",
        description=(
            "Replay a bound witness with an operator-authorized independent checker."
        ),
        annotations=_tool_annotations(idempotent=True),
        structured_output=structured_output,
    )
    async def witness_verify(
        claim_uri: str,
        candidate_uri: str,
        witness_uri: str,
        checker_id: str,
        ctx: Context[AppState, Any] | None = None,
    ) -> ResultEnvelope:
        kernel = _kernel(ctx)
        result = await asyncio.to_thread(
            kernel.verification.verify_witness,
            claim_uri=claim_uri,
            candidate_uri=candidate_uri,
            witness_uri=witness_uri,
            checker_id=checker_id,
        )
        return validate_result_envelope(result)

    @server.tool(
        name="shrink.run",
        description=(
            "Reduce a candidate or witness, accepting steps only after "
            "authorized preservation replay."
        ),
        annotations=_tool_annotations(),
        structured_output=structured_output,
    )
    async def shrink_run(
        target_kind: str,
        target_uri: str,
        claim_uri: str,
        plugin_id: str,
        preservation_checker_id: str,
        reducers: list[str],
        objectives: list[str] | None = None,
        budget: ShrinkBudget | None = None,
        ctx: Context[AppState, Any] | None = None,
    ) -> ShrinkResult:
        kernel = _kernel(ctx)
        active_budget = budget or ShrinkBudget()
        result = await asyncio.to_thread(
            kernel.shrinking.run,
            target_kind=target_kind,
            target_uri=target_uri,
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            preservation_checker_id=preservation_checker_id,
            reducers=tuple(reducers),
            objectives=tuple(objectives or ()),
            evaluation_budget=active_budget.evaluations,
        )
        return ShrinkResult.model_validate(result.model_dump(mode="json"))

    @server.tool(
        name="certificate.verify",
        description=(
            "Replay a self-describing certificate with the uniquely "
            "authorized compatible checker."
        ),
        annotations=_tool_annotations(idempotent=True),
        structured_output=structured_output,
    )
    async def certificate_verify(
        certificate_uri: str,
        ctx: Context[AppState, Any] | None = None,
    ) -> ResultEnvelope:
        kernel = _kernel(ctx)
        result = await asyncio.to_thread(
            kernel.verification.verify_certificate,
            certificate_uri=certificate_uri,
        )
        return validate_result_envelope(result)

    @server.tool(
        name="lean.verify",
        description=(
            "Bind and check one Lean proposition with the pinned kernel. CORE allows "
            "no imports or axioms; MATHLIB uses the pinned repository and an explicit "
            "standard trust-base allowlist."
        ),
        annotations=_tool_annotations(idempotent=True),
        structured_output=structured_output,
    )
    async def lean_verify(
        statement: Annotated[
            str,
            Field(
                min_length=1,
                max_length=2_000,
                description="One exact Lean proposition in the selected environment.",
            ),
        ],
        proof: Annotated[
            str,
            Field(
                min_length=1,
                max_length=20_000,
                description=(
                    "Tactic proof body only; omit the leading `by`. User-supplied "
                    "imports, axioms, sorry, native_decide, and metaprogramming "
                    "are forbidden."
                ),
            ),
        ],
        environment: LeanEnvironment = LeanEnvironment.CORE,
        ctx: Context[AppState, Any] | None = None,
    ) -> LeanVerifyResult:
        kernel = _kernel(ctx)
        service = _lean_service(kernel)
        return await asyncio.to_thread(
            service.verify,
            statement=statement,
            proof=proof,
            environment=environment,
        )

    async def execute_verification_run(
        reference_name: str,
        claim_payload: dict[str, Any],
        candidate_payload: dict[str, Any],
        witness_role: WitnessRole,
        profile: EvaluationProfile = EvaluationProfile.FAST,
        seed: int = 0,
        evaluation_budget: EvaluationBudget | None = None,
        witness_budget: WitnessBudget | None = None,
        ctx: Context[AppState, Any] | None = None,
    ) -> WitnessVerificationWorkflowResult:
        kernel = _kernel(ctx)
        service = _verification_workflow_service(kernel)
        return await asyncio.to_thread(
            _run_verification_workflow,
            service,
            reference_name=reference_name,
            claim_payload=claim_payload,
            candidate_payload=candidate_payload,
            witness_role=witness_role,
            profile=profile,
            seed=seed,
            evaluation_budget=evaluation_budget,
            witness_budget=witness_budget,
        )

    _register_verification_run_tool(
        server,
        profile=selected_profile,
        execute=execute_verification_run,
    )

    @server.tool(
        name="structure.canonicalize",
        description=(
            "Compute an untrusted domain canonical form and symmetry metadata "
            "for search deduplication."
        ),
        annotations=_tool_annotations(idempotent=True),
        structured_output=structured_output,
    )
    async def structure_canonicalize(
        structure_uri: str,
        plugin_id: str,
        budget: OperationBudget | None = None,
        ctx: Context[AppState, Any] | None = None,
    ) -> StructureCanonicalizationResult:
        kernel = _kernel(ctx)
        active_budget = budget or OperationBudget()
        result = await asyncio.to_thread(
            kernel.structures.canonicalize,
            structure_uri=structure_uri,
            plugin_id=plugin_id,
            wall_seconds=active_budget.wall_seconds,
        )
        return StructureCanonicalizationResult.model_validate(
            result.model_dump(mode="json")
        )

    @server.tool(
        name="search.enumerate",
        description=(
            "Launch a persistent bounded candidate-enumeration experiment and "
            "return a handle immediately. Search results remain unverified."
        ),
        annotations=_tool_annotations(),
        structured_output=structured_output,
    )
    async def search_enumerate(
        claim_uri: str,
        plugin_id: str,
        bounds: dict[str, Any],
        quotient_by_isomorphism: bool = False,
        profile: EvaluationProfile = EvaluationProfile.EXACT_CANDIDATE,
        seed: int = 0,
        budget: EnumerationBudgetInput | None = None,
        ctx: Context[AppState, Any] | None = None,
    ) -> ExperimentHandle:
        kernel = _kernel(ctx)
        active_budget = budget or EnumerationBudgetInput()
        request = SearchEnumerateRequest(
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            bounds=bounds,
            quotient_by_isomorphism=quotient_by_isomorphism,
            profile=profile,
            seed=seed,
            budget=EnumerationBudget(
                candidates_max=active_budget.candidates_max,
                wall_seconds=active_budget.wall_seconds,
                page_size=active_budget.page_size,
            ),
        )
        return await asyncio.to_thread(
            kernel.experiments.start_enumeration,
            request,
        )

    @server.tool(
        name="search.run",
        description=(
            "Launch one idempotent, strategy-neutral search experiment. "
            "Proposals and nominations remain unverified."
        ),
        annotations=_tool_annotations(idempotent=True),
        structured_output=structured_output,
    )
    async def search_run(
        idempotency_key: str,
        claim_uri: str,
        plugin_id: str,
        initial_state: dict[str, Any] | None = None,
        profile: EvaluationProfile = EvaluationProfile.EXACT_CANDIDATE,
        seed: int = 0,
        witness_role: WitnessRole | None = None,
        counterexample_checker_id: str | None = None,
        budget: SearchBudgetInput | None = None,
        ctx: Context[AppState, Any] | None = None,
    ) -> ExperimentHandle:
        kernel = _kernel(ctx)
        active_budget = budget or SearchBudgetInput()
        request = SearchRunRequest(
            idempotency_key=idempotency_key,
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            initial_state=initial_state or {},
            profile=profile,
            seed=seed,
            witness_role=witness_role,
            counterexample_checker_id=counterexample_checker_id,
            budget=SearchBudget(
                candidates_max=active_budget.candidates_max,
                iterations_max=active_budget.iterations_max,
                wall_seconds=active_budget.wall_seconds,
                batch_size=active_budget.batch_size,
                workers=active_budget.workers,
            ),
        )
        return await asyncio.to_thread(kernel.search.start, request)

    @server.tool(
        name="experiment.cancel",
        description=(
            "Request cooperative cancellation of a persistent experiment; "
            "already committed artifacts remain immutable."
        ),
        annotations=_tool_annotations(destructive=True, idempotent=True),
        structured_output=structured_output,
    )
    async def experiment_cancel(
        experiment_uri: str,
        ctx: Context[AppState, Any] | None = None,
    ) -> ExperimentControlResult:
        kernel = _kernel(ctx)
        result = await asyncio.to_thread(
            _cancel_experiment,
            kernel,
            experiment_uri,
        )
        return ExperimentControlResult.model_validate(result.model_dump(mode="json"))

    @server.tool(
        name="experiment.pause",
        description="Pause a strategy search at its next checkpoint boundary.",
        annotations=_tool_annotations(idempotent=True),
        structured_output=structured_output,
    )
    async def experiment_pause(
        experiment_uri: str,
        ctx: Context[AppState, Any] | None = None,
    ) -> ExperimentControlResult:
        kernel = _kernel(ctx)
        return await asyncio.to_thread(kernel.search.pause, experiment_uri)

    @server.tool(
        name="experiment.resume",
        description="Resume a paused strategy search from its immutable checkpoint.",
        annotations=_tool_annotations(idempotent=True),
        structured_output=structured_output,
    )
    async def experiment_resume(
        experiment_uri: str,
        ctx: Context[AppState, Any] | None = None,
    ) -> ExperimentControlResult:
        kernel = _kernel(ctx)
        return await asyncio.to_thread(kernel.search.resume, experiment_uri)

    _register_conjecture_tools(
        server,
        structured_output=structured_output,
    )

    @server.tool(
        name="transform.apply",
        description=(
            "Run an untrusted representation transformer and emit an explicit "
            "relation and proof obligation."
        ),
        annotations=_tool_annotations(),
        structured_output=structured_output,
    )
    async def transform_apply(
        source_uri: str,
        plugin_id: str,
        target_schema_uri: str,
        target_semantics_uri: str,
        requested_relation: TransformationRelation,
        budget: OperationBudget | None = None,
        ctx: Context[AppState, Any] | None = None,
    ) -> TransformationApplyResult:
        kernel = _kernel(ctx)
        active_budget = budget or OperationBudget()
        result = await asyncio.to_thread(
            kernel.transformations.apply,
            source_uri=source_uri,
            plugin_id=plugin_id,
            target_schema_uri=target_schema_uri,
            target_semantics_uri=target_semantics_uri,
            requested_relation=requested_relation,
            wall_seconds=active_budget.wall_seconds,
        )
        return TransformationApplyResult.model_validate(result.model_dump(mode="json"))

    @server.tool(
        name="transform.verify",
        description=(
            "Replay a representation relation with the uniquely compatible "
            "operator-authorized independent checker."
        ),
        annotations=_tool_annotations(idempotent=True),
        structured_output=structured_output,
    )
    async def transform_verify(
        transformation_uri: str,
        ctx: Context[AppState, Any] | None = None,
    ) -> ResultEnvelope:
        kernel = _kernel(ctx)
        result = await asyncio.to_thread(
            kernel.verification.verify_transformation,
            transformation_uri=transformation_uri,
        )
        return validate_result_envelope(result)

    @server.tool(
        name="polytope.separate",
        description=(
            "Generate exact finite convex-hull membership evidence or a "
            "strict rational separator. Evidence remains unverified until replay."
        ),
        annotations=_tool_annotations(),
        structured_output=structured_output,
    )
    async def polytope_separate(
        point_uri: str,
        generator_set_uri: str,
        projection: list[int] | None = None,
        budget: OperationBudget | None = None,
        ctx: Context[AppState, Any] | None = None,
    ) -> PolytopeSeparateResult:
        kernel = _kernel(ctx)
        active_budget = budget or OperationBudget()
        result = await asyncio.to_thread(
            kernel.polytope.separate,
            PolytopeSeparateRequest(
                point_uri=point_uri,
                generator_set_uri=generator_set_uri,
                projection=(tuple(projection) if projection is not None else None),
                wall_seconds=active_budget.wall_seconds,
            ),
        )
        return PolytopeSeparateResult.model_validate(result.model_dump(mode="json"))

    @server.resource(
        "artifact://sha256/{digest}",
        name="artifact",
        description="Read an immutable artifact manifest and payload.",
        mime_type="application/json",
    )
    async def artifact_resource(
        digest: str,
    ) -> str:
        active_kernel = _resource_kernel(kernel, tenant_router)
        artifact = await asyncio.to_thread(
            active_kernel.store.get,
            f"artifact://sha256/{digest}",
        )
        return json.dumps(
            {
                "artifact_uri": artifact.artifact_uri,
                "manifest": artifact.manifest.model_dump(mode="json"),
                "payload": artifact.payload,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    @server.resource(
        "capability://catalog",
        name="capability-catalog",
        description=(
            "Installed model-facing operations, supported lanes, and compact schemas."
        ),
        mime_type="application/json",
    )
    async def capability_catalog_resource() -> str:
        active_kernel = _resource_kernel(kernel, tenant_router)
        return json.dumps(
            active_kernel.capabilities.catalog().model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )

    @server.resource(
        "reference://catalog",
        name="reference-catalog",
        description="Installed reference plugin, schema, and checker IDs.",
        mime_type="application/json",
    )
    async def reference_catalog_resource() -> str:
        active_kernel = _resource_kernel(kernel, tenant_router)
        return json.dumps(
            reference_catalog(
                active_kernel.references,
                polytope=active_kernel.polytope,
                polytope_checkers=active_kernel.polytope_checkers,
                lean=active_kernel.lean_checkers,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )

    @server.resource(
        "reference://domain/{name}",
        name="reference-domain-agent-contract",
        description=(
            "Read one bundled domain's exact identifiers and model-facing schemas."
        ),
        mime_type="application/json",
    )
    async def reference_domain_resource(
        name: str,
    ) -> str:
        active_kernel = _resource_kernel(kernel, tenant_router)
        catalog = reference_catalog(
            active_kernel.references,
            polytope=active_kernel.polytope,
            polytope_checkers=active_kernel.polytope_checkers,
            lean=active_kernel.lean_checkers,
        )
        return json.dumps(
            _reference_domain_contract(active_kernel, name, catalog),
            ensure_ascii=False,
            sort_keys=True,
        )

    @server.resource(
        "experiment://{experiment_id}",
        name="experiment",
        description="Read the latest durable experiment snapshot.",
        mime_type="application/json",
    )
    async def experiment_resource(
        experiment_id: str,
    ) -> str:
        active_kernel = _resource_kernel(kernel, tenant_router)
        snapshot = await asyncio.to_thread(
            _inspect_experiment,
            active_kernel,
            f"experiment://{experiment_id}",
        )
        return json.dumps(
            snapshot.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )

    @server.resource(
        "experiment://{experiment_id}/accounting",
        name="experiment-accounting",
        description="Read durable enumeration accounting and assurance labels.",
        mime_type="application/json",
    )
    async def experiment_accounting_resource(
        experiment_id: str,
    ) -> str:
        active_kernel = _resource_kernel(kernel, tenant_router)
        snapshot = await asyncio.to_thread(
            _inspect_experiment,
            active_kernel,
            f"experiment://{experiment_id}",
        )
        coverage = getattr(snapshot, "coverage", None)
        return json.dumps(
            {
                "experiment_uri": snapshot.experiment_uri,
                "state": snapshot.state.value,
                "stop_reason": (
                    snapshot.stop_reason.value
                    if snapshot.stop_reason is not None
                    else None
                ),
                "coverage": coverage.value if coverage is not None else None,
                "verification": snapshot.verification.value,
                "accounting": snapshot.accounting.model_dump(mode="json"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    @server.resource(
        "experiment://{experiment_id}/scope",
        name="experiment-scope",
        description="Read the current enumeration scope artifact, when available.",
        mime_type="application/json",
    )
    async def experiment_scope_resource(
        experiment_id: str,
    ) -> str:
        active_kernel = _resource_kernel(kernel, tenant_router)
        snapshot = await asyncio.to_thread(
            _inspect_experiment,
            active_kernel,
            f"experiment://{experiment_id}",
        )
        return await asyncio.to_thread(
            _experiment_scope_content,
            active_kernel,
            snapshot,
        )

    @server.resource(
        "experiment://{experiment_id}/archive",
        name="experiment-archive",
        description="Read the immutable archive manifest and page handles.",
        mime_type="application/json",
    )
    async def experiment_archive_resource(
        experiment_id: str,
    ) -> str:
        active_kernel = _resource_kernel(kernel, tenant_router)
        snapshot = await asyncio.to_thread(
            _inspect_experiment,
            active_kernel,
            f"experiment://{experiment_id}",
        )
        if snapshot.archive_uri is None:
            return json.dumps(
                {
                    "experiment_uri": snapshot.experiment_uri,
                    "archive_uri": None,
                    "page_uris": list(snapshot.archive_page_uris),
                },
                sort_keys=True,
            )
        archive = await asyncio.to_thread(
            active_kernel.store.get,
            snapshot.archive_uri,
        )
        return json.dumps(
            {
                "experiment_uri": snapshot.experiment_uri,
                "archive_uri": archive.artifact_uri,
                "manifest": archive.manifest.model_dump(mode="json"),
                "payload": archive.payload,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    _project_tool_profile(server, selected_profile)

    return server


def _register_conjecture_tools(
    server: MCPServer[AppState],
    *,
    structured_output: bool,
) -> None:
    @server.tool(
        name="conjecture.repair",
        description=(
            "Propose unverified claim repairs from an independently verified "
            "counterexample and optionally run the ordinary falsification loop."
        ),
        annotations=_tool_annotations(),
        structured_output=structured_output,
    )
    async def conjecture_repair(
        source_claim_uri: str,
        verification_record_uri: str,
        plugin_id: str,
        constraints: dict[str, Any] | None = None,
        evidence_uris: list[str] | None = None,
        seed: int = 0,
        max_hypotheses: int = 8,
        wall_seconds: int = 60,
        falsification: FalsificationPlanInput | None = None,
        ctx: Context[AppState, Any] | None = None,
    ) -> ConjectureWorkflowResult:
        kernel = _kernel(ctx)
        return await asyncio.to_thread(
            kernel.conjectures.run,
            ConjectureWorkflowRequest(
                operation=ConjectureOperation.REPAIR,
                plugin_id=plugin_id,
                source_uri=source_claim_uri,
                verification_record_uri=verification_record_uri,
                constraints=constraints or {},
                evidence_uris=tuple(evidence_uris or ()),
                seed=seed,
                max_hypotheses=max_hypotheses,
                wall_seconds=wall_seconds,
                falsification=_falsification_plan(falsification),
            ),
        )

    @server.tool(
        name="conjecture.generate",
        description=(
            "Generate deduplicated unverified formal hypotheses and optionally "
            "run the ordinary falsification loop."
        ),
        annotations=_tool_annotations(),
        structured_output=structured_output,
    )
    async def conjecture_generate(
        plugin_id: str,
        source_uri: str | None = None,
        constraints: dict[str, Any] | None = None,
        reference_claim_uris: list[str] | None = None,
        evidence_uris: list[str] | None = None,
        seed: int = 0,
        max_hypotheses: int = 8,
        wall_seconds: int = 60,
        falsification: FalsificationPlanInput | None = None,
        ctx: Context[AppState, Any] | None = None,
    ) -> ConjectureWorkflowResult:
        kernel = _kernel(ctx)
        return await asyncio.to_thread(
            kernel.conjectures.run,
            ConjectureWorkflowRequest(
                operation=ConjectureOperation.GENERATE,
                plugin_id=plugin_id,
                source_uri=source_uri,
                constraints=constraints or {},
                reference_claim_uris=tuple(reference_claim_uris or ()),
                evidence_uris=tuple(evidence_uris or ()),
                seed=seed,
                max_hypotheses=max_hypotheses,
                wall_seconds=wall_seconds,
                falsification=_falsification_plan(falsification),
            ),
        )

    @server.tool(
        name="parameter.generalize",
        description=(
            "Propose an exact parameter-region hypothesis from a verified "
            "construction; sampled and proposed regions remain unverified."
        ),
        annotations=_tool_annotations(),
        structured_output=structured_output,
    )
    async def parameter_generalize(
        source_uri: str,
        verification_record_uri: str,
        plugin_id: str,
        constraints: dict[str, Any] | None = None,
        evidence_uris: list[str] | None = None,
        seed: int = 0,
        max_hypotheses: int = 8,
        wall_seconds: int = 60,
        falsification: FalsificationPlanInput | None = None,
        ctx: Context[AppState, Any] | None = None,
    ) -> ConjectureWorkflowResult:
        kernel = _kernel(ctx)
        return await asyncio.to_thread(
            kernel.conjectures.run,
            ConjectureWorkflowRequest(
                operation=ConjectureOperation.PARAMETER_GENERALIZE,
                plugin_id=plugin_id,
                source_uri=source_uri,
                verification_record_uri=verification_record_uri,
                constraints=constraints or {},
                evidence_uris=tuple(evidence_uris or ()),
                seed=seed,
                max_hypotheses=max_hypotheses,
                wall_seconds=wall_seconds,
                falsification=_falsification_plan(falsification),
            ),
        )

    @server.tool(
        name="parameter.region.promote",
        description=(
            "Replay an authorized certificate bound to an immutable parameter "
            "region before labeling it verified sufficient or necessary."
        ),
        annotations=_tool_annotations(read_only=True, idempotent=True),
        structured_output=structured_output,
    )
    async def parameter_region_promote(
        subject_uri: str,
        verification_record_uri: str,
        ctx: Context[AppState, Any] | None = None,
    ) -> ParameterRegion:
        kernel = _kernel(ctx)
        return await asyncio.to_thread(
            kernel.conjectures.promote_parameter_region,
            subject_uri=subject_uri,
            verification_record_uri=verification_record_uri,
        )


def _inspect_experiment(
    kernel: JacobianKernel,
    experiment_uri: str,
) -> Any:
    from jacobian.experiments import ExperimentNotFoundError

    try:
        return kernel.experiments.inspect(experiment_uri)
    except ExperimentNotFoundError:
        return kernel.search.inspect(experiment_uri)


def _cancel_experiment(
    kernel: JacobianKernel,
    experiment_uri: str,
) -> Any:
    from jacobian.experiments import ExperimentNotFoundError

    try:
        return kernel.experiments.cancel(experiment_uri)
    except ExperimentNotFoundError:
        return kernel.search.cancel(experiment_uri)


def _falsification_plan(
    selected: FalsificationPlanInput | None,
) -> FalsificationPlan | None:
    if selected is None:
        return None
    return FalsificationPlan(
        initial_state=selected.initial_state,
        witness_role=selected.witness_role,
        counterexample_checker_id=selected.counterexample_checker_id,
        budget=SearchBudget(
            candidates_max=selected.budget.candidates_max,
            iterations_max=selected.budget.iterations_max,
            wall_seconds=selected.budget.wall_seconds,
            batch_size=selected.budget.batch_size,
            workers=selected.budget.workers,
        ),
    )


def _kernel(ctx: Context[AppState, Any] | None) -> JacobianKernel:
    if ctx is None:
        raise RuntimeError("MCP request context is unavailable")
    state = ctx.request_context.lifespan_context
    if not isinstance(state, AppState):
        raise RuntimeError("MCP lifespan state is invalid")
    if state.tenant_router is not None:
        from mcp.server.auth.middleware.auth_context import get_access_token

        access_token = get_access_token()
        subject = access_token.subject if access_token is not None else None
        return state.tenant_router.kernel_for(subject)
    if state.kernel is None:
        raise RuntimeError("MCP lifespan has no kernel")
    return state.kernel


def _resource_kernel(
    kernel: JacobianKernel | None,
    tenant_router: TenantKernelRouter | None,
) -> JacobianKernel:
    """Route resources through the same auth context as tools.

    MCP 2.0.0b2 does not inject ``Context`` into static resources, but its HTTP
    authentication middleware still scopes the access token with a contextvar.
    """

    if tenant_router is not None:
        from mcp.server.auth.middleware.auth_context import get_access_token

        access_token = get_access_token()
        subject = access_token.subject if access_token is not None else None
        return tenant_router.kernel_for(subject)
    if kernel is None:
        raise RuntimeError("MCP lifespan has no resource kernel")
    return kernel


def _configured_root(state_dir: str | Path | None) -> Path:
    if state_dir is not None:
        return Path(state_dir)
    return Path(os.environ.get("JACOBIAN_STATE_DIR", ".jacobian"))


def _optional_tuple(values: list[str] | None) -> tuple[str, ...]:
    return tuple(values or ())


def _experiment_scope_content(kernel: JacobianKernel, snapshot: Any) -> str:
    scope_uri = getattr(snapshot, "scope_uri", None)
    if scope_uri is None:
        return json.dumps(
            {
                "experiment_uri": snapshot.experiment_uri,
                "scope_uri": None,
            },
            sort_keys=True,
        )
    scope = kernel.store.get(scope_uri)
    return json.dumps(
        {
            "experiment_uri": snapshot.experiment_uri,
            "scope_uri": scope.artifact_uri,
            "manifest": scope.manifest.model_dump(mode="json"),
            "payload": scope.payload,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _lean_service(kernel: JacobianKernel) -> Any:
    if kernel.lean is None:
        raise RuntimeError("the bundled Lean checker is not installed")
    return kernel.lean


def _verification_workflow_service(kernel: JacobianKernel) -> Any:
    if kernel.verification_workflows is None:
        raise RuntimeError("bundled verification workflows are not installed")
    return kernel.verification_workflows


def _run_verification_workflow(
    service: VerificationWorkflowService,
    *,
    reference_name: str,
    claim_payload: dict[str, Any],
    candidate_payload: dict[str, Any],
    witness_role: WitnessRole,
    profile: EvaluationProfile,
    seed: int,
    evaluation_budget: EvaluationBudget | None,
    witness_budget: WitnessBudget | None,
) -> WitnessVerificationWorkflowResult:
    return service.verify_witness(
        reference_name=reference_name,
        claim_payload=claim_payload,
        candidate_payload=candidate_payload,
        witness_role=witness_role,
        profile=profile,
        seed=seed,
        evaluation_wall_seconds=(evaluation_budget or EvaluationBudget()).wall_seconds,
        witness_wall_seconds=(witness_budget or WitnessBudget()).wall_seconds,
    )


def _compact_result(result: ResultEnvelope) -> dict[str, Any]:
    return {
        "execution_status": result.execution.status.value,
        "input_status": result.input.status.value,
        "input_errors": list(result.input.errors),
        "conclusion": result.conclusion.value,
        "verification": result.assurance.verification.value,
    }


def _compact_workflow_result(
    result: WitnessVerificationWorkflowResult,
) -> dict[str, Any]:
    evaluation_result = (
        result.evaluation.items[0].result
        if result.evaluation is not None and result.evaluation.items
        else None
    )
    witness_search = result.witness_search
    verification = result.verification
    return {
        "schema_version": result.schema_version,
        "claim_uri": result.claim_uri,
        "candidate_uri": result.candidate_uri,
        "claim_validation": {
            "valid": result.claim_validation.valid,
            "input_status": result.claim_validation.input.status.value,
            "errors": list(result.claim_validation.input.errors),
        },
        "evaluation": (
            _compact_result(evaluation_result)
            if evaluation_result is not None
            else None
        ),
        "witness_search": (
            {
                **_compact_result(witness_search.result),
                "status": witness_search.status.value,
                "evidence_uri": (
                    witness_search.witness_uri or witness_search.certificate_uri
                ),
            }
            if witness_search is not None
            else None
        ),
        "verification": (
            {
                **_compact_result(verification),
                "evidence_uri": (
                    verification.evidence_uris[0]
                    if verification.evidence_uris
                    else None
                ),
                "verification_record_uri": verification.verification_record_uri,
                "checker_id": verification.assurance.checker_id,
            }
            if verification is not None
            else None
        ),
    }


def _register_verification_run_tool(
    server: MCPServer[AppState],
    *,
    profile: ToolProfile,
    execute: Any,
) -> None:
    description = (
        "Preferred bundled-domain witness workflow: store a claim and candidate, "
        "validate, evaluate, search, and independently verify discovered evidence. "
        "Intermediate evaluation and search stages remain UNVERIFIED."
    )
    if profile is ToolProfile.FULL:

        @server.tool(
            name="verification.run",
            description=description,
            annotations=_tool_annotations(),
            structured_output=True,
        )
        async def verification_run_full(
            reference_name: str,
            claim_payload: dict[str, Any],
            candidate_payload: dict[str, Any],
            witness_role: WitnessRole,
            profile: EvaluationProfile = EvaluationProfile.FAST,
            seed: int = 0,
            evaluation_budget: EvaluationBudget | None = None,
            witness_budget: WitnessBudget | None = None,
            ctx: Context[AppState, Any] | None = None,
        ) -> WitnessVerificationWorkflowResult:
            return cast(
                WitnessVerificationWorkflowResult,
                await execute(
                    reference_name=reference_name,
                    claim_payload=claim_payload,
                    candidate_payload=candidate_payload,
                    witness_role=witness_role,
                    profile=profile,
                    seed=seed,
                    evaluation_budget=evaluation_budget,
                    witness_budget=witness_budget,
                    ctx=ctx,
                ),
            )

    else:

        @server.tool(
            name="verification.run",
            description=description,
            annotations=_tool_annotations(),
            structured_output=False,
        )
        async def verification_run_compact(
            reference_name: str,
            claim_payload: dict[str, Any],
            candidate_payload: dict[str, Any],
            witness_role: WitnessRole,
            profile: EvaluationProfile = EvaluationProfile.FAST,
            seed: int = 0,
            evaluation_budget: EvaluationBudget | None = None,
            witness_budget: WitnessBudget | None = None,
            ctx: Context[AppState, Any] | None = None,
        ) -> dict[str, Any]:
            result = await execute(
                reference_name=reference_name,
                claim_payload=claim_payload,
                candidate_payload=candidate_payload,
                witness_role=witness_role,
                profile=profile,
                seed=seed,
                evaluation_budget=evaluation_budget,
                witness_budget=witness_budget,
                ctx=ctx,
            )
            return _compact_workflow_result(result)


def _compact_schema(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _compact_schema(item)
            for key, item in value.items()
            if key not in {"$schema", "default", "description", "title"}
        }
    if isinstance(value, list):
        return [_compact_schema(item) for item in value]
    return value


def _predicate_parameter_contract(claim_schema: dict[str, Any]) -> dict[str, Any]:
    try:
        predicate_definition = claim_schema["$defs"]["PredicateSpec"]
        names = predicate_definition["properties"]["name"]["enum"]
        rules = claim_schema["allOf"]
        parameters = {
            rule["if"]["properties"]["predicate"]["properties"]["name"]["const"]: (
                rule["then"]["properties"]["predicate"]["properties"]["parameters"]
            )
            for rule in rules
        }
    except (KeyError, TypeError) as exc:
        raise ValueError("claim schema has no compact predicate projection") from exc
    if (
        not isinstance(names, list)
        or not all(isinstance(name, str) for name in names)
        or set(names) != set(parameters)
    ):
        raise ValueError("claim schema predicate projection is incomplete")
    return {name: _compact_schema(parameters[name]) for name in names}


def _reference_domain_contract(
    kernel: JacobianKernel,
    name: str,
    catalog: dict[str, Any],
) -> dict[str, Any]:
    entry = catalog.get(name)
    if entry is None:
        raise ValueError(f"unknown bundled reference domain: {name}")

    def definition(uri: str) -> Any:
        payload = kernel.store.get(uri).payload
        if not isinstance(payload, dict) or "definition" not in payload:
            raise ValueError(f"reference descriptor has no definition: {uri}")
        return payload["definition"]

    if name in kernel.references:
        reference = kernel.references[name]
        claim_schema = definition(reference.claim_schema_uri)
        candidate_schema = definition(reference.candidate_schema_uri)
        if not isinstance(claim_schema, dict) or not isinstance(candidate_schema, dict):
            raise ValueError("reference schemas must be JSON objects")
        available_capabilities = set(entry["available_capabilities"])
        workflow_capabilities = ["Evaluator", "WitnessOracle"]
        if not set(workflow_capabilities).issubset(available_capabilities):
            raise ValueError("reference does not support the verification workflow")
        return {
            "name": name,
            "identity": {
                "domain_id": reference.domain_id,
                "domain_version": reference.domain_version,
                "semantics_uri": reference.semantics_uri,
            },
            "semantics": definition(reference.semantics_uri),
            "claim_contract": {
                "base": {
                    "claim_schema_version": "1",
                    "domain_id": reference.domain_id,
                    "domain_version": reference.domain_version,
                    "semantics_uri": reference.semantics_uri,
                    "quantifiers": [],
                    "bounds": {},
                    "required_capabilities": workflow_capabilities,
                    "correspondence_status": "UNREVIEWED",
                },
                "predicates": _predicate_parameter_contract(claim_schema),
                "instruction": (
                    "copy base and add predicate={name, parameters} using exactly "
                    "one declared predicate"
                ),
            },
            "candidate_schema": _compact_schema(candidate_schema),
            "workflow": {
                "assurance_rule": (
                    "Evaluation and witness search are UNVERIFIED. Only an "
                    "authorized compatible checker may return VERIFIED."
                ),
                "witness": [
                    "call capability.invoke with reference.solve, the predicate, "
                    "candidate, and witness role",
                    "use EXPLORE for candidates or VERIFY for a durable conclusion",
                    "advanced clients may call verification.run with a full claim",
                ],
            },
        }
    if name == "lean4" and kernel.lean_checkers:
        return {
            "name": name,
            "runtime": {
                "lean_version": entry["lean_version"],
                "lean_commit": entry["lean_commit"],
                "profiles": {
                    environment.value: {
                        "semantics_uri": installation.semantics_uri,
                        "import_name": installation.import_name,
                        "mathlib_commit": installation.mathlib_commit,
                        "allowed_axioms": installation.allowed_axioms,
                        "checker_timeout_seconds": (
                            installation.checker_timeout_seconds
                        ),
                    }
                    for environment, installation in sorted(
                        kernel.lean_checkers.items(),
                        key=lambda item: item[0].value,
                    )
                },
            },
            "semantics": {
                environment.value: definition(installation.semantics_uri)
                for environment, installation in sorted(
                    kernel.lean_checkers.items(),
                    key=lambda item: item[0].value,
                )
            },
            "workflow": {
                "assurance_rule": (
                    "Only a pinned Lean kernel acceptance with the exact statement, "
                    "proof source, selected environment, declared trust base, and "
                    "durable certificate is VERIFIED."
                ),
                "certificate": [
                    "choose CORE or MATHLIB from the declared profiles",
                    "call lean.verify with one proposition, environment, and a proof "
                    "body that omits the leading `by`",
                    "retain the returned claim, candidate, certificate, and "
                    "verification-record URIs",
                ],
            },
        }
    raise ValueError(f"reference domain has no agent contract: {name}")


def _project_tool_profile(
    server: MCPServer[AppState],
    profile: ToolProfile,
) -> None:
    if profile is ToolProfile.VERIFICATION:
        for tool_name in sorted(CAPABILITY_TOOL_NAMES):
            server.remove_tool(tool_name)
        for tool_name in sorted(NON_VERIFICATION_TOOL_NAMES):
            server.remove_tool(tool_name)
    elif profile is ToolProfile.CAPABILITIES:
        for tool_name in sorted(VERIFICATION_TOOL_NAMES | NON_VERIFICATION_TOOL_NAMES):
            server.remove_tool(tool_name)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="jacobian-mcp",
        description="Run the Jacobian MCP server locally or over remote HTTP.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--tool-profile",
        choices=tuple(profile.value for profile in ToolProfile),
        default=ToolProfile.CAPABILITIES.value,
        help="project the canonical tool registry for a specific host workflow",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http", "sse"),
        default="stdio",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        help="state root; defaults to JACOBIAN_STATE_DIR or .jacobian",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--path", default="/mcp")
    parser.add_argument(
        "--stateless-http",
        action="store_true",
        help="use stateless Streamable HTTP sessions",
    )
    parser.add_argument(
        "--auth-tokens-file",
        type=Path,
        help="JSON secret mapping opaque bearer tokens to tenant IDs",
    )
    parser.add_argument(
        "--public-base-url",
        help="public issuer/resource base URL advertised to remote clients",
    )
    parser.add_argument(
        "--allow-anonymous",
        action="store_true",
        help="development only: permit unauthenticated remote requests",
    )
    parser.add_argument(
        "--capability-adapter",
        action="append",
        default=[],
        help="operator-approved package.module:factory entrypoint; repeatable",
    )
    args = parser.parse_args()
    args.path = args.path if args.path.startswith("/") else f"/{args.path}"
    if args.transport == "stdio":
        if args.auth_tokens_file is not None or args.allow_anonymous:
            parser.error("remote authentication options cannot be used with stdio")
        create_server(
            state_dir=args.state_dir,
            tool_profile=args.tool_profile,
            capability_adapter_entrypoints=tuple(args.capability_adapter),
        ).run("stdio")
        return

    if args.auth_tokens_file is None and not args.allow_anonymous:
        parser.error(
            "remote transports require --auth-tokens-file or explicit --allow-anonymous"
        )
    token_verifier = None
    auth = None
    if args.auth_tokens_file is not None:
        from mcp.server.auth.settings import AuthSettings

        from jacobian.adapters.mcp.remote import (
            StaticTokenVerifier,
            load_static_token_file,
        )

        public_base_url = str(
            args.public_base_url or f"http://{args.host}:{args.port}"
        ).rstrip("/")
        token_verifier = StaticTokenVerifier(
            load_static_token_file(args.auth_tokens_file)
        )
        auth = AuthSettings(
            issuer_url=AnyHttpUrl(public_base_url),
            resource_server_url=AnyHttpUrl(f"{public_base_url}{args.path}"),
            required_scopes=["jacobian:use"],
        )
    server = create_server(
        state_dir=args.state_dir,
        tool_profile=args.tool_profile,
        tenant_isolation=True,
        allow_anonymous=args.allow_anonymous,
        token_verifier=token_verifier,
        auth=auth,
        capability_adapter_entrypoints=tuple(args.capability_adapter),
    )
    if args.transport == "streamable-http":
        server.run(
            "streamable-http",
            host=args.host,
            port=args.port,
            streamable_http_path=args.path,
            stateless_http=args.stateless_http,
        )
    else:
        server.run(
            "sse",
            host=args.host,
            port=args.port,
            sse_path=args.path,
            message_path="/messages/",
        )


if __name__ == "__main__":
    main()
