"""JSON projections and capability discovery views for the MCP adapter."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
from contextlib import suppress
from typing import TYPE_CHECKING, Any, Literal, cast

from mcp_types import CallToolResult, TextContent

from jacobian.adapters.mcp.constants import (
    CAPABILITY_DISCOVERY_RESPONSE_BYTE_LIMIT,
    CAPABILITY_STANDARD_FIELD_BYTE_LIMIT,
    CAPABILITY_STANDARD_INCLUDED_FIELD_BYTE_LIMIT,
    CAPABILITY_STANDARD_OUTPUT_BYTE_LIMIT,
)
from jacobian.bounded_process import bounded_process_cancellation
from jacobian.canonical import canonicalize_json
from jacobian.capabilities import CapabilityDiscoveryCursorError
from jacobian.contracts.capabilities import (
    CapabilityDescriptor,
    CapabilityDiscoveryRequest,
    CapabilityInputKind,
    CapabilityMode,
    CapabilityRequest,
    CapabilityResult,
)

_LOGGER = logging.getLogger(__name__)
CapabilityDescriptionView = Literal["SUMMARY", "CONTRACT", "FULL"]
CapabilityInvocationView = Literal["SUMMARY", "STANDARD", "FULL"]

if TYPE_CHECKING:
    from jacobian.runtime.model import JacobianRuntime


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
