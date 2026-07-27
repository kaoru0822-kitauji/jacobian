"""Codex JSONL telemetry parsing shared by executable evaluations."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_PARAMETER_ERROR_CODES = frozenset(
    {
        -32602,
        "INVALID_ARGUMENT",
        "INVALID_CONSTRAINT_RANGE",
        "INVALID_PARAMS",
        "INVALID_REQUEST",
        "SCHEMA_VALIDATION",
        "invalid_params",
    }
)


def _contains_value(value: object, *, field: str, accepted: set[object]) -> bool:
    if isinstance(value, Mapping):
        candidate = value.get(field)
        if isinstance(candidate, str | int | float | bool | type(None)) and (
            candidate in accepted
        ):
            return True
        return any(
            _contains_value(item, field=field, accepted=accepted)
            for item in value.values()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(
            _contains_value(item, field=field, accepted=accepted) for item in value
        )
    return False


def _mcp_text_payload(item: Mapping[str, Any]) -> dict[str, Any] | None:
    result = item.get("result")
    content = result.get("content") if isinstance(result, Mapping) else None
    if not isinstance(content, list):
        return None
    for block in content:
        if not isinstance(block, Mapping) or not isinstance(block.get("text"), str):
            continue
        try:
            payload = json.loads(block["text"])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _mcp_response_bytes(item: Mapping[str, Any]) -> int:
    result = item.get("result")
    try:
        encoded = json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        return 0
    return len(encoded)


def _mcp_call_signature(tool: str, arguments: object) -> tuple[str, str]:
    try:
        encoded = json.dumps(
            arguments,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        encoded = b"unserializable"
    return tool, f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def parse_agent_transcript(path: Path) -> dict[str, Any]:
    """Return calls, usage, failures, and successful capability dataflow."""

    mcp_calls: list[str] = []
    successful_calls: list[str] = []
    capability_attempt_ids: list[str] = []
    capability_ids: list[str] = []
    capability_invocations: list[dict[str, Any]] = []
    shell_calls: list[str] = []
    usage: dict[str, Any] | None = None
    tool_error_count = 0
    parameter_error_count = 0
    capability_rejection_count = 0
    mcp_response_bytes = 0
    mcp_response_bytes_by_tool: Counter[str] = Counter()
    mcp_call_signatures: Counter[tuple[str, str]] = Counter()
    capability_describe_index_calls = 0
    capability_describe_exact_calls = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "command_execution"
        ):
            command = item.get("command")
            shell_calls.append(command if isinstance(command, str) else "")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "mcp_tool_call"
            and isinstance(item.get("tool"), str)
        ):
            tool = item["tool"]
            mcp_calls.append(tool)
            arguments = item.get("arguments")
            response_bytes = _mcp_response_bytes(item)
            mcp_response_bytes += response_bytes
            mcp_response_bytes_by_tool[tool] += response_bytes
            mcp_call_signatures[_mcp_call_signature(tool, arguments)] += 1
            if tool == "capability.describe":
                if isinstance(arguments, Mapping) and isinstance(
                    arguments.get("capability_id"), str
                ):
                    capability_describe_exact_calls += 1
                else:
                    capability_describe_index_calls += 1
            if (
                tool == "capability.invoke"
                and isinstance(arguments, Mapping)
                and isinstance(arguments.get("capability_id"), str)
            ):
                capability_attempt_ids.append(arguments["capability_id"])
            result = item.get("result")
            response = _mcp_text_payload(item)
            failed = bool(
                item.get("status") in {"error", "failed"}
                or item.get("error")
                or (isinstance(result, Mapping) and result.get("isError") is True)
                or (
                    isinstance(response, Mapping)
                    and isinstance(response.get("error"), Mapping)
                )
                or _contains_value(
                    item,
                    field="status",
                    accepted={"CANCELLED", "ERROR", "TIMEOUT"},
                )
            )
            if failed:
                tool_error_count += 1
            else:
                successful_calls.append(tool)
                if (
                    tool == "capability.invoke"
                    and isinstance(response, Mapping)
                    and _contains_value(
                        response.get("output"),
                        field="status",
                        accepted={"REJECTED"},
                    )
                ):
                    capability_rejection_count += 1
                execution = (
                    response.get("execution") if isinstance(response, Mapping) else None
                )
                if (
                    tool == "capability.invoke"
                    and isinstance(arguments, Mapping)
                    and isinstance(arguments.get("capability_id"), str)
                    and isinstance(response, Mapping)
                    and response.get("capability_id") == arguments["capability_id"]
                    and isinstance(execution, Mapping)
                    and execution.get("status") == "COMPLETED"
                ):
                    capability_ids.append(arguments["capability_id"])
                    capability_invocations.append(
                        {
                            "capability_id": arguments["capability_id"],
                            "input": arguments.get("payload"),
                            "output": response.get("output"),
                            "artifact_uris": response.get("artifact_uris"),
                            "assurance": response.get("assurance"),
                            "completeness": response.get("completeness"),
                        }
                    )
            if _contains_value(
                item,
                field="code",
                accepted=set(_PARAMETER_ERROR_CODES),
            ):
                parameter_error_count += 1
        if event.get("type") == "turn.completed" and isinstance(
            event.get("usage"), dict
        ):
            usage = event["usage"]
    return {
        "mcp_calls": mcp_calls,
        "shell_calls": shell_calls,
        "usage": usage,
        "tool_error_count": tool_error_count,
        "parameter_error_count": parameter_error_count,
        "capability_rejection_count": capability_rejection_count,
        "successful_tool_calls": successful_calls,
        "capability_attempt_ids": capability_attempt_ids,
        "capability_ids": capability_ids,
        "capability_invocations": capability_invocations,
        "mcp_response_bytes": mcp_response_bytes,
        "mcp_response_bytes_by_tool": dict(sorted(mcp_response_bytes_by_tool.items())),
        "repeated_mcp_call_count": sum(
            count - 1 for count in mcp_call_signatures.values() if count > 1
        ),
        "repeated_mcp_calls": [
            {
                "tool": tool,
                "argument_digest": argument_digest,
                "count": count,
            }
            for (tool, argument_digest), count in sorted(mcp_call_signatures.items())
            if count > 1
        ],
        "capability_describe_index_calls": capability_describe_index_calls,
        "capability_describe_exact_calls": capability_describe_exact_calls,
    }
