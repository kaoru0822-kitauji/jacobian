"""Thin MCP 2.0.0b2 adapter over the tested Python kernel."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from jacobian import __version__
from jacobian.contracts.artifacts import ArtifactPutResult
from jacobian.contracts.claims import ClaimValidationResult
from jacobian.contracts.discovery import (
    EnumerationBudget,
    ExperimentCancelResult,
    ExperimentHandle,
    SearchEnumerateRequest,
    StructureCanonicalizationResult,
)
from jacobian.contracts.evaluation import (
    EvaluationBatchResult,
    EvaluationProfile,
)
from jacobian.contracts.polytope import (
    PolytopeSeparateRequest,
    PolytopeSeparateResult,
)
from jacobian.contracts.results import (
    ResultEnvelope,
    validate_result_envelope,
)
from jacobian.contracts.shrinking import ShrinkResult
from jacobian.contracts.transformations import TransformationApplyResult
from jacobian.contracts.witness_search import WitnessFindResult

if TYPE_CHECKING:
    from mcp.server import MCPServer
    from mcp.server.mcpserver import Context

    from jacobian.kernel import JacobianKernel


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


class OperationBudget(AdapterModel):
    wall_seconds: int = Field(default=30, ge=1, le=86_400)


@dataclass(frozen=True, slots=True)
class AppState:
    kernel: JacobianKernel


def create_server(
    state_dir: str | Path | None = None,
    *,
    install_references: bool = True,
) -> MCPServer[AppState]:
    """Create the thin MCP adapter over one local Jacobian kernel."""

    # Keep ``--help`` and ``--version`` independent of the MCP runtime's
    # heavier imports and shutdown hooks.
    from mcp.server import MCPServer
    from mcp.server.mcpserver import Context

    from jacobian.kernel import JacobianKernel
    from jacobian.references import reference_catalog

    globals().update(
        {
            "Context": Context,
            "JacobianKernel": JacobianKernel,
        }
    )
    configured_root = Path(
        state_dir
        if state_dir is not None
        else os.environ.get("JACOBIAN_STATE_DIR", ".jacobian")
    )
    kernel = JacobianKernel(
        configured_root,
        install_references=install_references,
    )

    @asynccontextmanager
    async def lifespan(_server: MCPServer[AppState]) -> AsyncIterator[AppState]:
        yield AppState(kernel=kernel)

    server: MCPServer[AppState] = MCPServer(
        name="jacobian",
        title="Jacobian Research Kernel",
        description=("Verifier-centric tools for bounded executable mathematics"),
        version=__version__,
        lifespan=lifespan,
    )

    @server.tool(
        name="artifact.put",
        description=(
            "Store schema-validated immutable content and return its address."
        ),
        structured_output=True,
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
            parents=tuple(parents or ()),
            summary=summary,
        )

    @server.tool(
        name="claim.validate",
        description=(
            "Validate claim structure and installed semantic capabilities; "
            "this does not prove correspondence or truth."
        ),
        structured_output=True,
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
        structured_output=True,
    )
    async def evaluate_batch(
        claim_uri: str,
        candidate_uris: list[str],
        plugin_id: str,
        profile: str = "FAST",
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
            profile=EvaluationProfile(profile),
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
        structured_output=True,
    )
    async def witness_find(
        claim_uri: str,
        candidate_uri: str,
        plugin_id: str,
        witness_role: str = "DEFEATS_CANDIDATE",
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
        structured_output=True,
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
        structured_output=True,
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
        structured_output=True,
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
        name="structure.canonicalize",
        description=(
            "Compute an untrusted domain canonical form and symmetry metadata "
            "for search deduplication."
        ),
        structured_output=True,
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
        structured_output=True,
    )
    async def search_enumerate(
        claim_uri: str,
        plugin_id: str,
        bounds: dict[str, Any],
        quotient_by_isomorphism: bool = False,
        profile: str = "EXACT_CANDIDATE",
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
            profile=EvaluationProfile(profile),
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
        name="experiment.cancel",
        description=(
            "Request cooperative cancellation of a persistent experiment; "
            "already committed artifacts remain immutable."
        ),
        structured_output=True,
    )
    async def experiment_cancel(
        experiment_uri: str,
        ctx: Context[AppState, Any] | None = None,
    ) -> ExperimentCancelResult:
        kernel = _kernel(ctx)
        return await asyncio.to_thread(
            kernel.experiments.cancel,
            experiment_uri,
        )

    @server.tool(
        name="transform.apply",
        description=(
            "Run an untrusted representation transformer and emit an explicit "
            "relation and proof obligation."
        ),
        structured_output=True,
    )
    async def transform_apply(
        source_uri: str,
        plugin_id: str,
        target_schema_uri: str,
        target_semantics_uri: str,
        requested_relation: str,
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
        structured_output=True,
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
        structured_output=True,
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
        artifact = await asyncio.to_thread(
            kernel.store.get,
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
        "reference://catalog",
        name="reference-catalog",
        description="Installed reference plugin, schema, and checker IDs.",
        mime_type="application/json",
    )
    async def reference_catalog_resource() -> str:
        return json.dumps(
            reference_catalog(
                kernel.references,
                polytope=kernel.polytope,
                polytope_checkers=kernel.polytope_checkers,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )

    @server.resource(
        "experiment://{experiment_id}",
        name="experiment",
        description="Read the latest durable experiment snapshot.",
        mime_type="application/json",
    )
    async def experiment_resource(experiment_id: str) -> str:
        snapshot = await asyncio.to_thread(
            kernel.experiments.inspect,
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
    async def experiment_accounting_resource(experiment_id: str) -> str:
        snapshot = await asyncio.to_thread(
            kernel.experiments.inspect,
            f"experiment://{experiment_id}",
        )
        return json.dumps(
            {
                "experiment_uri": snapshot.experiment_uri,
                "state": snapshot.state.value,
                "stop_reason": (
                    snapshot.stop_reason.value
                    if snapshot.stop_reason is not None
                    else None
                ),
                "coverage": snapshot.coverage.value,
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
    async def experiment_scope_resource(experiment_id: str) -> str:
        snapshot = await asyncio.to_thread(
            kernel.experiments.inspect,
            f"experiment://{experiment_id}",
        )
        if snapshot.scope_uri is None:
            return json.dumps(
                {
                    "experiment_uri": snapshot.experiment_uri,
                    "scope_uri": None,
                },
                sort_keys=True,
            )
        scope = await asyncio.to_thread(kernel.store.get, snapshot.scope_uri)
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

    @server.resource(
        "experiment://{experiment_id}/archive",
        name="experiment-archive",
        description="Read the immutable archive manifest and page handles.",
        mime_type="application/json",
    )
    async def experiment_archive_resource(experiment_id: str) -> str:
        snapshot = await asyncio.to_thread(
            kernel.experiments.inspect,
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
        archive = await asyncio.to_thread(kernel.store.get, snapshot.archive_uri)
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

    return server


def _kernel(ctx: Context[AppState, Any] | None) -> JacobianKernel:
    if ctx is None:
        raise RuntimeError("MCP request context is unavailable")
    state = ctx.request_context.lifespan_context
    if not isinstance(state, AppState):
        raise RuntimeError("MCP lifespan state is invalid")
    return state.kernel


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="jacobian-mcp",
        description="Run the Jacobian MCP server over stdio.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.parse_args()
    create_server().run("stdio")


if __name__ == "__main__":
    main()
