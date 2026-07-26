"""Thin MCP 2.0.0b2 adapter over the tested Python kernel."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from mcp.server.mcpserver.exceptions import ToolError
from mcp.shared.exceptions import MCPError
from mcp_types import ToolAnnotations
from pydantic import AnyHttpUrl, Field, StrictInt

from jacobian import __version__
from jacobian.contracts.capabilities import (
    CapabilityMode,
    CapabilityRequest,
    CapabilityResult,
)
from jacobian.contracts.workspaces import (
    WorkspaceAttemptDraft,
    WorkspaceBranchId,
    WorkspaceCardId,
    WorkspaceFindingDraft,
    WorkspaceFocusDraft,
    WorkspaceId,
    WorkspaceIdempotencyKey,
    WorkspaceMarkDraft,
    WorkspaceOpenRequest,
    WorkspaceOpenResult,
    WorkspaceQueryRequest,
    WorkspaceQueryResult,
    WorkspaceQueryView,
    WorkspaceRevisionId,
    WorkspaceScratchDraft,
    WorkspaceTag,
    WorkspaceWriteRequest,
    WorkspaceWriteResult,
)

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp.server import MCPServer
    from mcp.server.mcpserver import Context

    from jacobian.adapters.mcp.remote import TenantKernelRouter
    from jacobian.kernel import JacobianKernel


SERVER_INSTRUCTIONS = (
    "Call capability.describe before the first invocation of an unfamiliar "
    "capability passed to capability.invoke; do not guess payload fields. Direct "
    "workspace.* tools publish their input shape and enforce documented cross-field "
    "invariants without capability discovery. Use EXPLORE for low-friction search and "
    "VERIFY only when a durable checked conclusion is needed. Retrieved memory, "
    "search, evaluation, generated evidence, workspace entries, and lifecycle marks "
    "are not proof. Only assurance level VERIFIED with a local verification record is "
    "verified. Writing, retrieving, closing, retracting, superseding, or pinning a "
    "workspace entry never promotes mathematical assurance. Operational completion, "
    "failure to find a witness, and exhausted or bounded search are not mathematical "
    "conclusions. Follow returned artifact:// and experiment:// resources instead of "
    "requesting large payloads inline."
)

WORKSPACE_TOOL_NAMES = frozenset(
    {"workspace.open", "workspace.write", "workspace.query"}
)


class AgentRecoveryError(RuntimeError):
    """A safe, actionable failure intended for an agent tool response."""


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


def _forbid_extra_tool_arguments(server: Any, *tool_names: str) -> None:
    """Close SDK-generated argument models that otherwise ignore unknown fields."""

    # MCP 2.0.0b2 creates flat function argument models with Pydantic's default
    # ``extra="ignore"``. Workspace writes must reject the entire request instead of
    # silently committing a partial batch when a caller misspells a top-level field.
    manager = server._tool_manager
    for tool_name in tool_names:
        tool = manager.get_tool(tool_name)
        if tool is None:  # pragma: no cover - registration invariant
            raise RuntimeError(f"workspace tool was not registered: {tool_name}")
        argument_model = tool.fn_metadata.arg_model
        argument_model.model_config["extra"] = "forbid"
        argument_model.model_rebuild(force=True)
        tool.parameters = argument_model.model_json_schema(by_alias=True)


def _publish_workspace_normalization_aliases(server: Any) -> None:
    """Advertise exactly the input aliases normalized by workspace contracts."""

    tool = server._tool_manager.get_tool("workspace.write")
    if tool is None:  # pragma: no cover - registration invariant
        raise RuntimeError("workspace tool was not registered: workspace.write")
    schema = tool.parameters
    definitions = schema["$defs"]
    definitions["WorkspaceFindingKind"]["enum"].remove("PROBLEM")
    definitions["WorkspaceFindingKind"]["enum"].append("OPEN_GOAL")
    definitions["WorkspaceAttemptOutcome"]["enum"].append("SUCCEEDED")

    mark_schema = definitions["WorkspaceMarkDraft"]
    reason_schema = mark_schema["properties"]["reason"]
    mark_schema["properties"]["summary"] = {
        **reason_schema,
        "title": "Summary",
        "description": (
            "Input alias for reason. Supplying both summary and reason is rejected."
        ),
    }
    mark_schema["required"].remove("reason")
    mark_schema["oneOf"] = [
        {
            "required": ["reason"],
            "not": {"required": ["summary"]},
        },
        {
            "required": ["summary"],
            "not": {"required": ["reason"]},
        },
    ]


@dataclass(frozen=True, slots=True)
class AppState:
    kernel: JacobianKernel | None
    tenant_router: TenantKernelRouter | None = None


def create_server(
    state_dir: str | Path | None = None,
    *,
    install_references: bool = True,
    tenant_isolation: bool = False,
    allow_anonymous: bool = False,
    token_verifier: Any | None = None,
    auth: Any | None = None,
    capability_adapter_entrypoints: tuple[str, ...] = (),
    capability_exclusions: frozenset[str] = frozenset(),
) -> MCPServer[AppState]:
    """Create a local or tenant-routed adapter over the Jacobian kernel."""

    if tenant_isolation and capability_exclusions:
        raise ValueError("capability exclusions are supported only by local evaluation")

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

    class JacobianMCPServer(MCPServer[AppState]):
        async def call_tool(
            self,
            name: str,
            arguments: dict[str, Any],
            context: Context[AppState, Any] | None = None,
        ) -> Any:
            try:
                return await super().call_tool(name, arguments, context)
            except MCPError:
                raise
            except Exception as exc:
                _LOGGER.warning(
                    "MCP tool %s failed",
                    name,
                    exc_info=exc,
                )
                raise ValueError(_public_tool_error(name, exc)) from None

    configured_root = _configured_root(state_dir)
    kernel = (
        None
        if tenant_isolation
        else JacobianKernel(
            configured_root,
            install_references=install_references,
            capability_adapter_entrypoints=capability_adapter_entrypoints,
            capability_exclusions=capability_exclusions,
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
        if kernel is not None:
            _start_lean_warmup(kernel)
        yield AppState(kernel=kernel, tenant_router=tenant_router)

    server: MCPServer[AppState] = JacobianMCPServer(
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
        name="capability.describe",
        description=(
            "Read an installed capability's exact descriptor and input schema. Call "
            "this before guessing fields."
        ),
        annotations=_tool_annotations(read_only=True, idempotent=True),
        structured_output=True,
    )
    async def capability_describe(
        capability_id: str | None = None,
        ctx: Context[AppState, Any] | None = None,
    ) -> dict[str, Any]:
        active_kernel = _kernel(ctx)
        capability_catalog = active_kernel.capabilities.catalog()
        descriptors = {
            item.capability_id: item for item in capability_catalog.capabilities
        }
        if capability_id is None:
            return capability_catalog.model_dump(mode="json")
        try:
            descriptor = descriptors[capability_id]
        except KeyError:
            hint = (
                "workspace.* names are direct MCP tools, not capability IDs; call the "
                "workspace tool directly using its published input schema."
                if capability_id.startswith("workspace.")
                else (
                    "Call capability.describe without a capability_id to list installed "
                    "capabilities."
                )
            )
            return {
                "error": {
                    "code": "UNKNOWN_CAPABILITY",
                    "stage": "capability_resolution",
                    "message": f"Unknown capability: {capability_id}",
                    "hint": hint,
                    "available_capability_ids": sorted(descriptors),
                }
            }
        response: dict[str, Any] = {"capability": descriptor.model_dump(mode="json")}
        if capability_id == "lean.check" and active_kernel.lean_checkers:
            response["cache"] = {
                "key": "exact content-addressed certificate and active checker digest",
                "max_entries": 128,
                "warmup_environment_variable": "JACOBIAN_LEAN_WARMUP=1",
            }
        return response

    @server.tool(
        name="capability.invoke",
        description=(
            "Invoke an installed mathematical capability in the fast EXPLORE or "
            "checker-backed VERIFY lane. Call capability.describe first for exact "
            "payload fields; do not guess aliases."
        ),
        annotations=_tool_annotations(),
        structured_output=True,
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
        name="workspace.open",
        description=(
            "Direct tool; do not call capability.describe. Create a durable epistemic "
            "workspace with one canonical problem, a main branch, and an immutable "
            "initial revision. Workspace content is agent-authored and UNVERIFIED."
        ),
        annotations=_tool_annotations(idempotent=True),
        structured_output=False,
    )
    async def workspace_open(
        idempotency_key: WorkspaceIdempotencyKey,
        name: Annotated[str, Field(min_length=1, max_length=128)],
        problem: Annotated[str, Field(min_length=1, max_length=16_384)],
        tags: Annotated[
            list[WorkspaceTag] | None,
            Field(max_length=16),
        ] = None,
        ctx: Context[AppState, Any] | None = None,
    ) -> WorkspaceOpenResult:
        active_kernel = _kernel(ctx)
        return await asyncio.to_thread(
            active_kernel.workspaces.open,
            WorkspaceOpenRequest(
                idempotency_key=idempotency_key,
                name=name,
                problem=problem,
                tags=tuple(tags or ()),
            ),
        )

    @server.tool(
        name="workspace.write",
        description=(
            "Direct tool. Do not call capability.describe. Arguments are flat: send "
            "base_revision (never revision_id) and top-level findings, attempts, marks, "
            "scratch, or focus (never a batch wrapper). Every draft uses client_ref, "
            "never ref. Append at an exact base revision. Finding fields are client_ref, "
            "kind, title, body; optional links are dependency_refs and assumption_refs "
            "(never depends_on_refs). Attempt fields are client_ref, target_ref, method, "
            "outcome, summary. Margin marks append an explicit ACTIVE, CLOSED, "
            "RETRACTED, SUPERSEDED, or ARCHIVED state; only SUPERSEDED carries "
            "superseded_by_ref, and summary is accepted as an alias for reason. "
            "References may use a client_ref from the same batch. OPEN_GOAL normalizes "
            "to GOAL and SUCCEEDED normalizes to COMPLETED. PROBLEM is reserved for "
            "workspace.open. A RETRACTED or SUPERSEDED card must receive an ACTIVE mark "
            "before CLOSED or ARCHIVED. Set focus with active_ref/pinned_refs, clear it "
            "with clear=true, or omit it; focus references finding cards, never "
            "attempts, marks, or scratch. Never send verification/assertion/stale "
            "fields: all workspace assertions remain AGENT_RECORDED and UNVERIFIED. "
            "Canonical batch example: "
            'findings=[{"client_ref":"C1","kind":"CLAIM","title":"...","body":"..."}], '
            'attempts=[{"client_ref":"T1","target_ref":"C1","method":"...",'
            '"outcome":"COMPLETED","summary":"..."}], '
            'focus={"active_ref":"C1","pinned_refs":["C1"]}.'
        ),
        annotations=_tool_annotations(idempotent=True),
        structured_output=False,
    )
    async def workspace_write(
        workspace_id: Annotated[
            WorkspaceId,
            Field(description="workspace:// handle returned by workspace.open"),
        ],
        branch_id: Annotated[
            WorkspaceBranchId,
            Field(description="branch:// handle returned by workspace.open"),
        ],
        base_revision: Annotated[
            WorkspaceRevisionId,
            Field(
                description=(
                    "Exact current revision:// head returned by workspace.open, "
                    "workspace.write, or workspace.query."
                )
            ),
        ],
        idempotency_key: Annotated[
            WorkspaceIdempotencyKey,
            Field(
                description=(
                    "Caller-chosen key unique to this exact write payload; reuse only "
                    "to retry the identical request."
                )
            ),
        ],
        scratch: Annotated[
            list[WorkspaceScratchDraft] | None,
            Field(
                max_length=64,
                description="Optional unverified scratch entries to append.",
            ),
        ] = None,
        findings: Annotated[
            list[WorkspaceFindingDraft] | None,
            Field(
                max_length=64,
                description="Optional typed, unverified cards to append.",
                examples=[
                    [
                        {
                            "client_ref": "C1",
                            "kind": "CLAIM",
                            "title": "Candidate conclusion",
                            "body": "Agent-authored reasoning; still unverified.",
                        }
                    ]
                ],
            ),
        ] = None,
        attempts: Annotated[
            list[WorkspaceAttemptDraft] | None,
            Field(
                max_length=64,
                description="Optional unverified operational attempts to append.",
                examples=[
                    [
                        {
                            "client_ref": "T1",
                            "target_ref": "C1",
                            "method": "direct",
                            "outcome": "COMPLETED",
                            "summary": "The operational attempt finished.",
                        }
                    ]
                ],
            ),
        ] = None,
        marks: Annotated[
            list[WorkspaceMarkDraft] | None,
            Field(
                max_length=64,
                description=(
                    "Optional append-only lifecycle marks. CLOSED is workflow state, "
                    "not proof; RETRACTED and SUPERSEDED deterministically make explicit "
                    "dependents stale."
                ),
                examples=[
                    [
                        {
                            "client_ref": "M1",
                            "target_ref": "C1",
                            "state": "RETRACTED",
                            "reason": "The recorded premise was withdrawn.",
                        }
                    ]
                ],
            ),
        ] = None,
        focus: Annotated[
            WorkspaceFocusDraft | None,
            Field(
                description=(
                    "Optional explicit focus update: set active_ref/pinned_refs, use "
                    "clear=true to clear, or omit to preserve current focus."
                ),
                examples=[{"active_ref": "C1", "pinned_refs": ["C1"]}],
            ),
        ] = None,
        ctx: Context[AppState, Any] | None = None,
    ) -> WorkspaceWriteResult:
        active_kernel = _kernel(ctx)
        return await asyncio.to_thread(
            active_kernel.workspaces.write,
            WorkspaceWriteRequest(
                idempotency_key=idempotency_key,
                workspace_id=workspace_id,
                branch_id=branch_id,
                base_revision=base_revision,
                scratch=tuple(scratch or ()),
                findings=tuple(findings or ()),
                attempts=tuple(attempts or ()),
                marks=tuple(marks or ()),
                focus=focus,
            ),
        )

    @server.tool(
        name="workspace.query",
        description=(
            "Direct tool; do not call capability.describe. Read a compact deterministic "
            "RESUME, FRONTIER, ATTEMPTS, CONTEXT, or STALE view from agent-authored "
            "workspace state. CONTEXT requires target_card_id and follows only explicit "
            "dependency/assumption links. Derived staleness is a paper-like warning, "
            "not a mathematical conclusion. Retrieval preserves UNVERIFIED status."
        ),
        annotations=_tool_annotations(read_only=True, idempotent=True),
        structured_output=False,
    )
    async def workspace_query(
        workspace_id: WorkspaceId,
        branch_id: WorkspaceBranchId,
        revision_id: Annotated[
            WorkspaceRevisionId | None,
            Field(
                description=(
                    "Optional expected branch head revision:// handle. The query "
                    "fails if the current head differs; omit to read the latest."
                )
            ),
        ] = None,
        view: WorkspaceQueryView = WorkspaceQueryView.RESUME,
        target_card_id: WorkspaceCardId | None = None,
        limit: Annotated[StrictInt, Field(ge=1, le=50)] = 10,
        ctx: Context[AppState, Any] | None = None,
    ) -> WorkspaceQueryResult:
        active_kernel = _kernel(ctx)
        return await asyncio.to_thread(
            active_kernel.workspaces.query,
            WorkspaceQueryRequest(
                workspace_id=workspace_id,
                branch_id=branch_id,
                revision_id=revision_id,
                view=view,
                target_card_id=target_card_id,
                limit=limit,
            ),
        )

    _forbid_extra_tool_arguments(server, *WORKSPACE_TOOL_NAMES)
    _publish_workspace_normalization_aliases(server)

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
        description="Read installed domain schema, semantics, plugin, and checker IDs.",
        mime_type="application/json",
    )
    async def reference_catalog_resource() -> str:
        active_kernel = _resource_kernel(kernel, tenant_router)
        return json.dumps(
            reference_catalog(
                active_kernel.references,
                graph=active_kernel.graph,
                polytope=active_kernel.polytope,
                polytope_checkers=active_kernel.polytope_checkers,
                polynomial=active_kernel.polynomial,
                universal_algebra=active_kernel.universal_algebra,
                lean=active_kernel.lean_checkers,
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
    async def experiment_resource(
        experiment_id: str,
    ) -> str:
        active_kernel = _resource_kernel(kernel, tenant_router)
        snapshot = await asyncio.to_thread(
            active_kernel.experiment_router.inspect,
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
            active_kernel.experiment_router.inspect,
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
            active_kernel.experiment_router.inspect,
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
            active_kernel.experiment_router.inspect,
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

    return server


def _kernel(ctx: Context[AppState, Any] | None) -> JacobianKernel:
    if ctx is None:
        raise AgentRecoveryError(
            "Jacobian is unavailable for this request. Retry once; if it fails "
            "again, inspect the local Jacobian log."
        )
    state = ctx.request_context.lifespan_context
    if not isinstance(state, AppState):
        raise AgentRecoveryError(
            "Jacobian is unavailable for this request. Retry once; if it fails "
            "again, inspect the local Jacobian log."
        )
    if state.tenant_router is not None:
        from mcp.server.auth.middleware.auth_context import get_access_token

        access_token = get_access_token()
        subject = access_token.subject if access_token is not None else None
        kernel = state.tenant_router.kernel_for(subject)
        _start_lean_warmup(kernel)
        return kernel
    if state.kernel is None:
        raise AgentRecoveryError(
            "Jacobian is unavailable for this request. Retry once; if it fails "
            "again, inspect the local Jacobian log."
        )
    return state.kernel


def _start_lean_warmup(kernel: JacobianKernel) -> None:
    if kernel.lean is not None and os.environ.get("JACOBIAN_LEAN_WARMUP") == "1":
        kernel.lean.start_mathlib_warmup()


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
        raise AgentRecoveryError(
            "Jacobian is unavailable for this resource request. Retry once; if it "
            "fails again, inspect the local Jacobian log."
        )
    return kernel


def _configured_root(state_dir: str | Path | None) -> Path:
    if state_dir is not None:
        return Path(state_dir)
    return Path(os.environ.get("JACOBIAN_STATE_DIR", ".jacobian"))


def _public_tool_error(tool_name: str, exc: Exception) -> str:
    from jacobian.adapters.mcp.remote import AuthenticationError
    from jacobian.experiments import ExperimentNotFoundError
    from jacobian.registry import CheckerNotFoundError
    from jacobian.store import ArtifactNotFoundError
    from jacobian.workspaces import (
        WorkspaceConflictError,
        WorkspaceIdempotencyError,
        WorkspaceNotFoundError,
        WorkspaceReferenceError,
    )

    tool_error = exc.__cause__ if isinstance(exc, ToolError) else exc
    if not isinstance(tool_error, Exception):
        tool_error = exc
    if isinstance(tool_error, AgentRecoveryError):
        code = "SERVICE_UNAVAILABLE"
        message = str(tool_error)
        hint = "Follow the recovery action in the message, then retry the tool."
    elif isinstance(tool_error, TimeoutError):
        code = "OPERATION_TIMED_OUT"
        message = "The operation did not finish within the allowed time."
        hint = "Retry with a larger time budget or a smaller request."
    elif isinstance(tool_error, AuthenticationError):
        code = "AUTHENTICATION_REQUIRED"
        message = str(tool_error)
        hint = "Authenticate with a configured bearer token, then retry."
    elif isinstance(tool_error, PermissionError):
        code = "PERMISSION_DENIED"
        message = "Jacobian could not access the required local resource."
        hint = "Check the state-directory permissions, then retry."
    elif isinstance(
        tool_error,
        (
            ArtifactNotFoundError,
            CheckerNotFoundError,
            ExperimentNotFoundError,
            WorkspaceNotFoundError,
        ),
    ):
        code = "RESOURCE_NOT_FOUND"
        message = "A required Jacobian resource was not found."
        hint = (
            "Check the artifact or experiment URI returned by the earlier tool call, "
            "then retry."
        )
    elif isinstance(tool_error, WorkspaceConflictError):
        code = "WORKSPACE_CONFLICT"
        message = str(tool_error)
        hint = "Query the latest workspace revision, then retry from that exact head."
    elif isinstance(
        tool_error,
        (WorkspaceIdempotencyError, WorkspaceReferenceError),
    ):
        code = "INVALID_INPUT"
        message = str(tool_error)
        hint = "Check the published workspace tool schema and returned handles."
    elif isinstance(tool_error, ValueError):
        code = "INVALID_INPUT"
        message = "The tool input is not valid for this operation."
        hint = (
            "Check the published workspace tool schema, then retry."
            if tool_name.startswith("workspace.")
            else "Check the tool input schema or call capability.describe, then retry."
        )
    else:
        code = "OPERATION_FAILED"
        message = "Jacobian could not complete the operation."
        hint = "Retry once; if it fails again, inspect the local Jacobian log."
    return json.dumps(
        {
            "error": {
                "code": code,
                "stage": tool_name,
                "message": message,
                "hint": hint,
            }
        },
        ensure_ascii=False,
        sort_keys=True,
    )


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
