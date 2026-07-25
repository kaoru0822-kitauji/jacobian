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
from typing import TYPE_CHECKING, Any

from mcp.server.mcpserver.exceptions import ToolError
from mcp.shared.exceptions import MCPError
from mcp_types import ToolAnnotations
from pydantic import AnyHttpUrl

from jacobian import __version__
from jacobian.contracts.capabilities import (
    CapabilityMode,
    CapabilityRequest,
    CapabilityResult,
)

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp.server import MCPServer
    from mcp.server.mcpserver import Context

    from jacobian.adapters.mcp.remote import TenantKernelRouter
    from jacobian.kernel import JacobianKernel


SERVER_INSTRUCTIONS = (
    "Call capability.describe before the first invocation of an unfamiliar "
    "capability; do not guess payload fields. Use EXPLORE for low-friction search "
    "and VERIFY only when a durable checked conclusion is needed. Retrieved memory, "
    "search, evaluation, and generated evidence are not proof. Only assurance level "
    "VERIFIED with a local verification record is verified. Operational completion, "
    "failure to find a witness, and exhausted or bounded search are not mathematical "
    "conclusions. Follow returned artifact:// and experiment:// resources instead of "
    "requesting large payloads inline."
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
            return {
                "error": {
                    "code": "UNKNOWN_CAPABILITY",
                    "stage": "capability_resolution",
                    "message": f"Unknown capability: {capability_id}",
                    "hint": (
                        "Call capability.describe without a capability_id to list "
                        "installed capabilities."
                    ),
                    "available_capability_ids": sorted(descriptors),
                }
            }
        response: dict[str, Any] = {"capability": descriptor.model_dump(mode="json")}
        if capability_id == "lean.check" and active_kernel.lean_checkers:
            response["runtime"] = _lean_runtime_metadata(active_kernel)
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
                polytope=active_kernel.polytope,
                polytope_checkers=active_kernel.polytope_checkers,
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
        (ArtifactNotFoundError, CheckerNotFoundError, ExperimentNotFoundError),
    ):
        code = "RESOURCE_NOT_FOUND"
        message = "A required Jacobian resource was not found."
        hint = (
            "Check the artifact or experiment URI returned by the earlier tool call, "
            "then retry."
        )
    elif isinstance(tool_error, ValueError):
        code = "INVALID_INPUT"
        message = "The tool input is not valid for this operation."
        hint = "Check the tool input schema or call capability.describe, then retry."
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


def _lean_runtime_metadata(kernel: JacobianKernel) -> dict[str, Any]:
    return {
        "profiles": {
            environment.value: {
                "semantics_uri": installation.semantics_uri,
                "import_name": installation.import_name,
                "mathlib_commit": installation.mathlib_commit,
                "allowed_axioms": installation.allowed_axioms,
                "checker_timeout_seconds": installation.checker_timeout_seconds,
            }
            for environment, installation in sorted(
                kernel.lean_checkers.items(),
                key=lambda item: item[0].value,
            )
        }
    }


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
