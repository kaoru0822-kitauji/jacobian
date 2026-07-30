"""Thin MCP 2.0.0b2 adapter over the tested Python runtime."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

from mcp.server.extension import Extension, ResourceBinding, ToolBinding
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver.resources import FunctionResource, TextResource
from mcp.shared.exceptions import MCPError
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field, StrictInt

from jacobian import __version__
from jacobian.adapters.mcp.guidance import (
    CAPABILITY_DESCRIBE_DESCRIPTION,
    CAPABILITY_INVOKE_DESCRIPTION,
    OPERATING_GUIDE,
    SERVER_DESCRIPTION,
    SERVER_INSTRUCTIONS,
    discovery_prompt,
    evidence_check_prompt,
)
from jacobian.bounded_process import bounded_process_cancellation
from jacobian.canonical import canonicalize_json
from jacobian.capabilities import CapabilityDiscoveryCursorError, CapabilityPolicy
from jacobian.contracts.capabilities import (
    CapabilityDescriptor,
    CapabilityDiscoveryRequest,
    CapabilityInputKind,
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
from jacobian.references import reference_catalog

_LOGGER = logging.getLogger(__name__)
CAPABILITY_DISCOVERY_RESPONSE_BYTE_LIMIT = 16_384
CapabilityDescriptionView = Literal["SUMMARY", "CONTRACT", "FULL"]
CapabilityInvocationView = Literal["SUMMARY", "STANDARD", "FULL"]
CAPABILITY_STANDARD_OUTPUT_BYTE_LIMIT = 8_192
CAPABILITY_STANDARD_FIELD_BYTE_LIMIT = 2_048
CAPABILITY_STANDARD_INCLUDED_FIELD_BYTE_LIMIT = 6_144
_CAPABILITY_SCOPE_RULE = {
    "conclusion_scope": "Only the exact supplied input or claim is covered.",
    "bounded_repetition": (
        "Additional finite or bounded invocations remain finite evidence; they do "
        "not establish an all-orders, all-parameters, or otherwise unbounded "
        "conclusion."
    ),
}


def _compact_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _json_bytes(value: object) -> bytes:
    return _compact_json(value).encode("utf-8")


def _mcp_text_json_bytes(value: object) -> bytes:
    """Measure JSON as FastMCP renders structured tool results."""
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def _json_digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(_json_bytes(value)).hexdigest()}"


def _json_kind(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, list | tuple):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _json_pointer_segment(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _invocation_text_projection(
    result: CapabilityResult,
    *,
    view: CapabilityInvocationView,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project model-visible text without changing the canonical result."""

    canonical = result.model_dump(mode="json")
    canonical_bytes = _json_bytes(canonical)
    canonical_digest = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
    projected = dict(canonical)
    output = canonical["output"]
    output_bytes = _json_bytes(output)
    omitted: list[dict[str, Any]] = []

    if view == "SUMMARY":
        projected["output"] = {}
        if output:
            omitted.append(
                {
                    "path": "/output",
                    "json_type": "object",
                    "byte_count": len(output_bytes),
                    "sha256": _json_digest(output),
                }
            )
    elif (
        view == "STANDARD"
        and result.episode_uri is not None
        and len(output_bytes) > CAPABILITY_STANDARD_OUTPUT_BYTE_LIMIT
    ):
        included: dict[str, Any] = {}
        included_bytes = 0
        for key in sorted(output):
            value = output[key]
            value_bytes = _json_bytes(value)
            is_scalar = not isinstance(value, dict | list | tuple)
            fits_field = len(value_bytes) <= CAPABILITY_STANDARD_FIELD_BYTE_LIMIT
            fits_total = (
                included_bytes + len(value_bytes)
                <= CAPABILITY_STANDARD_INCLUDED_FIELD_BYTE_LIMIT
            )
            if is_scalar or (fits_field and fits_total):
                included[key] = value
                included_bytes += len(value_bytes)
                continue
            omitted.append(
                {
                    "path": f"/output/{_json_pointer_segment(key)}",
                    "json_type": _json_kind(value),
                    "byte_count": len(value_bytes),
                    "sha256": _json_digest(value),
                }
            )
        projected["output"] = included

    output_complete = not omitted
    projection = {
        "projection_version": "1",
        "view": view,
        "canonical_result_in_structured_content": True,
        "output_complete": output_complete,
        "logical_payload_bytes": len(canonical_bytes),
        "full_result_sha256": canonical_digest,
        "full_result_episode_uri": result.episode_uri,
        "omitted_output_fields": omitted,
    }
    if not output_complete:
        projection["recovery"] = (
            "Read full_result_episode_uri for the durable canonical result, or invoke "
            'again with view="FULL" when no durable result is available.'
        )
    if view != "FULL":
        projected["mcp_projection"] = projection
    return projected, projection


def _capability_call_tool_result(
    result: CapabilityResult,
    *,
    view: CapabilityInvocationView,
) -> CallToolResult:
    canonical = result.model_dump(mode="json")
    projected, projection = _invocation_text_projection(result, view=view)
    text = _compact_json(canonical if view == "FULL" else projected)
    model_visible_bytes = len(text.encode("utf-8"))
    return CallToolResult(
        _meta={
            "jacobian": {
                "result_view": view,
                "logical_payload_bytes": projection["logical_payload_bytes"],
                "model_visible_payload_bytes": model_visible_bytes,
                "full_result_sha256": projection["full_result_sha256"],
                "full_result_episode_uri": projection["full_result_episode_uri"],
                "output_complete": projection["output_complete"],
            }
        },
        content=[TextContent(type="text", text=text)],
        structured_content=canonical,
        is_error=False,
    )


_RELATED_CAPABILITIES: dict[str, tuple[tuple[str, str], ...]] = {
    "sat.cnf.materialize": (
        ("sat.model.find", "find a candidate named assignment"),
        ("sat.model.verify", "independently verify a candidate assignment"),
        ("sat.unsat_proof.find", "produce an addition-only DRAT candidate"),
        ("sat.unsat_proof.verify", "independently verify the exact DRAT proof"),
    ),
    "sat.model.find": (
        ("sat.cnf.materialize", "materialize the exact input CNF"),
        ("sat.model.verify", "independently verify the named assignment"),
    ),
    "sat.unsat_proof.find": (
        ("sat.cnf.materialize", "materialize the exact input CNF"),
        ("sat.unsat_proof.verify", "independently verify the retained DRAT proof"),
    ),
    "smt.unsat_proof.find": (
        ("smt.unsat_proof.verify", "independently verify compatible proof evidence"),
        (
            "sat.cnf.materialize",
            "prefer named Boolean CNF for finite colorings and forbidden patterns",
        ),
    ),
    "graph.invariant.maximum_matching.compute": (
        (
            "graph.invariant.maximum_matching.verify",
            "independently replay the stored Tutte-Berge certificate",
        ),
    ),
    "graph.invariant.maximum_matching.verify": (
        (
            "graph.invariant.maximum_matching.compute",
            "produce a matching witness and Tutte-Berge certificate",
        ),
    ),
    "graph.hamiltonian_path.decide": (
        (
            "graph.hamiltonian_path.verify",
            "independently verify the stored positive or negative decision",
        ),
    ),
    "graph.hamiltonian_path.verify": (
        (
            "graph.hamiltonian_path.decide",
            "produce a complete bounded decision and optional path witness",
        ),
    ),
    "polynomial.jacobian_syzygy.minimum_degree.compute": (
        (
            "polynomial.jacobian_syzygy.minimum_degree.verify",
            "independently rebuild the graded maps, ranks, minors, and first kernel",
        ),
    ),
    "polynomial.jacobian_syzygy.minimum_degree.verify": (
        (
            "polynomial.jacobian_syzygy.minimum_degree.compute",
            "produce the provenance-bound graded rank ledger and kernel witness",
        ),
    ),
    "geometry.projective_line_arrangement.flats.materialize": (
        (
            "geometry.projective_line_arrangement.flats.verify",
            "independently rebuild all projective flats and pair accounting",
        ),
    ),
    "geometry.projective_line_arrangement.flats.verify": (
        (
            "geometry.projective_line_arrangement.flats.materialize",
            "materialize normalized lines, exact flats, incidences and multiplicities",
        ),
    ),
}

if TYPE_CHECKING:
    from mcp.server import MCPServer
    from mcp.server.mcpserver import Context

    from jacobian.adapters.mcp.remote import TenantRuntimeRouter
    from jacobian.runtime import CheckerAuthorityMode
    from jacobian.runtime.model import JacobianRuntime


def _invoke_capability_with_cancellation(
    runtime: Any,
    request: CapabilityRequest,
    cancellation_event: threading.Event,
) -> CapabilityResult:
    with bounded_process_cancellation(cancellation_event):
        result: CapabilityResult = runtime.core.capabilities.invoke(request)
        return result


def _consume_cancelled_worker_result(task: asyncio.Task[CapabilityResult]) -> None:
    with suppress(BaseException):
        task.result()


def _capability_inspection_extensions(
    capability_id: str,
    descriptors: dict[str, CapabilityDescriptor],
) -> dict[str, Any]:
    extensions: dict[str, Any] = {}
    related = [
        {
            "capability_id": related_id,
            "relationship": relationship,
        }
        for related_id, relationship in _RELATED_CAPABILITIES.get(capability_id, ())
        if related_id in descriptors
    ]
    if related:
        extensions["related_capabilities"] = related
    if capability_id.startswith(("sat.", "smt.")):
        extensions["synchronous_execution"] = {
            "remote_safe_wall_seconds_max": 150,
            "timeout_is_a_non_conclusion": True,
            "partition_larger_searches": True,
            "backend_suitability": (
                "Named Boolean CNF is preferred for finite colorings and forbidden "
                "finite configurations; use SMT when arithmetic or "
                "uninterpreted-function structure is essential."
            ),
        }
    return extensions


def _compact_json_schema(value: Any) -> Any:
    """Drop annotation-only prose while preserving validation semantics."""

    if isinstance(value, dict):
        return {
            key: _compact_json_schema(item)
            for key, item in value.items()
            if key
            not in {
                "$comment",
                "default",
                "deprecated",
                "description",
                "discriminator",
                "examples",
                "readOnly",
                "title",
                "writeOnly",
            }
        }
    if isinstance(value, list):
        return [_compact_json_schema(item) for item in value]
    return value


def _output_schema_summary(schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties")
    summary: dict[str, Any] = {
        "type": schema.get("type"),
        "required": schema.get("required", []),
        "property_names": (sorted(properties) if isinstance(properties, dict) else []),
    }
    if "$ref" in schema:
        summary["$ref"] = schema["$ref"]
    if "oneOf" in schema:
        summary["one_of_variants"] = len(schema["oneOf"])
    if "anyOf" in schema:
        summary["any_of_variants"] = len(schema["anyOf"])
    return summary


def _input_schema_summary(schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties")
    return {
        "type": schema.get("type"),
        "required": schema.get("required", []),
        "property_names": sorted(properties) if isinstance(properties, dict) else [],
    }


def _capability_descriptor_view(
    descriptor: CapabilityDescriptor,
    *,
    view: CapabilityDescriptionView,
) -> dict[str, Any]:
    if view == "FULL":
        return descriptor.model_dump(mode="json")
    runtime = descriptor.provider_runtime
    if view == "SUMMARY":
        runtime_summary = (
            runtime.model_dump(
                mode="json",
                exclude_none=True,
                include={
                    "availability",
                    "version",
                    "diagnostic",
                },
            )
            if runtime is not None
            else None
        )
        return {
            "capability_id": descriptor.capability_id,
            "version": descriptor.version,
            "title": descriptor.title,
            "description": descriptor.description,
            "provider": descriptor.provider,
            "provider_runtime": runtime_summary,
            "modes": [mode.value for mode in descriptor.modes],
            "tags": list(descriptor.tags),
            "accepted_input_kinds": [
                kind.value for kind in descriptor.accepted_input_kinds
            ],
            "accepted_artifact_types": list(descriptor.accepted_artifact_types),
            "input_schema_summary": _input_schema_summary(descriptor.input_schema),
            "output_schema_summary": _output_schema_summary(descriptor.output_schema),
            "has_invocation_examples": bool(descriptor.invocation_examples),
        }
    runtime_summary = (
        runtime.model_dump(
            mode="json",
            exclude_none=True,
            include={
                "availability",
                "version",
                "digest",
                "checker_ids",
                "diagnostic",
            },
        )
        if runtime is not None
        else None
    )
    return {
        "capability_id": descriptor.capability_id,
        "version": descriptor.version,
        "title": descriptor.title,
        "description": descriptor.description,
        "provider": descriptor.provider,
        "provider_runtime": runtime_summary,
        "modes": [mode.value for mode in descriptor.modes],
        "accepted_input_kinds": [
            kind.value for kind in descriptor.accepted_input_kinds
        ],
        "accepted_artifact_types": list(descriptor.accepted_artifact_types),
        "input_schema": _compact_json_schema(descriptor.input_schema),
        "output_schema_summary": _output_schema_summary(descriptor.output_schema),
    }


WORKSPACE_TOOL_NAMES = frozenset(
    {"workspace.open", "workspace.write", "workspace.query"}
)
WORKSPACE_OPEN_DESCRIPTION = (
    "Direct tool; do not call capability.describe. Create a durable epistemic "
    "workspace with one canonical problem, a main branch, and an immutable initial "
    "revision. Workspace content is agent-authored and UNVERIFIED."
)
WORKSPACE_WRITE_DESCRIPTION = (
    "Direct tool. Do not call capability.describe. Arguments are flat: send "
    "base_revision (never revision_id) and top-level findings, attempts, marks, "
    "scratch, or focus (never a batch wrapper). Every draft uses client_ref, never "
    "ref. Append at an exact base revision. Finding fields are client_ref, kind, "
    "title, body; optional links are dependency_refs and assumption_refs (never "
    "depends_on_refs). Attempt fields are client_ref, target_ref, method, outcome, "
    "summary. Margin marks append an explicit ACTIVE, CLOSED, RETRACTED, SUPERSEDED, "
    "or ARCHIVED state; only SUPERSEDED carries superseded_by_ref. References may "
    "use a client_ref from the same batch. "
    "PROBLEM is reserved for workspace.open. A RETRACTED or SUPERSEDED card must "
    "receive an ACTIVE mark before CLOSED or ARCHIVED. Set focus with "
    "active_ref/pinned_refs, clear it with clear=true, or omit it; focus references "
    "finding cards, never attempts, marks, or scratch. Never send "
    "verification/assertion/stale fields: all workspace assertions remain "
    "AGENT_RECORDED and UNVERIFIED. Canonical batch example: "
    'findings=[{"client_ref":"C1","kind":"CLAIM","title":"...","body":"..."}], '
    'attempts=[{"client_ref":"T1","target_ref":"C1","method":"...",'
    '"outcome":"COMPLETED","summary":"..."}], '
    'focus={"active_ref":"C1","pinned_refs":["C1"]}.'
)
WORKSPACE_QUERY_DESCRIPTION = (
    "Direct tool; do not call capability.describe. Read a compact deterministic "
    "RESUME, FRONTIER, ATTEMPTS, CONTEXT, or STALE view from agent-authored workspace "
    "state. CONTEXT requires target_card_id and follows only explicit "
    "dependency/assumption links. Derived staleness is a paper-like warning, not a "
    "mathematical conclusion. Retrieval preserves UNVERIFIED status."
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


def _argument_digest(arguments: dict[str, Any]) -> str:
    try:
        encoded = canonicalize_json(arguments)
    except (TypeError, ValueError):
        encoded = json.dumps(
            arguments,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _request_trace_digest(ctx: Any | None) -> tuple[str, str]:
    """Return a bounded correlation digest without retaining caller identifiers."""

    if ctx is None:
        return "none", "none"
    headers = getattr(ctx, "headers", None)
    if headers is not None:
        traceparent = headers.get("traceparent")
        if isinstance(traceparent, str) and 0 < len(traceparent) <= 256:
            digest = hashlib.sha256(traceparent.encode("utf-8")).hexdigest()[:8]
            return digest, "traceparent"
    try:
        request_id = str(ctx.request_id)
    except (AttributeError, TypeError, ValueError):
        return "none", "none"
    if not request_id or len(request_id) > 256:
        return "none", "none"
    digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:8]
    return digest, "request_id"


def _response_size(value: Any) -> int:
    try:
        if hasattr(value, "model_dump_json"):
            return len(value.model_dump_json().encode("utf-8"))
        return len(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        )
    except (TypeError, ValueError):
        return -1


def _log_capability_attempt(
    *,
    capability_id: str,
    mode: CapabilityMode,
    started: float,
    argument_digest: str,
    trace_digest: str,
    trace_source: str,
    result: CapabilityResult | None = None,
    execution_status: str | None = None,
    diagnostic_codes: tuple[str, ...] = (),
) -> None:
    if result is not None:
        execution_status = result.execution.status.value
        diagnostic_codes = tuple(item.code for item in result.diagnostics)
        capability_version = result.capability_version
        assurance = result.assurance.level.value
        operation_runtime_ms = result.execution.runtime_ms
        response_bytes = _response_size(result)
    else:
        capability_version = "unknown"
        assurance = "none"
        operation_runtime_ms = None
        response_bytes = 0
    codes = ",".join(diagnostic_codes[:8]) or "none"
    _LOGGER.info(
        "MCP capability attempt trace_digest=%s trace_source=%s "
        "capability_id=%s capability_version=%s mode=%s "
        "execution_status=%s assurance=%s diagnostic_codes=%s "
        "attempt_duration_ms=%.3f operation_runtime_ms=%s "
        "response_bytes=%d argument_digest=%s",
        trace_digest,
        trace_source,
        capability_id,
        capability_version,
        mode.value,
        execution_status or "ERROR",
        assurance,
        codes,
        (time.monotonic() - started) * 1000,
        "none" if operation_runtime_ms is None else operation_runtime_ms,
        response_bytes,
        argument_digest,
    )


async def _invoke_capability_attempt(
    runtime: Any,
    *,
    capability_id: str,
    payload: dict[str, Any],
    mode: CapabilityMode,
    ctx: Any | None,
) -> CapabilityResult:
    started = time.monotonic()
    argument_digest = _argument_digest(
        {
            "capability_id": capability_id,
            "mode": mode.value,
            "payload": payload,
        }
    )
    trace_digest, trace_source = _request_trace_digest(ctx)
    cancellation_event = threading.Event()
    worker = asyncio.create_task(
        asyncio.to_thread(
            _invoke_capability_with_cancellation,
            runtime,
            CapabilityRequest(
                capability_id=capability_id,
                mode=mode,
                input=payload,
            ),
            cancellation_event,
        )
    )
    try:
        result = await asyncio.shield(worker)
    except asyncio.CancelledError:
        cancellation_event.set()
        worker.add_done_callback(_consume_cancelled_worker_result)
        _log_capability_attempt(
            capability_id=capability_id,
            mode=mode,
            started=started,
            argument_digest=argument_digest,
            trace_digest=trace_digest,
            trace_source=trace_source,
            execution_status="CANCELLED",
            diagnostic_codes=("CLIENT_CANCELLED",),
        )
        raise
    except Exception:
        _log_capability_attempt(
            capability_id=capability_id,
            mode=mode,
            started=started,
            argument_digest=argument_digest,
            trace_digest=trace_digest,
            trace_source=trace_source,
            execution_status="ERROR",
            diagnostic_codes=("INVOCATION_EXCEPTION",),
        )
        raise
    _log_capability_attempt(
        capability_id=capability_id,
        mode=mode,
        started=started,
        argument_digest=argument_digest,
        trace_digest=trace_digest,
        trace_source=trace_source,
        result=result,
    )
    return result


def _catalog_digest(
    catalog_version: str,
    capabilities: tuple[CapabilityDescriptor, ...],
) -> str:
    payload = {
        "catalog_version": catalog_version,
        "capabilities": [
            descriptor.model_dump(mode="json") for descriptor in capabilities
        ],
    }
    return f"sha256:{hashlib.sha256(canonicalize_json(payload)).hexdigest()}"


def _capability_discovery_response(
    runtime: JacobianRuntime,
    *,
    query: str | None,
    domain: str | None,
    mode: CapabilityMode | None,
    input_kind: CapabilityInputKind | None,
    artifact_type: str | None,
    limit: int | None,
    cursor: str | None,
) -> dict[str, Any]:
    catalog = runtime.core.capabilities.catalog()
    try:
        discovered = runtime.core.capabilities.discover(
            CapabilityDiscoveryRequest(
                query=query,
                domain=domain,
                mode=mode,
                input_kind=input_kind,
                artifact_type=artifact_type,
                limit=limit if limit is not None else 5,
                cursor=cursor,
            )
        )
    except CapabilityDiscoveryCursorError:
        return {
            "error": {
                "code": "INVALID_CURSOR",
                "stage": "capability_discovery",
                "message": "The capability discovery cursor is not in this result set.",
                "hint": (
                    "Restart discovery without a cursor, or reuse the same query, "
                    "domain, mode, input_kind, artifact_type, and limit that produced "
                    "next_cursor."
                ),
            }
        }
    response = {
        "kind": "discovery",
        "catalog_version": catalog.catalog_version,
        "policy_profile": catalog.policy_profile,
        "policy_digest": catalog.policy_digest,
        "catalog_digest": _catalog_digest(
            catalog.catalog_version,
            catalog.capabilities,
        ),
        **discovered.model_dump(mode="json"),
        "next_step": {
            "tool": "capability.describe",
            "argument": "capability_id",
            "choose_from": "matches[].capability_id",
        },
        "routing_guidance": {
            "inspect_candidates": (
                "Inspect only the strongest one or two domain-relevant matches; "
                "search again only when none fits the required outcome."
            ),
            "verification_handoff": (
                "Invoke the selected producer before searching for a checker; "
                "follow checker, certificate, and verification fields returned by "
                "the producer result instead of guessing a generic verifier."
            ),
        },
        "response_byte_limit": CAPABILITY_DISCOVERY_RESPONSE_BYTE_LIMIT,
        "truncation_reason": None,
    }
    matches = cast(list[dict[str, Any]], response["matches"])
    while (
        len(_mcp_text_json_bytes(response)) > CAPABILITY_DISCOVERY_RESPONSE_BYTE_LIMIT
        and len(matches) > 1
    ):
        matches.pop()
        response["truncated"] = True
        response["next_cursor"] = matches[-1]["capability_id"]
        response["truncation_reason"] = "BYTE_LIMIT"
    available_domains = cast(list[str], response["available_domains"])
    response["available_domains_total"] = len(available_domains)
    response["available_domains_truncated"] = False
    while (
        len(_mcp_text_json_bytes(response)) > CAPABILITY_DISCOVERY_RESPONSE_BYTE_LIMIT
        and available_domains
    ):
        available_domains.pop()
        response["available_domains_truncated"] = True
        response["truncation_reason"] = "BYTE_LIMIT"
    response["match_metadata_truncated"] = False
    compact_fields = ("tags", "matched_on", "matched_terms")
    while (
        len(_mcp_text_json_bytes(response)) > CAPABILITY_DISCOVERY_RESPONSE_BYTE_LIMIT
    ):
        removed = False
        for match in matches:
            for field in compact_fields:
                values = match.get(field)
                if isinstance(values, list) and values:
                    values.pop()
                    removed = True
                    response["match_metadata_truncated"] = True
                    response["truncation_reason"] = "BYTE_LIMIT"
                    break
            if removed:
                break
        if not removed:
            raise RuntimeError(
                "compact capability discovery response exceeds its hard byte limit"
            )
    return response


@dataclass(frozen=True, slots=True)
class AppState:
    runtime: JacobianRuntime | None
    tenant_router: TenantRuntimeRouter | None = None


class JacobianCoreExtension(Extension):
    """Stable Jacobian tools and static resources contributed through MCP v2."""

    identifier = "io.jacobian/core"

    def __init__(
        self,
        runtime: JacobianRuntime | None,
        tenant_router: TenantRuntimeRouter | None,
    ) -> None:
        self._runtime = runtime
        self._tenant_router = tenant_router

    def settings(self) -> dict[str, Any]:
        return {"version": "1"}

    def tools(self) -> tuple[ToolBinding, ...]:
        return (
            ToolBinding(
                _safe_tool_handler("capability.describe", capability_describe),
                kwargs={
                    "name": "capability.describe",
                    "title": "Discover mathematical capabilities",
                    "description": CAPABILITY_DESCRIBE_DESCRIPTION,
                    "annotations": _tool_annotations(read_only=True, idempotent=True),
                    "structured_output": True,
                },
            ),
            ToolBinding(
                _safe_tool_handler("capability.invoke", capability_invoke),
                kwargs={
                    "name": "capability.invoke",
                    "title": "Execute a mathematical capability",
                    "description": CAPABILITY_INVOKE_DESCRIPTION,
                    "annotations": _tool_annotations(),
                    "structured_output": True,
                },
            ),
            ToolBinding(
                _safe_tool_handler("workspace.open", workspace_open),
                kwargs={
                    "name": "workspace.open",
                    "description": WORKSPACE_OPEN_DESCRIPTION,
                    "annotations": _tool_annotations(idempotent=True),
                    "structured_output": False,
                },
            ),
            ToolBinding(
                _safe_tool_handler("workspace.write", workspace_write),
                kwargs={
                    "name": "workspace.write",
                    "description": WORKSPACE_WRITE_DESCRIPTION,
                    "annotations": _tool_annotations(idempotent=True),
                    "structured_output": False,
                },
            ),
            ToolBinding(
                _safe_tool_handler("workspace.query", workspace_query),
                kwargs={
                    "name": "workspace.query",
                    "description": WORKSPACE_QUERY_DESCRIPTION,
                    "annotations": _tool_annotations(read_only=True, idempotent=True),
                    "structured_output": False,
                },
            ),
        )

    def resources(self) -> tuple[ResourceBinding, ...]:
        return (
            ResourceBinding(
                TextResource(
                    uri="jacobian://instructions",
                    name="jacobian-instructions",
                    title="Jacobian operating guide",
                    description=(
                        "Complete guidance for discovering, invoking, and independently "
                        "checking Jacobian mathematical capabilities."
                    ),
                    mime_type="text/markdown",
                    text=OPERATING_GUIDE,
                )
            ),
            ResourceBinding(
                FunctionResource.from_function(
                    self._capability_catalog,
                    uri="capability://catalog",
                    name="capability-catalog",
                    description=(
                        "Installed model-facing operations, supported lanes, and "
                        "compact schemas."
                    ),
                    mime_type="application/json",
                )
            ),
            ResourceBinding(
                FunctionResource.from_function(
                    self._reference_catalog,
                    uri="reference://catalog",
                    name="reference-catalog",
                    description=(
                        "Read installed domain schema, semantics, plugin, and checker IDs."
                    ),
                    mime_type="application/json",
                )
            ),
        )

    async def _capability_catalog(self) -> str:
        active_runtime = _resource_runtime(self._runtime, self._tenant_router)
        return json.dumps(
            active_runtime.core.capabilities.catalog().model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )

    async def _reference_catalog(self) -> str:
        active_runtime = _resource_runtime(self._runtime, self._tenant_router)
        return json.dumps(
            reference_catalog(
                active_runtime.portfolio.references,
                graph=active_runtime.portfolio.graph,
                polytope=active_runtime.services.polytope,
                polytope_checkers=active_runtime.portfolio.polytope_checkers,
                polynomial=active_runtime.portfolio.polynomial,
                universal_algebra=active_runtime.portfolio.universal_algebra,
                lean=active_runtime.portfolio.lean_checkers,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )

    async def intercept_tool_call(
        self,
        params: Any,
        ctx: Any,
        call_next: Any,
    ) -> Any:
        started = time.monotonic()
        arguments = params.arguments or {}
        argument_digest = _argument_digest(arguments)
        try:
            result = await call_next(ctx)
        except MCPError:
            _log_tool_call(params.name, started, argument_digest, status="error")
            raise
        except Exception as exc:
            _LOGGER.warning("MCP tool %s failed", params.name, exc_info=exc)
            _log_tool_call(params.name, started, argument_digest, status="error")
            raise ToolError(_public_tool_error(params.name, exc)) from exc
        _log_tool_call(
            params.name,
            started,
            argument_digest,
            status="success",
            result=result,
        )
        return result


def _safe_tool_handler(tool_name: str, handler: Any) -> Any:
    """Translate internal failures at the handler boundary before SDK rendering."""

    @wraps(handler)
    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            return await handler(*args, **kwargs)
        except MCPError:
            raise
        except Exception as exc:
            _LOGGER.warning("MCP tool %s failed", tool_name, exc_info=exc)
            raise ToolError(_public_tool_error(tool_name, exc)) from exc

    return wrapped


def _log_tool_call(
    name: str,
    started: float,
    argument_digest: str,
    *,
    status: str,
    result: Any | None = None,
) -> None:
    _LOGGER.info(
        "MCP tool call tool=%s status=%s duration_ms=%.3f "
        "response_bytes=%d argument_digest=%s",
        name,
        status,
        (time.monotonic() - started) * 1000,
        0 if result is None else _response_size(result),
        argument_digest,
    )


def _selected_checker_authority(
    authority: CheckerAuthorityMode | None,
) -> CheckerAuthorityMode:
    if authority is not None:
        return authority
    from jacobian.runtime import CheckerAuthorityMode

    return CheckerAuthorityMode.INSTALL_BUNDLED


@asynccontextmanager
async def _runtime_lifespan(
    _server: Any,
    *,
    runtime: JacobianRuntime | None,
    tenant_router: TenantRuntimeRouter | None,
) -> AsyncIterator[AppState]:
    if runtime is not None:
        _start_lean_warmup(runtime)
    try:
        yield AppState(runtime=runtime, tenant_router=tenant_router)
    finally:
        if runtime is not None:
            runtime.close()
        if tenant_router is not None:
            tenant_router.close()


def create_server(
    state_dir: str | Path | None = None,
    *,
    checker_authority: CheckerAuthorityMode | None = None,
    tenant_isolation: bool = False,
    allow_anonymous: bool = False,
    anonymous_tenant_id: str = "anonymous",
    token_verifier: Any | None = None,
    auth: Any | None = None,
    capability_adapter_entrypoints: tuple[str, ...] = (),
    capability_exclusions: frozenset[str] = frozenset(),
    capability_policy: CapabilityPolicy | None = None,
    max_tenant_runtimes: int | None = None,
) -> MCPServer[AppState]:
    """Create a local or tenant-routed adapter over a Jacobian runtime."""

    if tenant_isolation and capability_exclusions:
        raise ValueError("capability exclusions are supported only by local evaluation")

    # Keep ``--help`` and ``--version`` independent of the MCP runtime's
    # heavier imports and shutdown hooks.
    from mcp.server import MCPServer
    from mcp.server.mcpserver import Context

    from jacobian.adapters.mcp.remote import (
        DEFAULT_MAX_TENANT_RUNTIMES,
        TenantRuntimeRouter,
    )
    from jacobian.runtime import create_runtime
    from jacobian.runtime.model import JacobianRuntime

    globals().update(
        {
            "Context": Context,
            "JacobianRuntime": JacobianRuntime,
        }
    )

    selected_authority = _selected_checker_authority(checker_authority)
    configured_root = _configured_root(state_dir)
    runtime = (
        None
        if tenant_isolation
        else create_runtime(
            configured_root,
            checker_authority=selected_authority,
            capability_adapter_entrypoints=capability_adapter_entrypoints,
            capability_exclusions=capability_exclusions,
            capability_policy=capability_policy,
        )
    )
    tenant_router = (
        TenantRuntimeRouter(
            configured_root,
            checker_authority=selected_authority,
            allow_anonymous=allow_anonymous,
            anonymous_tenant_id=anonymous_tenant_id,
            capability_adapter_entrypoints=capability_adapter_entrypoints,
            capability_policy=capability_policy,
            max_tenant_runtimes=(
                DEFAULT_MAX_TENANT_RUNTIMES
                if max_tenant_runtimes is None
                else max_tenant_runtimes
            ),
        )
        if tenant_isolation
        else None
    )

    @asynccontextmanager
    async def lifespan(server: MCPServer[AppState]) -> AsyncIterator[AppState]:
        async with _runtime_lifespan(
            server,
            runtime=runtime,
            tenant_router=tenant_router,
        ) as state:
            yield state

    server: MCPServer[AppState] = MCPServer(
        name="jacobian",
        title="Jacobian Mathematical Workbench",
        description=SERVER_DESCRIPTION,
        instructions=SERVER_INSTRUCTIONS,
        version=__version__,
        lifespan=lifespan,
        token_verifier=token_verifier,
        auth=auth,
        extensions=[JacobianCoreExtension(runtime, tenant_router)],
    )

    _register_resources_and_prompts(server, runtime, tenant_router)
    return server


def _register_resources_and_prompts(
    server: Any,
    runtime: JacobianRuntime | None,
    tenant_router: Any,
) -> None:
    """Register all MCP resource and prompt handlers on the server."""

    @server.resource(  # type: ignore[untyped-decorator]
        "artifact://sha256/{digest}",
        name="artifact",
        description="Read an immutable artifact manifest and payload.",
        mime_type="application/json",
    )
    async def artifact_resource(
        digest: str,
    ) -> str:
        active_runtime = _resource_runtime(runtime, tenant_router)
        artifact = await asyncio.to_thread(
            active_runtime.core.store.get,
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

    @server.resource(  # type: ignore[untyped-decorator]
        "experiment://{experiment_id}",
        name="experiment",
        description="Read the latest durable experiment snapshot.",
        mime_type="application/json",
    )
    async def experiment_resource(
        experiment_id: str,
    ) -> str:
        active_runtime = _resource_runtime(runtime, tenant_router)
        snapshot = await asyncio.to_thread(
            active_runtime.services.experiment_router.inspect,
            f"experiment://{experiment_id}",
        )
        return json.dumps(
            snapshot.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )

    @server.resource(  # type: ignore[untyped-decorator]
        "experiment://{experiment_id}/accounting",
        name="experiment-accounting",
        description="Read durable enumeration accounting and assurance labels.",
        mime_type="application/json",
    )
    async def experiment_accounting_resource(
        experiment_id: str,
    ) -> str:
        active_runtime = _resource_runtime(runtime, tenant_router)
        snapshot = await asyncio.to_thread(
            active_runtime.services.experiment_router.inspect,
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

    @server.resource(  # type: ignore[untyped-decorator]
        "experiment://{experiment_id}/scope",
        name="experiment-scope",
        description="Read the current enumeration scope artifact, when available.",
        mime_type="application/json",
    )
    async def experiment_scope_resource(
        experiment_id: str,
    ) -> str:
        active_runtime = _resource_runtime(runtime, tenant_router)
        snapshot = await asyncio.to_thread(
            active_runtime.services.experiment_router.inspect,
            f"experiment://{experiment_id}",
        )
        return await asyncio.to_thread(
            _experiment_scope_content,
            active_runtime,
            snapshot,
        )

    @server.resource(  # type: ignore[untyped-decorator]
        "experiment://{experiment_id}/archive",
        name="experiment-archive",
        description="Read the immutable archive manifest and page handles.",
        mime_type="application/json",
    )
    async def experiment_archive_resource(
        experiment_id: str,
    ) -> str:
        active_runtime = _resource_runtime(runtime, tenant_router)
        snapshot = await asyncio.to_thread(
            active_runtime.services.experiment_router.inspect,
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
            active_runtime.core.store.get,
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

    @server.prompt(  # type: ignore[untyped-decorator]
        name="jacobian-discover",
        title="Discover Jacobian capabilities",
        description=(
            "Guide capability discovery without choosing the agent's mathematical "
            "research strategy."
        ),
    )
    def jacobian_discover_prompt(
        task: Annotated[
            str,
            Field(description="The mathematical task or desired outcome."),
        ],
    ) -> str:
        return discovery_prompt(task)

    @server.prompt(  # type: ignore[untyped-decorator]
        name="jacobian-check-evidence",
        title="Check mathematical evidence with Jacobian",
        description=(
            "Guide selection and use of an installed independent checker without "
            "promoting unverified evidence."
        ),
    )
    def jacobian_check_evidence_prompt(
        claim: Annotated[
            str,
            Field(description="The exact mathematical claim to check."),
        ],
        artifact_uri: Annotated[
            str | None,
            Field(description="Optional artifact:// URI carrying candidate evidence."),
        ] = None,
    ) -> str:
        return evidence_check_prompt(claim, artifact_uri)


async def capability_describe(
    capability_id: Annotated[
        str | None,
        Field(
            description=(
                "Exact installed ID; cannot be combined with discovery filters."
            )
        ),
    ] = None,
    query: Annotated[
        str | None,
        Field(
            min_length=1,
            max_length=512,
            description=("Mathematical outcome to find; no capability ID is required."),
        ),
    ] = None,
    domain: Annotated[
        str | None,
        Field(
            pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,127}$",
            description=(
                "Optional domain tag filter, such as universal_algebra, graph, "
                "polynomial, or lean."
            ),
        ),
    ] = None,
    mode: Annotated[
        CapabilityMode | None,
        Field(description="Optional EXPLORE or VERIFY capability filter."),
    ] = None,
    input_kind: Annotated[
        CapabilityInputKind | None,
        Field(description=("Input boundary used to reject incompatible routes.")),
    ] = None,
    artifact_type: Annotated[
        str | None,
        Field(
            pattern=r"^artifact://sha256/[0-9a-f]{64}$",
            description=(
                "Exact schema_uri from the stored artifact manifest; requires "
                "TYPED_ARTIFACT."
            ),
        ),
    ] = None,
    limit: Annotated[
        StrictInt | None,
        Field(
            ge=1,
            le=20,
            description=(
                "Maximum compact discovery matches; defaults to 5. Start with "
                "5 and inspect only the strongest one or two candidates."
            ),
        ),
    ] = None,
    cursor: Annotated[
        str | None,
        Field(
            max_length=128,
            pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$",
            description=(
                "Opaque continuation ID from next_cursor. Reuse the same query, "
                "domain, mode, input kind, artifact type, and limit."
            ),
        ),
    ] = None,
    view: Annotated[
        CapabilityDescriptionView,
        Field(
            description=(
                "Exact-lookup projection. SUMMARY is the small agent-facing "
                "default for judging fit. CONTRACT adds the validation-equivalent "
                "input schema, runtime identity, related operations, and validated "
                "invocation examples; request it before invoking. FULL returns "
                "the complete installed descriptor for audit or client generation. "
                "Omit for discovery."
            )
        ),
    ] = "SUMMARY",
    ctx: Context[AppState, Any] | None = None,
) -> dict[str, Any]:
    active_runtime = _runtime(ctx)
    search_arguments = (
        query,
        domain,
        mode,
        input_kind,
        artifact_type,
        limit,
        cursor,
    )
    if capability_id is not None and any(
        argument is not None for argument in search_arguments
    ):
        raise AgentRecoveryError(
            "capability_id is an exact lookup and cannot be combined with query, "
            "domain, mode, input_kind, artifact_type, limit, or cursor. Use one "
            "discovery call followed by "
            "one exact description call."
        )
    if capability_id is None:
        return _capability_discovery_response(
            active_runtime,
            query=query,
            domain=domain,
            mode=mode,
            input_kind=input_kind,
            artifact_type=artifact_type,
            limit=limit,
            cursor=cursor,
        )
    capability_catalog = active_runtime.core.capabilities.catalog()
    descriptors = {item.capability_id: item for item in capability_catalog.capabilities}
    try:
        descriptor = descriptors[capability_id]
    except KeyError:
        hint = (
            "workspace.* names are direct MCP tools, not capability IDs; call the "
            "workspace tool directly using its published input schema."
            if capability_id.startswith("workspace.")
            else (
                "Call capability.describe with a mathematical query to search "
                "installed capabilities."
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
    response: dict[str, Any] = {
        "kind": "capability",
        "view": view,
        "policy_profile": capability_catalog.policy_profile,
        "policy_digest": capability_catalog.policy_digest,
        "capability": _capability_descriptor_view(descriptor, view=view),
        "scope_rule": _CAPABILITY_SCOPE_RULE,
    }
    if view == "SUMMARY":
        response["next_views"] = {
            "CONTRACT": (
                "Request before invocation for the validation-equivalent input "
                "schema and validated examples."
            ),
            "FULL": (
                "Request only for complete output schema, provider configuration, "
                "licensing, or audit metadata."
            ),
        }
    else:
        response["invocations"] = [
            {
                "name": example.name,
                **(
                    {
                        "description": example.description,
                    }
                    if view == "FULL"
                    else {}
                ),
                "tool": "capability.invoke",
                "arguments": {
                    "capability_id": descriptor.capability_id,
                    "mode": example.mode.value,
                    "payload": example.input,
                },
            }
            for example in descriptor.invocation_examples
        ]
        response.update(_capability_inspection_extensions(capability_id, descriptors))
    if (
        view != "SUMMARY"
        and capability_id == "lean.check"
        and active_runtime.portfolio.lean_checkers
    ):
        response["cache"] = {
            "key": "exact content-addressed certificate and active checker digest",
            "max_entries": 128,
            "warmup_environment_variable": "JACOBIAN_LEAN_WARMUP=1",
            "mathlib_warmup": (
                active_runtime.portfolio.lean.mathlib_warmup_health()
                if active_runtime.portfolio.lean is not None
                else {"status": "UNAVAILABLE", "detail": None}
            ),
        }
    return response


async def capability_invoke(
    capability_id: str,
    payload: dict[str, Any],
    mode: CapabilityMode = CapabilityMode.EXPLORE,
    view: CapabilityInvocationView = "STANDARD",
    ctx: Context[AppState, Any] | None = None,
) -> Annotated[CallToolResult, CapabilityResult]:
    active_runtime = _runtime(ctx)
    result = await _invoke_capability_attempt(
        active_runtime,
        capability_id=capability_id,
        payload=payload,
        mode=mode,
        ctx=ctx,
    )
    return _capability_call_tool_result(result, view=view)


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
    active_runtime = _runtime(ctx)
    return await asyncio.to_thread(
        active_runtime.core.workspaces.open,
        WorkspaceOpenRequest(
            idempotency_key=idempotency_key,
            name=name,
            problem=problem,
            tags=tuple(tags or ()),
        ),
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
    active_runtime = _runtime(ctx)
    return await asyncio.to_thread(
        active_runtime.core.workspaces.write,
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
    active_runtime = _runtime(ctx)
    return await asyncio.to_thread(
        active_runtime.core.workspaces.query,
        WorkspaceQueryRequest(
            workspace_id=workspace_id,
            branch_id=branch_id,
            revision_id=revision_id,
            view=view,
            target_card_id=target_card_id,
            limit=limit,
        ),
    )


def _runtime(ctx: Context[AppState, Any] | None) -> JacobianRuntime:
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
        runtime = state.tenant_router.runtime_for(subject)
        _start_lean_warmup(runtime)
        return runtime
    if state.runtime is None:
        raise AgentRecoveryError(
            "Jacobian is unavailable for this request. Retry once; if it fails "
            "again, inspect the local Jacobian log."
        )
    return state.runtime


def _start_lean_warmup(runtime: JacobianRuntime) -> None:
    if (
        runtime.portfolio.lean is not None
        and os.environ.get("JACOBIAN_LEAN_WARMUP") == "1"
    ):
        runtime.portfolio.lean.start_mathlib_warmup()


def _resource_runtime(
    runtime: JacobianRuntime | None,
    tenant_router: TenantRuntimeRouter | None,
) -> JacobianRuntime:
    """Route resources through the same auth context as tools.

    MCP 2.0.0b2 does not inject ``Context`` into static resources, but its HTTP
    authentication middleware still scopes the access token with a contextvar.
    """

    if tenant_router is not None:
        from mcp.server.auth.middleware.auth_context import get_access_token

        access_token = get_access_token()
        subject = access_token.subject if access_token is not None else None
        return tenant_router.runtime_for(subject)
    if runtime is None:
        raise AgentRecoveryError(
            "Jacobian is unavailable for this resource request. Retry once; if it "
            "fails again, inspect the local Jacobian log."
        )
    return runtime


def _configured_root(state_dir: str | Path | None) -> Path:
    if state_dir is not None:
        return Path(state_dir)
    return Path(os.environ.get("JACOBIAN_STATE_DIR", ".jacobian"))


def _public_tool_error(tool_name: str, exc: Exception) -> str:
    from jacobian.adapters.mcp.remote import (
        AuthenticationError,
        TenantRuntimeLimitError,
    )
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
    elif isinstance(tool_error, TenantRuntimeLimitError):
        code = "TENANT_KERNEL_LIMIT"
        message = str(tool_error)
        hint = (
            "Retry on another server instance or ask the operator to raise the limit."
        )
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


def _experiment_scope_content(runtime: JacobianRuntime, snapshot: Any) -> str:
    scope_uri = getattr(snapshot, "scope_uri", None)
    if scope_uri is None:
        return json.dumps(
            {
                "experiment_uri": snapshot.experiment_uri,
                "scope_uri": None,
            },
            sort_keys=True,
        )
    scope = runtime.core.store.get(scope_uri)
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


if __name__ == "__main__":
    from jacobian.adapters.mcp.cli import main

    main()
