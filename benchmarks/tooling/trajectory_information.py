"""Collect and analyze bounded observable Jacobian trajectory information.

This operator-run study deliberately excludes hidden reasoning, ATIF
``reasoning_content``, tool arguments, and tool results from its derived
dataset. Raw Codex JSONL and task workspaces remain host-local inputs to the
post-run projection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import socket
import sys
import threading
import time
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from random import Random
from typing import Any

from benchmarks.tooling.command_runner import (
    ToolCommandRequest,
    ToolCommandResult,
    ToolCommandStatus,
    git_head_sha,
    git_tracked_worktree_is_clean,
    operator_environment,
    run_operator_command,
    run_tool_command,
)
from benchmarks.tooling.errors import HarborSuiteError
from benchmarks.tooling.harbor_suite import ROOT, get_suite, task_digest
from benchmarks.validation.mathematical_benchmarks_v1._verifier import _run_verifier

_DEFAULT_CONFIG = ROOT / "benchmarks/config/trajectory-information-v1.json"
_LEXICON = (
    "error",
    "fail",
    "retry",
    "fallback",
    "verify",
    "checked",
    "found",
    "compute",
    "wrote",
    "complete",
    "cannot",
    "timeout",
)
_SUMMARY_MAX_BYTES = 512
_SUMMARY_MAX_MESSAGES = 32
_SUMMARY_TOTAL_MAX_BYTES = 8192
_SERVER_EVENT_MARKER = re.compile(r"\bMCP (?:tool call|capability attempt)\b")
_TOOL_CALL = re.compile(
    r"\bMCP tool call tool=(math\.(?:find|run))\b"
    r".{0,512}?\bstatus=(success|error)\b"
    r".{0,512}?\brequest_digest=([0-9a-f]{16}|none)\b"
    r".{0,512}?\btrace_digest=([0-9a-f]{8}|none)\b"
    r".{0,512}?\btrace_source=([^\s]+)\b"
    r".{0,512}?\bduration_ms=([0-9]+(?:\.[0-9]+)?)\b"
    r".{0,512}?\bresponse_bytes=(-?[0-9]+)\b"
    r".{0,512}?\bargument_digest=(sha256:(?:[0-9a-f]\s*){64})",
    re.DOTALL,
)
_CAPABILITY_ATTEMPT = re.compile(
    r"\bMCP capability attempt request_digest=([0-9a-f]{16}|none)\b"
    r".{0,512}?\btrace_digest=([0-9a-f]{8}|none)\b"
    r".{0,512}?\btrace_source=([^\s]+)\b"
    r".{0,512}?\bcapability_id=([^\s]+)\b"
    r".{0,512}?\bcapability_version=([^\s]+)\b"
    r".{0,512}?\bexecution_status=([A-Z_]+)\b"
    r".{0,512}?\bassurance=([^\s]+)\b"
    r".{0,512}?\bdiagnostic_codes=([^\s]+)\b"
    r".{0,512}?\battempt_duration_ms=([0-9]+(?:\.[0-9]+)?)\b"
    r".{0,512}?\boperation_runtime_ms=([^\s]+)\b"
    r".{0,512}?\bresponse_bytes=(-?[0-9]+)\b"
    r".{0,512}?\bargument_digest=(sha256:(?:[0-9a-f]\s*){64})",
    re.DOTALL,
)
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\bBearer\s+[^\s,;]+"), "[REDACTED_BEARER]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"/(?:Users|home)/[^/\s]+"), "[REDACTED_HOME]"),
    (
        re.compile(r"/(?:private/)?tmp/[^\s)\]]+|/var/folders/[^\s)\]]+"),
        "[REDACTED_TEMP_PATH]",
    ),
)
_CONDITIONS = ("x+y", "x+y+b", "x+y+tau_tools", "x+y+b+tau_tools")
_TARGETS = (
    "next_tool_action_class",
    "checker_rejection_recovery",
    "mathematical_milestone",
    "terminal_verifier_success",
    "tool_use_failure_class",
)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HarborSuiteError(f"unable to read JSON {path}: {exc}") from exc


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _json_digest(value: object) -> str:
    return _sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def _collector_digest() -> str:
    return _sha256(Path(__file__).resolve(strict=True))


def _config(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    if not isinstance(value, dict) or value.get("schema_version") != "1":
        raise HarborSuiteError("trajectory study config must be a schema-v1 object")
    if value.get("status") != "FROZEN_BEFORE_MODEL_RUNS":
        raise HarborSuiteError("trajectory study config is not frozen before runs")
    return value


def _selected_tasks(
    config: Mapping[str, Any], selected: set[str]
) -> list[dict[str, str]]:
    dataset = config.get("dataset")
    tasks = dataset.get("tasks") if isinstance(dataset, Mapping) else None
    if not isinstance(tasks, list):
        raise HarborSuiteError("study config has no task list")
    values: list[dict[str, str]] = []
    for item in tasks:
        if not (
            isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and isinstance(item.get("digest"), str)
        ):
            raise HarborSuiteError("study task records must bind IDs and digests")
        if not selected or item["id"] in selected:
            values.append(item)
    unknown = selected - {item["id"] for item in values}
    if unknown:
        raise HarborSuiteError(f"unknown selected tasks: {sorted(unknown)}")
    return values


def _validate_task_digest(task: Path, expected: str) -> None:
    actual = "sha256:" + task_digest(task)
    if actual != expected:
        raise HarborSuiteError(
            f"task digest drift for {task.name}: expected {expected}, got {actual}"
        )


def _copy_visible_task(task: Path, workspace: Path) -> None:
    workspace.mkdir(parents=True)
    shutil.copy2(task / "instruction.md", workspace / "instruction.md")
    shutil.copy2(task / "environment/input.json", workspace / "input.json")
    shutil.copy2(
        task / "environment/submission_schema.json",
        workspace / "submission_schema.json",
    )


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run_server_command(
    request: ToolCommandRequest, results: list[ToolCommandResult]
) -> None:
    results.append(run_tool_command(request))


def _wait_for_port(
    port: int,
    worker: threading.Thread,
    results: Sequence[ToolCommandResult],
) -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if not worker.is_alive():
            status = results[0].status if results else "UNKNOWN"
            raise HarborSuiteError(
                f"Jacobian MCP server exited during startup: {status}"
            )
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.2)
    raise HarborSuiteError("Jacobian MCP server did not become ready")


def _server_command(*, state_dir: Path, port: int, trial_id: str) -> tuple[str, ...]:
    code = (
        "import logging,sys;"
        "logging.basicConfig(level=logging.INFO,stream=sys.stderr,"
        "format='%(levelname)s %(message)s');"
        "from jacobian.adapters.mcp.cli import main;main()"
    )
    return (
        sys.executable,
        "-c",
        code,
        "--transport",
        "streamable-http",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--allow-anonymous",
        "--anonymous-tenant-id",
        trial_id,
        "--capability-policy-profile",
        "COMPUTE_VERIFY_NO_RETRIEVAL",
        "--state-dir",
        str(state_dir),
    )


def _codex_arguments(
    *, workspace: Path, model: str, reasoning_effort: str, mcp_url: str, prompt: str
) -> tuple[str, ...]:
    return (
        "-a",
        "never",
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--ignore-user-config",
        "-C",
        str(workspace),
        "-s",
        "workspace-write",
        "--json",
        "-m",
        model,
        "-c",
        f"model_reasoning_effort={json.dumps(reasoning_effort)}",
        "-c",
        f"mcp_servers.jacobian.url={json.dumps(mcp_url)}",
        "-c",
        'mcp_servers.jacobian.default_tools_approval_mode="approve"',
        "--enable",
        "unified_exec",
        prompt,
    )


def _run_trial(
    *, task: Path, task_record: Mapping[str, str], config: Mapping[str, Any], root: Path
) -> dict[str, Any]:
    trial_id = task.name
    trial = root / trial_id
    if trial.exists():
        raise HarborSuiteError(f"refusing to overwrite trial: {trial}")
    trial.mkdir(parents=True)
    workspace = trial / "workspace"
    verifier_logs = trial / "verifier"
    state_dir = trial / "state"
    verifier_logs.mkdir()
    state_dir.mkdir()
    _copy_visible_task(task, workspace)
    port = _free_port()
    server_stdout = trial / "server.stdout"
    server_log = trial / "server.log"
    server_environment = dict(operator_environment(include=("PATH",)))
    server_environment.update(
        {
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
        }
    )
    started = time.monotonic()
    with server_stdout.open("wb") as stdout_handle, server_log.open("wb") as log_handle:
        server_command = _server_command(
            state_dir=state_dir, port=port, trial_id=trial_id
        )
        server_cancel = threading.Event()
        server_results: list[ToolCommandResult] = []
        server_request = ToolCommandRequest(
            executable=server_command[0],
            arguments=server_command[1:],
            environment=server_environment,
            cwd=str(ROOT),
            timeout_seconds=float(config["runtime"]["task_timeout_seconds"]) + 180,
            stdout_limit_bytes=8 * 1024 * 1024,
            stderr_limit_bytes=32 * 1024 * 1024,
            cancellation_event=server_cancel,
            stdout_sink=stdout_handle.write,
            stderr_sink=log_handle.write,
        )
        server_worker = threading.Thread(
            target=_run_server_command,
            args=(server_request, server_results),
            daemon=True,
        )
        server_worker.start()
        try:
            _wait_for_port(port, server_worker, server_results)
            runtime = config["runtime"]
            environment = dict(
                operator_environment(
                    include=(
                        "HOME",
                        "PATH",
                        "CODEX_HOME",
                        "HTTP_PROXY",
                        "HTTPS_PROXY",
                        "ALL_PROXY",
                        "http_proxy",
                        "https_proxy",
                        "all_proxy",
                    )
                )
            )
            environment.update(
                {
                    "NO_PROXY": "127.0.0.1,localhost",
                    "no_proxy": "127.0.0.1,localhost",
                }
            )
            result = run_operator_command(
                "codex",
                _codex_arguments(
                    workspace=workspace,
                    model=runtime["model"],
                    reasoning_effort=runtime["reasoning_effort"],
                    mcp_url=f"http://127.0.0.1:{port}/mcp",
                    prompt=config["prompt"],
                ),
                cwd=workspace,
                timeout_seconds=float(runtime["task_timeout_seconds"]),
                stdout_limit_bytes=32 * 1024 * 1024,
                stderr_limit_bytes=4 * 1024 * 1024,
                environment=environment,
            )
        finally:
            server_cancel.set()
            server_worker.join(timeout=30)
            if server_worker.is_alive():
                raise HarborSuiteError(
                    "Jacobian MCP server did not stop within the tooling deadline"
                )
            if not server_results:
                raise HarborSuiteError("Jacobian MCP server produced no command result")
            server_result = server_results[0]
            if server_result.status not in {
                ToolCommandStatus.CANCELLED,
                ToolCommandStatus.EXITED,
            }:
                raise HarborSuiteError(
                    f"Jacobian MCP server ended with {server_result.status}"
                )
            if server_result.stdout_exceeded or server_result.stderr_exceeded:
                raise HarborSuiteError("Jacobian MCP server output exceeded its bound")
    transcript = trial / "codex.jsonl"
    stderr = trial / "codex.stderr"
    transcript.write_bytes(result.stdout)
    stderr.write_bytes(result.stderr)
    verifier = _run_verifier(task, workspace, verifier_logs)
    final_message = _final_agent_message(result.stdout)
    artifacts = _workspace_artifacts(workspace)
    record = {
        "schema_version": "1",
        "trial_id": trial_id,
        "task_digest": task_record["digest"],
        "source_sha": git_head_sha(ROOT),
        "command": {
            "status": result.status,
            "exit_code": result.exit_code,
            "diagnostic": result.diagnostic,
            "stdout_exceeded": result.stdout_exceeded,
            "stderr_exceeded": result.stderr_exceeded,
            "elapsed_seconds": round(time.monotonic() - started, 6),
        },
        "verifier": {"reward": verifier.reward, "details": dict(verifier.details)},
        "final_message_sha256": _sha256_bytes(final_message.encode("utf-8")),
        "final_message_utf8_bytes": len(final_message.encode("utf-8")),
        "workspace_artifacts": artifacts,
        "raw_artifacts": {
            "transcript": {"path": transcript.name, "sha256": _sha256(transcript)},
            "stderr": {"path": stderr.name, "sha256": _sha256(stderr)},
            "server_log": {"path": server_log.name, "sha256": _sha256(server_log)},
        },
    }
    _write_json(trial / "trial.json", record)
    return record


def _workspace_artifacts(workspace: Path) -> list[dict[str, object]]:
    values = []
    for relative in ("submission.json",):
        path = workspace / relative
        if path.is_file() and not path.is_symlink():
            values.append(
                {
                    "path": relative,
                    "sha256": _sha256(path),
                    "bytes": path.stat().st_size,
                }
            )
    evidence = workspace / "evidence"
    if evidence.is_dir() and not evidence.is_symlink():
        for path in sorted(evidence.rglob("*")):
            if path.is_file() and not path.is_symlink():
                values.append(
                    {
                        "path": path.relative_to(workspace).as_posix(),
                        "sha256": _sha256(path),
                        "bytes": path.stat().st_size,
                    }
                )
    return values


def _jsonl_events(payload: bytes) -> list[dict[str, Any]]:
    values = []
    for line in payload.decode("utf-8", errors="strict").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            values.append(value)
    return values


def _final_agent_message(payload: bytes) -> str:
    messages = []
    for event in _jsonl_events(payload):
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "agent_message"
            and isinstance(item.get("text"), str)
        ):
            messages.append(item["text"])
    return messages[-1] if messages else ""


def _bounded_message(text: str) -> tuple[str, int, bool, int]:
    value = text.strip()
    redactions = 0
    for pattern, replacement in _REDACTIONS:
        value, count = pattern.subn(replacement, value)
        redactions += count
    encoded = value.encode("utf-8")
    if len(encoded) <= _SUMMARY_MAX_BYTES:
        return value, len(encoded), False, redactions
    return (
        encoded[:_SUMMARY_MAX_BYTES].decode("utf-8", errors="ignore"),
        len(encoded),
        True,
        redactions,
    )


def _safe_int(value: object) -> int:
    return value if type(value) is int else 0


def _safe_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    result = float(value)
    return result if math.isfinite(result) else 0.0


def _safe_length(value: object) -> int:
    return len(value) if isinstance(value, list | tuple) else 0


def _visible_messages(payload: bytes) -> tuple[list[dict[str, object]], list[int]]:
    raw: list[tuple[int, str]] = []
    tool_message_counts: list[int] = []
    for position, event in enumerate(_jsonl_events(payload), start=1):
        item = event.get("item")
        if not (event.get("type") == "item.completed" and isinstance(item, dict)):
            continue
        if item.get("type") == "agent_message" and isinstance(item.get("text"), str):
            raw.append((position, item["text"]))
        elif item.get("type") == "mcp_tool_call" and item.get("tool") in {
            "math.find",
            "math.run",
        }:
            tool_message_counts.append(len(raw))
    if raw:
        raw = raw[:-1]
    summaries: list[dict[str, object]] = []
    retained_bytes = 0
    for position, text in raw[:_SUMMARY_MAX_MESSAGES]:
        bounded, original_bytes, truncated, redactions = _bounded_message(text)
        remaining = _SUMMARY_TOTAL_MAX_BYTES - retained_bytes
        if remaining <= 0:
            break
        encoded = bounded.encode("utf-8")
        if len(encoded) > remaining:
            bounded = encoded[:remaining].decode("utf-8", errors="ignore")
            truncated = True
        retained_bytes += len(bounded.encode("utf-8"))
        summaries.append(
            {
                "source_position": position,
                "text": bounded,
                "original_utf8_bytes": original_bytes,
                "truncated": truncated,
                "redaction_count": redactions,
            }
        )
    return summaries, tool_message_counts


def _server_events(payload: str) -> tuple[list[dict[str, object]], dict[str, int]]:
    events: list[tuple[int, dict[str, object]]] = []
    for match in _TOOL_CALL.finditer(payload):
        (
            tool,
            status,
            request_digest,
            trace_digest,
            trace_source,
            duration_ms,
            response_bytes,
            argument_digest,
        ) = match.groups()
        events.append(
            (
                match.start(),
                {
                    "kind": "TOOL_CALL",
                    "tool": tool,
                    "status": status,
                    "request_digest": request_digest,
                    "trace_digest": trace_digest,
                    "trace_source": trace_source,
                    "duration_ms": float(duration_ms),
                    "response_bytes": int(response_bytes),
                    "argument_digest": re.sub(r"\s", "", argument_digest),
                },
            )
        )
    for match in _CAPABILITY_ATTEMPT.finditer(payload):
        (
            request_digest,
            trace_digest,
            trace_source,
            capability_id,
            capability_version,
            execution_status,
            assurance,
            diagnostic_codes,
            attempt_duration_ms,
            operation_runtime_ms,
            response_bytes,
            argument_digest,
        ) = match.groups()
        events.append(
            (
                match.start(),
                {
                    "kind": "CAPABILITY_ATTEMPT",
                    "request_digest": request_digest,
                    "trace_digest": trace_digest,
                    "trace_source": trace_source,
                    "capability_id": capability_id,
                    "capability_version": capability_version,
                    "execution_status": execution_status,
                    "assurance": assurance,
                    "diagnostic_codes": (
                        []
                        if diagnostic_codes in {"none", "-"}
                        else diagnostic_codes.split(",")[:8]
                    ),
                    "attempt_duration_ms": float(attempt_duration_ms),
                    "operation_runtime_ms": (
                        None
                        if operation_runtime_ms == "none"
                        else float(operation_runtime_ms)
                    ),
                    "response_bytes": int(response_bytes),
                    "argument_digest": re.sub(r"\s", "", argument_digest),
                },
            )
        )
    ordered = [event for _, event in sorted(events, key=lambda item: item[0])]
    candidates = len(_SERVER_EVENT_MARKER.findall(payload))
    return ordered, {"candidates": candidates, "recorded": len(ordered)}


def _task_features(task: Path) -> dict[str, float]:
    task_toml = (task / "task.toml").read_text(encoding="utf-8")
    instruction = (task / "instruction.md").read_text(encoding="utf-8")
    input_bytes = (task / "environment/input.json").read_bytes()
    schema = _read_json(task / "environment/submission_schema.json")
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    return {
        "x:instruction_bytes": float(len(instruction.encode("utf-8"))),
        "x:instruction_lines": float(len(instruction.splitlines())),
        "x:input_bytes": float(len(input_bytes)),
        "x:schema_properties": float(
            len(properties) if isinstance(properties, dict) else 0
        ),
        "x:requires_verification_record": float(
            "verification_record_uri" in properties
        ),
        "x:difficulty_hard": float('difficulty = "hard"' in task_toml),
        "x:difficulty_medium": float('difficulty = "medium"' in task_toml),
    }


def _y_features(
    *, record: Mapping[str, Any], final_message: str, target: str
) -> dict[str, float]:
    verifier = record.get("verifier", {})
    details = verifier.get("details", {}) if isinstance(verifier, Mapping) else {}
    features = {
        "y:final_message_bytes": float(len(final_message.encode("utf-8"))),
        "y:final_message_lines": float(len(final_message.splitlines())),
        "y:workspace_artifact_count": float(len(record.get("workspace_artifacts", []))),
    }
    for key, value in sorted(details.items() if isinstance(details, Mapping) else ()):
        if target == "mathematical_milestone" and key == "correctness":
            continue
        if target == "terminal_verifier_success":
            continue
        if isinstance(value, bool) or (
            isinstance(value, int | float) and math.isfinite(float(value))
        ):
            features[f"y:verifier:{key}"] = float(value)
    if target != "terminal_verifier_success" and isinstance(verifier, Mapping):
        reward = verifier.get("reward")
        if isinstance(reward, int | float) and not isinstance(reward, bool):
            features["y:verifier_reward"] = float(reward)
    return features


def _b_features(messages: Sequence[Mapping[str, object]]) -> dict[str, float]:
    text = "\n".join(str(item["text"]) for item in messages).lower()
    features = {
        "b:message_count": float(len(messages)),
        "b:utf8_bytes": float(len(text.encode("utf-8"))),
        "b:truncated_count": float(sum(bool(item["truncated"]) for item in messages)),
        "b:redaction_count": float(
            sum(_safe_int(item["redaction_count"]) for item in messages)
        ),
    }
    for token in _LEXICON:
        features[f"b:lex:{token}"] = float(
            len(re.findall(rf"\b{re.escape(token)}\w*\b", text))
        )
    return features


def _tool_action(
    event: Mapping[str, object], attempts: Mapping[str, Mapping[str, object]]
) -> str:
    if event.get("tool") == "math.find":
        return "FIND"
    attempt = attempts.get(str(event.get("request_digest")))
    capability_id = (
        attempt.get("capability_id") if isinstance(attempt, Mapping) else None
    )
    return (
        "RUN_CHECKER"
        if isinstance(capability_id, str) and capability_id.endswith(".verify")
        else "RUN_PRODUCER"
    )


def _tau_features(events: Sequence[Mapping[str, object]]) -> dict[str, float]:
    attempts = {
        str(event["request_digest"]): event
        for event in events
        if event.get("kind") == "CAPABILITY_ATTEMPT"
    }
    tools = [event for event in events if event.get("kind") == "TOOL_CALL"]
    actions = [_tool_action(event, attempts) for event in tools]
    features: dict[str, float] = {
        "tau:event_count": float(len(events)),
        "tau:tool_call_count": float(len(tools)),
        "tau:attempt_count": float(len(attempts)),
        "tau:error_count": float(
            sum(event.get("status") == "error" for event in tools)
        ),
        "tau:diagnostic_count": float(
            sum(
                _safe_length(event.get("diagnostic_codes"))
                for event in attempts.values()
            )
        ),
        "tau:duration_log1p_sum": sum(
            math.log1p(
                _safe_float(
                    event.get("duration_ms", event.get("attempt_duration_ms", 0.0))
                )
            )
            for event in events
        ),
        "tau:response_bytes_log1p_sum": sum(
            math.log1p(max(0, _safe_int(event.get("response_bytes"))))
            for event in events
        ),
        "tau:request_digest_available": float(
            sum(event.get("request_digest") != "none" for event in events)
        ),
        "tau:argument_digest_available": float(
            sum(
                str(event.get("argument_digest", "")).startswith("sha256:")
                for event in events
            )
        ),
    }
    for action, count in Counter(actions).items():
        features[f"tau:action:{action}"] = float(count)
    for left, right in pairwise(actions):
        features[f"tau:bigram:{left}>{right}"] = (
            features.get(f"tau:bigram:{left}>{right}", 0.0) + 1.0
        )
    capability_ids = [str(event["capability_id"]) for event in attempts.values()]
    features["tau:unique_capability_count"] = float(len(set(capability_ids)))
    features["tau:unique_domain_count"] = float(
        len({value.split(".", 1)[0] for value in capability_ids})
    )
    features["tau:checker_attempt_count"] = float(
        sum(value.endswith(".verify") for value in capability_ids)
    )
    for event in attempts.values():
        features[f"tau:execution:{event.get('execution_status')}"] = (
            features.get(f"tau:execution:{event.get('execution_status')}", 0.0) + 1.0
        )
        features[f"tau:assurance:{event.get('assurance')}"] = (
            features.get(f"tau:assurance:{event.get('assurance')}", 0.0) + 1.0
        )
    return features


def _checker_label(events: Sequence[Mapping[str, object]]) -> str:
    checkers = [
        event
        for event in events
        if event.get("kind") == "CAPABILITY_ATTEMPT"
        and str(event.get("capability_id", "")).endswith(".verify")
    ]
    if not checkers:
        return "NO_CHECKER"
    rejected = [
        event
        for event in checkers
        if event.get("execution_status") != "COMPLETED"
        or bool(event.get("diagnostic_codes"))
        or event.get("assurance") != "VERIFIED"
    ]
    if not rejected:
        return "SUCCESS_WITHOUT_REJECTION"
    last_rejection = max(events.index(event) for event in rejected)
    recovered = any(
        index > last_rejection
        and event.get("kind") == "CAPABILITY_ATTEMPT"
        and str(event.get("capability_id", "")).endswith(".verify")
        and event.get("execution_status") == "COMPLETED"
        and event.get("assurance") == "VERIFIED"
        and not event.get("diagnostic_codes")
        for index, event in enumerate(events)
    )
    return "REJECTED_RECOVERED" if recovered else "REJECTED_UNRECOVERED"


def _failure_label(events: Sequence[Mapping[str, object]]) -> str:
    tools = [event for event in events if event.get("kind") == "TOOL_CALL"]
    runs = [event for event in tools if event.get("tool") == "math.run"]
    if not tools:
        return "NO_SERVER_TOOL_USE"
    if not runs:
        return "DISCOVERY_ONLY"
    failures = [event for event in runs if event.get("status") != "success"]
    attempts = [event for event in events if event.get("kind") == "CAPABILITY_ATTEMPT"]
    failures.extend(
        event for event in attempts if event.get("execution_status") != "COMPLETED"
    )
    if not failures:
        return "CLEAN_EXECUTION"
    last_failure = max(events.index(event) for event in failures)
    recovered = any(
        index > last_failure
        and event.get("kind") == "TOOL_CALL"
        and event.get("tool") == "math.run"
        and event.get("status") == "success"
        for index, event in enumerate(events)
    )
    return "RECOVERED_AFTER_FAILURE" if recovered else "UNRECOVERED_FAILURE"


@dataclass(frozen=True)
class Row:
    task_id: str
    label: str
    x_y: Mapping[str, float]
    b: Mapping[str, float]
    tau: Mapping[str, float]


def _project_trial(
    task: Path, trial: Path
) -> tuple[dict[str, Any], dict[str, list[Row]]]:
    record = _read_json(trial / "trial.json")
    transcript_path = trial / record["raw_artifacts"]["transcript"]["path"]
    server_path = trial / record["raw_artifacts"]["server_log"]["path"]
    if _sha256(transcript_path) != record["raw_artifacts"]["transcript"]["sha256"]:
        raise HarborSuiteError(f"transcript digest mismatch: {trial.name}")
    if _sha256(server_path) != record["raw_artifacts"]["server_log"]["sha256"]:
        raise HarborSuiteError(f"server-log digest mismatch: {trial.name}")
    transcript = transcript_path.read_bytes()
    final_message = _final_agent_message(transcript)
    messages, message_prefix_counts = _visible_messages(transcript)
    events, coverage = _server_events(server_path.read_text(encoding="utf-8"))
    if coverage["candidates"] != coverage["recorded"]:
        raise HarborSuiteError(f"incomplete server event projection: {trial.name}")
    base_x = _task_features(task)
    rows: dict[str, list[Row]] = defaultdict(list)
    trajectory_labels = {
        "checker_rejection_recovery": _checker_label(events),
        "mathematical_milestone": (
            "REACHED"
            if record["verifier"]["details"].get("correctness") == 1.0
            else "NOT_REACHED"
        ),
        "terminal_verifier_success": (
            "PASS" if record["verifier"]["reward"] == 1.0 else "FAIL"
        ),
        "tool_use_failure_class": _failure_label(events),
    }
    for target, label in trajectory_labels.items():
        rows[target].append(
            Row(
                task_id=task.name,
                label=label,
                x_y={
                    **base_x,
                    **_y_features(
                        record=record, final_message=final_message, target=target
                    ),
                },
                b=_b_features(messages),
                tau=_tau_features(events),
            )
        )
    attempts = {
        str(event["request_digest"]): event
        for event in events
        if event.get("kind") == "CAPABILITY_ATTEMPT"
    }
    tool_events = [event for event in events if event.get("kind") == "TOOL_CALL"]
    for index in range(len(tool_events) + 1):
        label = (
            "TERMINAL"
            if index == len(tool_events)
            else _tool_action(tool_events[index], attempts)
        )
        message_count = (
            message_prefix_counts[index]
            if index < len(message_prefix_counts)
            else len(messages)
        )
        prior_request_digests = {
            str(event.get("request_digest")) for event in tool_events[:index]
        }
        prefix_events = [
            event
            for event in events
            if (event.get("kind") == "TOOL_CALL" and event in tool_events[:index])
            or (
                event.get("kind") == "CAPABILITY_ATTEMPT"
                and str(event.get("request_digest")) in prior_request_digests
            )
        ]
        rows["next_tool_action_class"].append(
            Row(
                task_id=task.name,
                label=label,
                x_y={
                    **base_x,
                    **_y_features(
                        record=record,
                        final_message=final_message,
                        target="next_tool_action_class",
                    ),
                    "xy:prefix_index": float(index),
                },
                b=_b_features(messages[:message_count]),
                tau=_tau_features(prefix_events),
            )
        )
    projection = {
        "trial_id": task.name,
        "status": "COMPLETE",
        "server_event_coverage": coverage,
        "summary_metrics": {
            "message_count": len(messages),
            "utf8_bytes": sum(
                len(str(item["text"]).encode("utf-8")) for item in messages
            ),
            "truncated_count": sum(bool(item["truncated"]) for item in messages),
            "redaction_count": sum(
                _safe_int(item["redaction_count"]) for item in messages
            ),
        },
        "tool_metrics": {
            "event_count": len(events),
            "tool_call_count": sum(
                event.get("kind") == "TOOL_CALL" for event in events
            ),
            "capability_attempt_count": sum(
                event.get("kind") == "CAPABILITY_ATTEMPT" for event in events
            ),
        },
        "labels": trajectory_labels,
    }
    return projection, rows


def _condition_features(row: Row, condition: str) -> dict[str, float]:
    values = dict(row.x_y)
    if "+b" in condition:
        values.update(row.b)
    if "tau_tools" in condition:
        values.update(row.tau)
    return values


def _distance(
    left: Mapping[str, float],
    right: Mapping[str, float],
    ranges: Mapping[str, tuple[float, float]],
) -> float:
    total = 0.0
    for name, (minimum, maximum) in ranges.items():
        scale = maximum - minimum
        if scale <= 0:
            continue
        delta = (left.get(name, 0.0) - right.get(name, 0.0)) / scale
        total += delta * delta
    return math.sqrt(total)


def _predict(train: Sequence[Row], test: Row, condition: str) -> str:
    if not train:
        raise HarborSuiteError("empty training fold")
    vectors = [_condition_features(row, condition) for row in train]
    names = sorted({name for vector in vectors for name in vector})
    ranges = {
        name: (
            min(vector.get(name, 0.0) for vector in vectors),
            max(vector.get(name, 0.0) for vector in vectors),
        )
        for name in names
    }
    test_vector = _condition_features(test, condition)
    neighbors = sorted(
        (
            (_distance(vector, test_vector, ranges), row.task_id, row.label)
            for row, vector in zip(train, vectors, strict=True)
        ),
        key=lambda item: (item[0], item[1], item[2]),
    )[: min(3, len(train))]
    counts = Counter(label for _, _, label in neighbors)
    return sorted(counts, key=lambda label: (-counts[label], label))[0]


def _predictions(rows: Sequence[Row], condition: str) -> list[dict[str, str]]:
    predictions = []
    tasks = sorted({row.task_id for row in rows})
    for held_out in tasks:
        train = [row for row in rows if row.task_id != held_out]
        for row in rows:
            if row.task_id == held_out:
                predictions.append(
                    {
                        "task_id": row.task_id,
                        "truth": row.label,
                        "prediction": _predict(train, row, condition),
                    }
                )
    return predictions


def _descriptive_value(value: float) -> str:
    """Map a numeric feature to one fixed, corpus-independent presence bin."""

    if value == 0:
        return "ZERO"
    if value < 0:
        return "NEGATIVE"
    if value == 1:
        return "ONE"
    if value <= 3:
        return "TWO_OR_THREE"
    return "FOUR_OR_MORE"


def _descriptive_signature(row: Row, condition: str) -> str:
    features = _condition_features(row, condition)
    return _json_digest(
        {name: _descriptive_value(value) for name, value in sorted(features.items())}
    )


def _descriptive_predictions(
    rows: Sequence[Row], condition: str
) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    """Return labeled transductive signature purity and exact contingencies."""

    groups: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        groups[_descriptive_signature(row, condition)].append(row)
    predictions: list[dict[str, str]] = []
    contingencies: list[dict[str, object]] = []
    for signature, members in sorted(groups.items()):
        counts = Counter(row.label for row in members)
        prediction = sorted(counts, key=lambda label: (-counts[label], label))[0]
        predictions.extend(
            {
                "task_id": row.task_id,
                "truth": row.label,
                "prediction": prediction,
            }
            for row in members
        )
        contingencies.append(
            {
                "signature_digest": signature,
                "row_count": len(members),
                "task_count": len({row.task_id for row in members}),
                "label_counts": dict(sorted(counts.items())),
            }
        )
    return predictions, contingencies


def _majority_predictions(rows: Sequence[Row]) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    for held_out in sorted({row.task_id for row in rows}):
        counts = Counter(row.label for row in rows if row.task_id != held_out)
        prediction = sorted(counts, key=lambda label: (-counts[label], label))[0]
        values.extend(
            {"task_id": row.task_id, "truth": row.label, "prediction": prediction}
            for row in rows
            if row.task_id == held_out
        )
    return values


def _task_identity_upper(rows: Sequence[Row]) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    for task_id in sorted({row.task_id for row in rows}):
        counts = Counter(row.label for row in rows if row.task_id == task_id)
        prediction = sorted(counts, key=lambda label: (-counts[label], label))[0]
        values.extend(
            {"task_id": row.task_id, "truth": row.label, "prediction": prediction}
            for row in rows
            if row.task_id == task_id
        )
    return values


def _metrics(predictions: Sequence[Mapping[str, str]]) -> dict[str, float]:
    classes = sorted({item["truth"] for item in predictions})
    if not predictions or not classes:
        return {"macro_f1": 0.0, "balanced_accuracy": 0.0, "accuracy": 0.0}
    f1s = []
    recalls = []
    for label in classes:
        true_positive = sum(
            item["truth"] == label == item["prediction"] for item in predictions
        )
        false_positive = sum(
            item["truth"] != label and item["prediction"] == label
            for item in predictions
        )
        false_negative = sum(
            item["truth"] == label and item["prediction"] != label
            for item in predictions
        )
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1s.append(
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
        recalls.append(recall)
    return {
        "macro_f1": sum(f1s) / len(f1s),
        "balanced_accuracy": sum(recalls) / len(recalls),
        "accuracy": sum(item["truth"] == item["prediction"] for item in predictions)
        / len(predictions),
    }


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(probability * (len(ordered) - 1))))
    return ordered[index]


def _bootstrap_increment(
    predictions: Mapping[str, Mapping[str, Sequence[Mapping[str, str]]]],
    eligible: Sequence[str],
    *,
    seed: int,
    repetitions: int,
) -> dict[str, float]:
    task_ids = sorted(
        {
            item["task_id"]
            for target in eligible
            for item in predictions[target]["x+y+b+tau_tools"]
        }
    )
    random = Random(seed)
    samples = []
    for _ in range(repetitions):
        selected = [random.choice(task_ids) for _ in task_ids]
        increments = []
        for target in eligible:
            by_condition = {}
            for condition in ("x+y+tau_tools", "x+y+b+tau_tools"):
                source = predictions[target][condition]
                replicated = [
                    item
                    for task_id in selected
                    for item in source
                    if item["task_id"] == task_id
                ]
                by_condition[condition] = _metrics(replicated)["macro_f1"]
            increments.append(
                by_condition["x+y+b+tau_tools"] - by_condition["x+y+tau_tools"]
            )
        samples.append(sum(increments) / len(increments))
    return {
        "lower_95": _percentile(samples, 0.025),
        "upper_95": _percentile(samples, 0.975),
    }


def _decision(
    results: Mapping[str, Mapping[str, Any]],
    eligible: Sequence[str],
    interval: Mapping[str, float],
) -> tuple[str, list[str]]:
    increments = [
        results[target]["conditions"]["x+y+b+tau_tools"]["macro_f1"]
        - results[target]["conditions"]["x+y+tau_tools"]["macro_f1"]
        for target in eligible
    ]
    tau_increments = [
        results[target]["conditions"]["x+y+tau_tools"]["macro_f1"]
        - results[target]["conditions"]["x+y"]["macro_f1"]
        for target in eligible
    ]
    mean_increment = sum(increments) / len(increments)
    mean_tau = sum(tau_increments) / len(tau_increments)
    minimize = (
        all(value <= 0.02 for value in increments)
        and mean_increment <= 0.01
        and mean_tau >= 0.05
        and interval["upper_95"] <= 0.02
    )
    preserve = (
        sum(value >= 0.05 for value in increments) >= 2
        and mean_increment >= 0.03
        and interval["lower_95"] > 0
    )
    if minimize:
        return "DATA_MINIMIZATION_SUPPORTED", []
    if preserve:
        return "PRESERVE_B_SUPPORTED", []
    return (
        "INCONCLUSIVE_RESEARCH_ONLY",
        [
            "The frozen data-minimization and preserve-b thresholds were not both directionally and uncertainty satisfied."
        ],
    )


def run_study(args: argparse.Namespace) -> int:
    if not args.execute:
        raise SystemExit(
            "refusing paid/authenticated model execution without --execute"
        )
    config_path = args.config.resolve(strict=True)
    config = _config(config_path)
    if not git_tracked_worktree_is_clean(ROOT):
        raise HarborSuiteError(
            "study execution requires a clean tracked worktree so collector bytes "
            "are bound by source SHA"
        )
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"output directory already exists: {output}")
    output.mkdir(parents=True)
    tasks_by_name = {
        ref.path.name: ref.path for ref in get_suite("mathematical-benchmarks-v1").tasks
    }
    selected = _selected_tasks(config, set(args.task))
    manifest = {
        "schema_version": "1",
        "study_id": config["study_id"],
        "config_sha256": _sha256(config_path),
        "collector_sha256": _collector_digest(),
        "source_sha": git_head_sha(ROOT),
        "codex_version": None,
        "trials": [],
    }
    version = run_operator_command(
        "codex", ("--version",), cwd=ROOT, timeout_seconds=30
    )
    if version.status is not ToolCommandStatus.EXITED or version.exit_code != 0:
        raise HarborSuiteError("codex --version failed")
    manifest["codex_version"] = version.stdout.decode("utf-8", errors="replace").strip()
    for item in selected:
        task = tasks_by_name.get(item["id"])
        if task is None:
            raise HarborSuiteError(
                f"selected task is not a dataset member: {item['id']}"
            )
        _validate_task_digest(task, item["digest"])
        record = _run_trial(task=task, task_record=item, config=config, root=output)
        manifest["trials"].append(
            {
                "trial_id": item["id"],
                "record": f"{item['id']}/trial.json",
                "record_sha256": _sha256(output / item["id"] / "trial.json"),
                "command_status": record["command"]["status"],
                "verifier_reward": record["verifier"]["reward"],
            }
        )
        _write_json(output / "manifest.json", manifest)
        print(json.dumps(manifest["trials"][-1], sort_keys=True), flush=True)
    return 0


def _summarize_diagnostics(
    all_rows: Mapping[str, Sequence[Row]], eligibility: Mapping[str, object]
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    results: dict[str, dict[str, Any]] = {}
    eligible_targets: list[str] = []
    minimum_classes = _safe_int(eligibility.get("diagnostic_requires_at_least_classes"))
    for target in _TARGETS:
        target_rows = all_rows[target]
        labels = sorted({row.label for row in target_rows})
        eligible = len(labels) >= minimum_classes
        if eligible:
            eligible_targets.append(target)
        condition_metrics = {}
        contingencies = {}
        for condition in _CONDITIONS:
            predictions, contingency = _descriptive_predictions(target_rows, condition)
            condition_metrics[condition] = _metrics(predictions)
            contingencies[condition] = contingency
        results[target] = {
            "eligible": eligible,
            "row_count": len(target_rows),
            "task_count": len({row.task_id for row in target_rows}),
            "class_counts": dict(
                sorted(Counter(row.label for row in target_rows).items())
            ),
            "conditions": condition_metrics,
            "exact_contingencies": contingencies,
            "baselines": {
                "global_majority_loto": _metrics(_majority_predictions(target_rows)),
                "task_identity_resubstitution_upper_bound": _metrics(
                    _task_identity_upper(target_rows)
                ),
            },
        }
    return results, eligible_targets


def analyze_study(args: argparse.Namespace) -> int:
    config_path = args.config.resolve(strict=True)
    config = _config(config_path)
    results_root = args.results.resolve(strict=True)
    manifest = _read_json(results_root / "manifest.json")
    if manifest.get("config_sha256") != _sha256(config_path):
        raise HarborSuiteError("run manifest is not bound to the selected study config")
    collector_digest = manifest.get("collector_sha256")
    if not isinstance(collector_digest, str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", collector_digest
    ):
        raise HarborSuiteError("run manifest does not bind collector bytes")
    tasks_by_name = {
        ref.path.name: ref.path for ref in get_suite("mathematical-benchmarks-v1").tasks
    }
    all_rows: dict[str, list[Row]] = defaultdict(list)
    projections = []
    for trial_record in manifest.get("trials", []):
        task_id = trial_record["trial_id"]
        trial_path = results_root / task_id
        if _sha256(trial_path / "trial.json") != trial_record["record_sha256"]:
            raise HarborSuiteError(f"trial record digest mismatch: {task_id}")
        projection, projected_rows = _project_trial(tasks_by_name[task_id], trial_path)
        projections.append(projection)
        for target, values in projected_rows.items():
            all_rows[target].extend(values)
    eligibility = config["eligibility"]
    completed = sum(item["status"] == "COMPLETE" for item in projections)
    server_tool_trajectories = sum(
        item["tool_metrics"]["tool_call_count"] > 0 for item in projections
    )
    no_run_or_failed = sum(
        item["labels"]["tool_use_failure_class"]
        in {
            "NO_SERVER_TOOL_USE",
            "DISCOVERY_ONLY",
            "RECOVERED_AFTER_FAILURE",
            "UNRECOVERED_FAILURE",
        }
        for item in projections
    )
    results, eligible_targets = _summarize_diagnostics(all_rows, eligibility)
    dataset_eligible = (
        completed >= _safe_int(eligibility["minimum_completed_trials"])
        and len(eligible_targets)
        >= _safe_int(eligibility["minimum_eligible_diagnostics"])
        and server_tool_trajectories
        >= _safe_int(eligibility["minimum_server_tool_trajectories"])
        and no_run_or_failed
        >= _safe_int(eligibility["minimum_no_run_or_failed_run_trajectories"])
    )
    interval = None
    decision = "INCONCLUSIVE_RESEARCH_ONLY"
    reasons = [
        "Two pre-analysis execution approaches failed: loopback proxy leakage, then an unbound collector revision.",
        "The frozen fallback permits deterministic descriptive condition coverage and exact contingency tables, not a production data-minimization decision.",
    ]
    if not dataset_eligible:
        reasons.append("The frozen dataset eligibility thresholds were not satisfied.")
    report = {
        "schema_version": "1",
        "study_id": config["study_id"],
        "evidence_class": config["evidence_class"],
        "causal_claim_authorized": False,
        "config_sha256": _sha256(config_path),
        "run_manifest_sha256": _sha256(results_root / "manifest.json"),
        "source_sha": manifest.get("source_sha"),
        "collector_sha256": collector_digest,
        "analysis": {
            "mode": "FROZEN_SIMPLEST_DEFENSIBLE_FALLBACK",
            "metric_semantics": "Transductive exact-signature purity over fixed corpus-independent presence bins; descriptive only.",
            "held_out": False,
            "transductive": True,
        },
        "dataset": {
            "trial_count": len(projections),
            "completed_trial_count": completed,
            "server_tool_trajectory_count": server_tool_trajectories,
            "no_run_or_failed_run_trajectory_count": no_run_or_failed,
            "eligible": dataset_eligible,
        },
        "diagnostics": results,
        "eligible_diagnostics": eligible_targets,
        "incremental_b": {
            "per_diagnostic_macro_f1": {
                target: (
                    results[target]["conditions"]["x+y+b+tau_tools"]["macro_f1"]
                    - results[target]["conditions"]["x+y+tau_tools"]["macro_f1"]
                )
                for target in eligible_targets
            },
            "mean_macro_f1": (
                sum(
                    results[target]["conditions"]["x+y+b+tau_tools"]["macro_f1"]
                    - results[target]["conditions"]["x+y+tau_tools"]["macro_f1"]
                    for target in eligible_targets
                )
                / len(eligible_targets)
                if eligible_targets
                else 0.0
            ),
            "task_bootstrap_95": interval,
        },
        "incremental_tau_tools": {
            "mean_macro_f1": (
                sum(
                    results[target]["conditions"]["x+y+tau_tools"]["macro_f1"]
                    - results[target]["conditions"]["x+y"]["macro_f1"]
                    for target in eligible_targets
                )
                / len(eligible_targets)
                if eligible_targets
                else 0.0
            )
        },
        "decision": decision,
        "decision_reasons": reasons,
        "projections": projections,
        "retention": config["retention"],
        "limitations": [
            "This is a small, non-deterministic, single-run-per-task workflow diagnostic, not a causal comparison or capability-stealing experiment.",
            "Docker and Podman were unavailable; exact verifiers ran through the maintained clean child-process harness rather than Harbor containers.",
            "The first infrastructure smoke sent loopback MCP traffic through the host proxy and received HTTP 502; study runs explicitly bind loopback NO_PROXY.",
            "A first partial collection was excluded because its uncommitted collector bytes were not manifest-bound; accepted runs require a clean tracked tree and a collector SHA-256 binding.",
            "After those two failures, the preregistered fallback replaces held-out k-nearest-neighbor modeling with labeled transductive descriptive signatures; no production decision can follow from these scores.",
            "Task-visible final answers and verifier outcomes can dominate retrospective diagnostics; the study asks only for incremental observable information.",
            "No raw agent messages, tool arguments, tool results, or hidden reasoning are committed.",
        ],
    }
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"output already exists: {output}")
    _write_json(output, report)
    print(
        json.dumps({"decision": decision, "dataset": report["dataset"]}, sort_keys=True)
    )
    print(f"report_sha256={_sha256(output)}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--config", type=Path, default=_DEFAULT_CONFIG)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--task", action="append", default=[])
    run.add_argument("--execute", action="store_true")
    run.set_defaults(function=run_study)
    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("--config", type=Path, default=_DEFAULT_CONFIG)
    analyze.add_argument("--results", type=Path, required=True)
    analyze.add_argument("--output", type=Path, required=True)
    analyze.set_defaults(function=analyze_study)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return int(args.function(args))


if __name__ == "__main__":
    raise SystemExit(main())
