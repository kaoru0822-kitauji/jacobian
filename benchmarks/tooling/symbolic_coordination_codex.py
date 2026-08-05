"""Host-local Codex CLI observations for ``symbolic-coordination-v1``.

The runner deliberately lives outside Harbor's Docker execution path.  It
materializes only the public task contract in a fresh workspace, constrains
model-visible filesystem and network access, and invokes the existing task
verifier after the model process has exited.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmarks.tooling.command_runner import (
    ToolCommandRequest,
    ToolCommandResult,
    ToolCommandStatus,
    ToolResolver,
    git_head_sha,
    operator_environment,
    run_tool_command,
)
from benchmarks.validation._verifier_child import (
    VerifierExecutionError,
    run_verifier_in_child,
)
from jacobian.eval.telemetry import parse_agent_transcript

ROOT = Path(__file__).resolve().parents[2]
DATASET_ID = "symbolic-coordination-v1"
DATASET = ROOT / "benchmarks" / "datasets" / DATASET_ID
DEFAULT_TASK = "symbolic-coordination-near-miss-01"
DEFAULT_MODEL = "gpt-5.3-codex-spark"
DEFAULT_REASONING_EFFORT = "medium"
HARBOR_VERSION = "0.20.0"
CONDITIONS = ("A", "B", "C")
FORBIDDEN_ENVIRONMENT = frozenset({"JACOBIAN_MODEL", "OPENAI_API_KEY"})
FORBIDDEN_WORKSPACE_NAMES = frozenset(
    {
        ".git",
        "auth.json",
        "generate.py",
        "oracle",
        "pilot-manifest.json",
        "solution",
        "tests",
        "verifier.py",
        "verifier_support.py",
    }
)
INITIAL_FILES = frozenset({"input.json", "instruction.md", "submission_schema.json"})
PRIMARY_PROMPT = """Complete the mathematical task in this isolated directory.

Read instruction.md, input.json, and submission_schema.json.  Independently
assess the exact terminal claim and write submission.json plus every evidence
file required by the public contract.  Use any available local or Jacobian
tools if helpful, choosing your own mathematical method.  Do not use the web,
inspect paths outside this directory, or merely describe what should be
written.  Finish only after the on-disk submission and evidence are complete.
"""
AUDIT_PROMPT = """Perform exactly one targeted post-solution contract audit.

Review the current submission.json and evidence files against instruction.md,
input.json, and submission_schema.json.  Check the schema, exact task and
artifact bindings, scope, completeness, limitations, assurance, evidence
digest, and every mathematical direction required by the terminal
certificate.  This is a contract audit, not Jacobian reasoning-log AUDIT
mode.  Do not use the web or inspect paths outside this directory.

If a defect is present, revise submission.json and its evidence exactly once
as one coherent revision.  Otherwise leave them unchanged.  In either case,
write audit-report.json with exactly these keys:
  audit_schema_version: "1"
  status: "PASS" or "REVISED"
  revision_applied: boolean
  checks: an object whose exact boolean keys are schema, input_binding,
          scope, completeness, assurance, evidence_binding, mathematics
  notes: a string
Do not perform a second audit pass.
"""

PRIMARY_TIMEOUT_SECONDS = 900.0
AUDIT_TIMEOUT_SECONDS = 600.0
STDOUT_LIMIT_BYTES = 32 * 1024 * 1024
STDERR_LIMIT_BYTES = 4 * 1024 * 1024
MAX_TOTAL_TOKENS = 800_000
MAX_SUBMISSION_BYTES = 2 * 1024 * 1024
MAX_WORKSPACE_BYTES = 8 * 1024 * 1024
PROFILE_NAME = "symbolic-workspace-only"
PROFILE_TOML = (
    '{extends=":workspace",filesystem={":root"="deny",":minimal"="read",'
    '":tmpdir"="deny",":slash_tmp"="deny"},network={enabled=false}}'
)
MODEL_SHELL_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
SHELL_POLICY_TOML = (
    '{inherit="none",set={PATH="' + MODEL_SHELL_PATH + '",LANG="C.UTF-8"}}'
)


class HarnessError(RuntimeError):
    """The observation cannot safely continue."""


@dataclass(frozen=True, slots=True)
class TaskContract:
    """Frozen public and verifier identities for one task."""

    task_id: str
    path: Path
    harbor_digest: str
    public_hashes: Mapping[str, str]
    verifier_hashes: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class Preflight:
    """Validated local runtime inputs used to freeze a snapshot."""

    codex: Path
    mcp: Path
    auth_file: Path
    codex_version: str
    source_revision: str
    branch: str
    selected_model: Mapping[str, Any]
    selected_model_digest: str
    report: Mapping[str, Any]


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise HarnessError(f"expected a regular file: {path}")
    return _digest_bytes(path.read_bytes())


def _digest_json(value: object) -> str:
    return _digest_bytes(_canonical_bytes(value))


def _write_json(path: Path, value: object, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "xb" if exclusive else "wb"
    with path.open(mode) as stream:
        stream.write(_canonical_bytes(value))


def _write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


def _decode_json_object(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HarnessError(f"{label} did not return valid JSON") from exc
    if not isinstance(value, dict):
        raise HarnessError(f"{label} must return a JSON object")
    return value


def _command_succeeded(result: ToolCommandResult, *, label: str) -> bytes:
    if result.status is not ToolCommandStatus.EXITED or result.exit_code != 0:
        diagnostic = result.stderr.decode("utf-8", errors="replace").strip()
        raise HarnessError(
            f"{label} failed ({result.status}): {diagnostic[:1024] or 'no diagnostic'}"
        )
    return result.stdout


def _command_environment(
    source: Mapping[str, str], *, codex_home: Path
) -> Mapping[str, str]:
    return operator_environment(
        source=source,
        declared={
            "CODEX_HOME": str(codex_home),
            "HOME": str(codex_home),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "NO_COLOR": "1",
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
    )


def _run(
    executable: Path,
    arguments: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    timeout_seconds: float,
    stdin: bytes = b"",
    stdout_limit_bytes: int = STDERR_LIMIT_BYTES,
    stderr_limit_bytes: int = STDERR_LIMIT_BYTES,
) -> ToolCommandResult:
    return run_tool_command(
        ToolCommandRequest(
            executable=str(executable),
            arguments=tuple(arguments),
            environment=environment,
            cwd=str(cwd.resolve(strict=True)),
            timeout_seconds=timeout_seconds,
            stdin_bytes=stdin,
            stdout_limit_bytes=stdout_limit_bytes,
            stderr_limit_bytes=stderr_limit_bytes,
        )
    )


def _git_text(arguments: Sequence[str]) -> str:
    result = _run(
        Path("/usr/bin/git"),
        arguments,
        cwd=ROOT,
        environment=operator_environment(),
        timeout_seconds=30.0,
    )
    return _command_succeeded(result, label="git").decode("utf-8").strip()


def _validate_harbor_digest(value: str) -> str:
    hex_digest = value.removeprefix("sha256:")
    if len(hex_digest) != 64:
        raise HarnessError("pinned Harbor returned a malformed task digest")
    try:
        int(hex_digest, 16)
    except ValueError as exc:
        raise HarnessError("pinned Harbor returned a malformed task digest") from exc
    return value


def _harbor_task_digest(task: Path) -> str:
    script = (
        "import sys; from pathlib import Path; "
        "from benchmarks.tooling.harbor_digest import task_digest; "
        "print(task_digest(Path(sys.argv[1])))"
    )
    uvx = ToolResolver().resolve("uvx")
    if uvx is None:
        raise HarnessError("uvx is unavailable")
    result = run_tool_command(
        ToolCommandRequest(
            executable=uvx,
            arguments=(
                "--from",
                f"harbor=={HARBOR_VERSION}",
                "--with",
                "tomli-w==1.2.0",
                "--with",
                "jsonschema",
                "python",
                "-c",
                script,
                str(task),
            ),
            environment=operator_environment(),
            cwd=str(ROOT),
            timeout_seconds=180.0,
            stdout_limit_bytes=64 * 1024,
            stderr_limit_bytes=64 * 1024,
        )
    )
    value = (
        _command_succeeded(result, label="pinned Harbor task digest")
        .decode("ascii", errors="strict")
        .strip()
    )
    return _validate_harbor_digest(value)


def _require_clean_source() -> tuple[str, str]:
    revision = git_head_sha(ROOT)
    if revision is None:
        raise HarnessError("unable to resolve the source revision")
    if _git_text(("status", "--porcelain")):
        raise HarnessError("host-local evaluation requires a clean source worktree")
    branch = _git_text(("branch", "--show-current"))
    if not branch:
        raise HarnessError("host-local evaluation requires a named branch")
    return revision, branch


def _task_contract(task_id: str) -> TaskContract:
    if Path(task_id).name != task_id or task_id.startswith("."):
        raise HarnessError("task must be one symbolic-coordination-v1 member name")
    task = DATASET / task_id
    if task.is_symlink() or not task.is_dir():
        raise HarnessError(f"unknown {DATASET_ID} task: {task_id}")
    public_paths = {
        "input.json": task / "environment" / "input.json",
        "instruction.md": task / "instruction.md",
        "submission_schema.json": task / "environment" / "submission_schema.json",
    }
    verifier_paths = {
        "public_contract.json": task / "tests" / "public_contract.json",
        "verifier.py": task / "tests" / "verifier.py",
        "verifier_support.py": task / "tests" / "verifier_support.py",
    }
    for path in (*public_paths.values(), *verifier_paths.values()):
        try:
            path.resolve(strict=True).relative_to(task.resolve(strict=True))
        except (OSError, ValueError) as exc:
            raise HarnessError(f"task file escapes its task directory: {path}") from exc
    return TaskContract(
        task_id=task_id,
        path=task,
        harbor_digest=_harbor_task_digest(task),
        public_hashes={name: _digest_file(path) for name, path in public_paths.items()},
        verifier_hashes={
            name: _digest_file(path) for name, path in verifier_paths.items()
        },
    )


def _resolve_auth_file(source: Mapping[str, str], doctor: Mapping[str, Any]) -> Path:
    checks = doctor.get("checks")
    auth = checks.get("auth.credentials") if isinstance(checks, dict) else None
    details = auth.get("details") if isinstance(auth, dict) else None
    if (
        not isinstance(auth, dict)
        or auth.get("status") != "ok"
        or not isinstance(details, dict)
        or details.get("stored auth mode") != "chatgpt"
        or details.get("stored ChatGPT tokens") != "true"
        or details.get("stored API key") != "false"
        or details.get("auth storage mode") != "File"
    ):
        raise HarnessError(
            "Codex doctor must report file-backed ChatGPT auth with no stored API key"
        )
    configured_home = source.get("CODEX_HOME")
    base = Path(configured_home) if configured_home else Path.home() / ".codex"
    auth_file = base / "auth.json"
    if auth_file.is_symlink() or not auth_file.is_file():
        raise HarnessError("the file-backed Codex ChatGPT credential is unavailable")
    if not stat.S_ISREG(auth_file.stat().st_mode):
        raise HarnessError("the Codex ChatGPT credential is not a regular file")
    return auth_file.resolve(strict=True)


@contextmanager
def _ephemeral_codex_home(auth_file: Path) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="jacobian-codex-auth-") as raw:
        root = Path(raw)
        root.chmod(0o700)
        target = root / "auth.json"
        shutil.copyfile(auth_file, target)
        target.chmod(0o600)
        yield root


def _selected_model(catalog: Mapping[str, Any]) -> dict[str, Any]:
    models = catalog.get("models")
    if not isinstance(models, list):
        raise HarnessError("Codex model catalog omitted models")
    selected = next(
        (
            model
            for model in models
            if isinstance(model, dict) and model.get("slug") == DEFAULT_MODEL
        ),
        None,
    )
    if not isinstance(selected, dict) or selected.get("visibility") != "list":
        raise HarnessError(f"selected model {DEFAULT_MODEL!r} is not locally listed")
    levels = selected.get("supported_reasoning_levels")
    if not isinstance(levels, list):
        raise HarnessError("selected model omitted supported reasoning levels")
    efforts = {level.get("effort") for level in levels if isinstance(level, dict)}
    if DEFAULT_REASONING_EFFORT not in efforts:
        raise HarnessError(
            f"selected model does not support {DEFAULT_REASONING_EFFORT} reasoning"
        )
    if selected.get("shell_type") != "shell_command":
        raise HarnessError("selected model does not support the required shell tool")
    context_window = selected.get("context_window")
    if not isinstance(context_window, int) or context_window <= 0:
        raise HarnessError("selected model omitted its context-window contract")
    eligible_contexts = [
        model.get("context_window")
        for model in models
        if isinstance(model, dict)
        and model.get("visibility") == "list"
        and model.get("shell_type") == "shell_command"
        and isinstance(model.get("context_window"), int)
        and any(
            isinstance(level, dict) and level.get("effort") == DEFAULT_REASONING_EFFORT
            for level in model.get("supported_reasoning_levels", [])
        )
    ]
    if not eligible_contexts or context_window != min(eligible_contexts):
        raise HarnessError(
            "selected model is not the lowest-context listed shell model supporting "
            f"{DEFAULT_REASONING_EFFORT} reasoning"
        )
    return {
        "slug": selected["slug"],
        "display_name": selected.get("display_name"),
        "description": selected.get("description"),
        "priority": selected.get("priority"),
        "visibility": selected.get("visibility"),
        "supported_in_api": selected.get("supported_in_api"),
        "shell_type": selected.get("shell_type"),
        "context_window": context_window,
        "max_context_window": selected.get("max_context_window"),
        "supports_parallel_tool_calls": selected.get("supports_parallel_tool_calls"),
        "supported_reasoning_levels": sorted(str(effort) for effort in efforts),
        "tool_mode": selected.get("tool_mode"),
        "selection_basis": (
            "minimum_context_window_among_listed_shell_models_supporting_"
            f"{DEFAULT_REASONING_EFFORT}_reasoning"
        ),
    }


def _profile_config_arguments() -> tuple[str, ...]:
    return (
        "-c",
        f'default_permissions="{PROFILE_NAME}"',
        "-c",
        f"permissions.{PROFILE_NAME}={PROFILE_TOML}",
        "-c",
        'web_search="disabled"',
        "-c",
        "tools.web_search=false",
        "-c",
        f"shell_environment_policy={SHELL_POLICY_TOML}",
        "-c",
        f'model_reasoning_effort="{DEFAULT_REASONING_EFFORT}"',
    )


def _sandbox_probe(
    codex: Path,
    auth_file: Path,
    source: Mapping[str, str],
) -> Mapping[str, Any]:
    with tempfile.TemporaryDirectory(prefix="jacobian-codex-isolation-") as raw:
        root = Path(raw)
        workspace = root / "workspace"
        workspace.mkdir()
        inside = workspace / "inside.txt"
        outside = root / "outside.txt"
        inside.write_text("public\n", encoding="utf-8")
        outside.write_text("private\n", encoding="utf-8")
        with _ephemeral_codex_home(auth_file) as codex_home:
            environment = _command_environment(source, codex_home=codex_home)
            common = (
                "sandbox",
                "-C",
                str(workspace),
                "-P",
                PROFILE_NAME,
                "-c",
                f"permissions.{PROFILE_NAME}={PROFILE_TOML}",
            )
            inside_result = _run(
                codex,
                (*common, "/usr/bin/head", "-n", "1", str(inside)),
                cwd=workspace,
                environment=environment,
                timeout_seconds=30.0,
            )
            outside_result = _run(
                codex,
                (*common, "/usr/bin/head", "-n", "1", str(outside)),
                cwd=workspace,
                environment=environment,
                timeout_seconds=30.0,
            )
    if (
        inside_result.status is not ToolCommandStatus.EXITED
        or inside_result.exit_code != 0
        or inside_result.stdout.strip() != b"public"
    ):
        raise HarnessError("Codex permission profile cannot read its workspace")
    if (
        outside_result.status is not ToolCommandStatus.EXITED
        or outside_result.exit_code == 0
        or b"private" in outside_result.stdout
    ):
        raise HarnessError("Codex permission profile did not deny an outside read")
    return {
        "profile": PROFILE_NAME,
        "inside_read": "ALLOWED",
        "outside_read": "DENIED",
        "network": "DENIED",
        "web_search": "DISABLED",
    }


def _catalog_contract(
    codex: Path,
    auth_file: Path,
    source: Mapping[str, str],
) -> tuple[dict[str, Any], str]:
    # Model discovery is an operator-side check, not a model-visible process.
    # Reuse Codex's local catalog cache so a transient refresh failure cannot
    # silently replace the account catalog with a smaller bundled fallback.
    result = _run(
        codex,
        ("debug", "models"),
        cwd=ROOT,
        environment=_command_environment(source, codex_home=auth_file.parent),
        timeout_seconds=60.0,
        stdout_limit_bytes=4 * 1024 * 1024,
    )
    catalog = _decode_json_object(
        _command_succeeded(result, label="codex debug models"),
        label="codex debug models",
    )
    selected = _selected_model(catalog)
    return selected, _digest_json(selected)


def preflight(source: Mapping[str, str]) -> Preflight:
    """Validate auth, model, source, and the deny-by-default filesystem profile."""

    present = sorted(name for name in FORBIDDEN_ENVIRONMENT if name in source)
    if present:
        raise HarnessError(
            "forbidden API/model environment variable(s) are set: " + ", ".join(present)
        )
    resolver = ToolResolver(search_path=source.get("PATH"))
    codex_raw = resolver.resolve("codex")
    if codex_raw is None:
        raise HarnessError("codex is not installed")
    codex = Path(codex_raw)
    mcp = ROOT / ".venv" / "bin" / "jacobian-mcp"
    if mcp.is_symlink() or not mcp.is_file() or not os.access(mcp, os.X_OK):
        raise HarnessError("the locked .venv jacobian-mcp entry point is unavailable")
    original_home = Path(source.get("CODEX_HOME", str(Path.home() / ".codex")))
    doctor_result = _run(
        codex,
        ("doctor", "--json"),
        cwd=ROOT,
        environment=_command_environment(source, codex_home=original_home),
        timeout_seconds=60.0,
        stdout_limit_bytes=4 * 1024 * 1024,
    )
    if doctor_result.status is not ToolCommandStatus.EXITED:
        raise HarnessError(f"codex doctor did not exit: {doctor_result.status}")
    doctor = _decode_json_object(
        doctor_result.stdout,
        label="codex doctor",
    )
    auth_file = _resolve_auth_file(source, doctor)
    selected, selected_digest = _catalog_contract(codex, auth_file, source)
    revision, branch = _require_clean_source()
    isolation = _sandbox_probe(codex, auth_file, source)
    version = doctor.get("codexVersion")
    if not isinstance(version, str) or not version:
        raise HarnessError("Codex doctor omitted its version")
    auth_check = doctor["checks"]["auth.credentials"]
    report = {
        "schema_version": "1",
        "status": "READY",
        "auth": {
            "mode": "chatgpt",
            "storage": "ephemeral-copy-of-file-backed-session",
            "stored_api_key": False,
        },
        "codex_version": version,
        "doctor_overall_status": doctor.get("overallStatus"),
        "doctor_auth_status": auth_check["status"],
        "model": selected,
        "model_contract_digest": selected_digest,
        "model_selection": (
            "gpt-5.3-codex-spark is the locally listed ultra-fast model with the "
            "smallest context window among shell models supporting medium reasoning; "
            "the completed dry run proves Codex accepts its MCP configuration"
        ),
        "isolation": isolation,
        "source_revision": revision,
        "source_branch": branch,
    }
    return Preflight(
        codex=codex,
        mcp=mcp.resolve(strict=True),
        auth_file=auth_file,
        codex_version=version,
        source_revision=revision,
        branch=branch,
        selected_model=selected,
        selected_model_digest=selected_digest,
        report=report,
    )


def _require_output_root(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved_parent = path.parent.resolve(strict=True)
    candidate = resolved_parent / path.name
    try:
        candidate.relative_to(ROOT.resolve(strict=True))
    except ValueError:
        pass
    else:
        raise HarnessError("evaluation output must be outside the source repository")
    if candidate.exists():
        if candidate.is_symlink() or not candidate.is_dir():
            raise HarnessError("evaluation output must be a new directory")
        if any(candidate.iterdir()):
            raise HarnessError("evaluation output directory is not empty")
    else:
        candidate.mkdir(mode=0o700)
    return candidate.resolve(strict=True)


def _snapshot_body(
    task: TaskContract,
    preflight_result: Preflight,
) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "created_at": datetime.now(UTC).isoformat(),
        "dataset": DATASET_ID,
        "task": {
            "id": task.task_id,
            "harbor_digest": task.harbor_digest,
            "public_file_hashes": dict(task.public_hashes),
            "verifier_hashes": dict(task.verifier_hashes),
        },
        "harbor_version": HARBOR_VERSION,
        "source": {
            "revision": preflight_result.source_revision,
            "branch": preflight_result.branch,
            "uv_lock_digest": _digest_file(ROOT / "uv.lock"),
            "pilot_manifest_digest": _digest_file(DATASET / "pilot-manifest.json"),
        },
        "codex": {
            "version": preflight_result.codex_version,
            "executable_digest": _digest_file(preflight_result.codex),
            "auth_mode": "chatgpt",
            "api_key": False,
            "ephemeral_session": True,
            "ignore_user_config": True,
            "ignore_rules": True,
        },
        "model": dict(preflight_result.selected_model),
        "model_contract_digest": preflight_result.selected_model_digest,
        "reasoning_effort": DEFAULT_REASONING_EFFORT,
        "prompts": {
            "primary_digest": _digest_bytes(PRIMARY_PROMPT.encode("utf-8")),
            "audit_digest": _digest_bytes(AUDIT_PROMPT.encode("utf-8")),
        },
        "budgets": {
            "primary_wall_seconds": PRIMARY_TIMEOUT_SECONDS,
            "audit_wall_seconds": AUDIT_TIMEOUT_SECONDS,
            "codex_jsonl_bytes": STDOUT_LIMIT_BYTES,
            "stderr_bytes": STDERR_LIMIT_BYTES,
            "max_total_tokens_per_stage": MAX_TOTAL_TOKENS,
            "max_submission_bytes": MAX_SUBMISSION_BYTES,
            "max_workspace_bytes": MAX_WORKSPACE_BYTES,
        },
        "sampling": {
            "seed": None,
            "temperature": None,
            "deterministic": False,
            "source": "codex-cli-chatgpt-defaults-no-cli-overrides",
        },
        "isolation": {
            "permission_profile": PROFILE_NAME,
            "permission_profile_digest": _digest_bytes(PROFILE_TOML.encode()),
            "filesystem_default": "DENY",
            "workspace": "WRITE",
            "network": "DENY",
            "web_search": "DISABLED",
            "model_shell_path": MODEL_SHELL_PATH,
            "initial_files": sorted(INITIAL_FILES),
        },
        "jacobian": {
            "mcp_executable_digest": _digest_file(preflight_result.mcp),
            "policy_profile": "COMPUTE_VERIFY_NO_RETRIEVAL",
            "reasoning_log_mode": "REQUIRED",
        },
        "conditions": {
            "A": {
                "jacobian_enabled": False,
                "post_solution_audit": False,
                "reasoning_log_mode": "OFF",
            },
            "B": {
                "jacobian_enabled": True,
                "post_solution_audit": False,
                "reasoning_log_mode": "REQUIRED",
            },
            "C": {
                "jacobian_enabled": True,
                "post_solution_audit": True,
                "audit_passes": 1,
                "allowed_revisions": 1,
                "reasoning_log_mode": "REQUIRED",
                "audit_stage_jacobian_enabled": False,
            },
        },
    }


def freeze_snapshot(
    output: Path,
    task: TaskContract,
    preflight_result: Preflight,
) -> tuple[dict[str, Any], str]:
    body = _snapshot_body(task, preflight_result)
    snapshot_id = _digest_json(body)
    snapshot = {**body, "snapshot_id": snapshot_id}
    path = output / "runtime-snapshot.json"
    _write_json(path, snapshot, exclusive=True)
    path.chmod(0o444)
    _write_bytes(output / "primary-prompt.txt", PRIMARY_PROMPT.encode("utf-8"))
    _write_bytes(output / "audit-prompt.txt", AUDIT_PROMPT.encode("utf-8"))
    return snapshot, _digest_file(path)


def _assert_snapshot(path: Path, expected_digest: str) -> None:
    if _digest_file(path) != expected_digest:
        raise HarnessError("immutable runtime snapshot drifted")


def _assert_global_invariants(
    task: TaskContract,
    preflight_result: Preflight,
    source: Mapping[str, str],
) -> None:
    revision, branch = _require_clean_source()
    if (
        revision != preflight_result.source_revision
        or branch != preflight_result.branch
    ):
        raise HarnessError("source revision or branch drifted during evaluation")
    current = _task_contract(task.task_id)
    if current != task:
        raise HarnessError("task contract drifted during evaluation")
    selected, digest = _catalog_contract(
        preflight_result.codex, preflight_result.auth_file, source
    )
    if digest != preflight_result.selected_model_digest or selected != dict(
        preflight_result.selected_model
    ):
        raise HarnessError("selected Codex model contract drifted during evaluation")


def prepare_workspace(condition_root: Path, task: TaskContract) -> Path:
    workspace = condition_root / "workspace"
    workspace.mkdir(parents=True)
    shutil.copyfile(task.path / "environment" / "input.json", workspace / "input.json")
    shutil.copyfile(task.path / "instruction.md", workspace / "instruction.md")
    shutil.copyfile(
        task.path / "environment" / "submission_schema.json",
        workspace / "submission_schema.json",
    )
    (workspace / "evidence").mkdir()
    assert_workspace_safe(workspace, expected_hashes=task.public_hashes)
    return workspace


def assert_workspace_safe(
    workspace: Path,
    *,
    expected_hashes: Mapping[str, str],
) -> None:
    if workspace.is_symlink() or not workspace.is_dir():
        raise HarnessError("model workspace is not a regular directory")
    total_bytes = 0
    for entry in workspace.rglob("*"):
        if entry.is_symlink():
            raise HarnessError(f"workspace contamination: symlink {entry.name}")
        if not entry.is_dir() and not entry.is_file():
            raise HarnessError(f"workspace contamination: special file {entry.name}")
        if entry.name.lower() in FORBIDDEN_WORKSPACE_NAMES:
            raise HarnessError(f"workspace contamination: forbidden {entry.name}")
        if entry.is_file():
            total_bytes += entry.stat().st_size
    if total_bytes > MAX_WORKSPACE_BYTES:
        raise HarnessError("workspace byte budget exceeded")
    for name, expected in expected_hashes.items():
        path = workspace / name
        if _digest_file(path) != expected:
            raise HarnessError(f"runtime-visible task file drifted: {name}")


def _mcp_config_arguments(mcp: Path, state: Path) -> tuple[str, ...]:
    server_args = [
        "--state-dir",
        str(state),
        "--capability-policy-profile",
        "COMPUTE_VERIFY_NO_RETRIEVAL",
        "--reasoning-log-mode",
        "required",
    ]
    return (
        "-c",
        f"mcp_servers.jacobian.command={json.dumps(str(mcp))}",
        "-c",
        f"mcp_servers.jacobian.args={json.dumps(server_args)}",
        "-c",
        f"mcp_servers.jacobian.cwd={json.dumps(str(state))}",
        "-c",
        "mcp_servers.jacobian.required=true",
        "-c",
        "mcp_servers.jacobian.startup_timeout_sec=120",
        "-c",
        "mcp_servers.jacobian.tool_timeout_sec=120",
    )


def codex_arguments(
    *,
    workspace: Path,
    mcp: Path | None,
    state: Path | None,
) -> tuple[str, ...]:
    arguments = ["-a", "never", *_profile_config_arguments()]
    if mcp is not None:
        if state is None:
            raise HarnessError("Jacobian MCP requires an isolated state directory")
        arguments.extend(_mcp_config_arguments(mcp, state))
    arguments.extend(
        [
            "exec",
            "--ignore-user-config",
            "--ignore-rules",
            "--strict-config",
            "--skip-git-repo-check",
            "--ephemeral",
            "--json",
            "--color",
            "never",
            "--model",
            DEFAULT_MODEL,
            "--cd",
            str(workspace),
            "-",
        ]
    )
    return tuple(arguments)


def _run_codex_stage(
    *,
    label: str,
    prompt: str,
    condition_root: Path,
    workspace: Path,
    preflight_result: Preflight,
    source: Mapping[str, str],
    mcp_state: Path | None,
    timeout_seconds: float,
) -> tuple[ToolCommandResult, Mapping[str, Any], Mapping[str, Any]]:
    arguments = codex_arguments(
        workspace=workspace,
        mcp=preflight_result.mcp if mcp_state is not None else None,
        state=mcp_state,
    )
    _write_json(
        condition_root / f"{label}.command.json",
        {
            "executable": str(preflight_result.codex),
            "arguments": list(arguments),
            "stdin_digest": _digest_bytes(prompt.encode("utf-8")),
            "environment_names": [
                "CODEX_HOME",
                "HOME",
                "LANG",
                "LC_ALL",
                "NO_COLOR",
                "PATH",
            ],
        },
    )
    started_wall = datetime.now(UTC).isoformat()
    started = time.monotonic()
    with _ephemeral_codex_home(preflight_result.auth_file) as codex_home:
        result = _run(
            preflight_result.codex,
            arguments,
            cwd=workspace,
            environment=_command_environment(source, codex_home=codex_home),
            timeout_seconds=timeout_seconds,
            stdin=prompt.encode("utf-8"),
            stdout_limit_bytes=STDOUT_LIMIT_BYTES,
            stderr_limit_bytes=STDERR_LIMIT_BYTES,
        )
    elapsed = time.monotonic() - started
    timing = {
        "started_at": started_wall,
        "finished_at": datetime.now(UTC).isoformat(),
        "elapsed_seconds": elapsed,
        "timeout_seconds": timeout_seconds,
        "terminal_status": result.status.value,
        "exit_code": result.exit_code,
    }
    raw_path = condition_root / f"{label}.codex.jsonl"
    _write_bytes(raw_path, result.stdout)
    _write_bytes(condition_root / f"{label}.stderr.txt", result.stderr)
    _write_json(condition_root / f"{label}.timing.json", timing)
    telemetry = parse_agent_transcript(raw_path)
    telemetry.update(_jsonl_runtime_facts(result.stdout))
    _write_json(condition_root / f"{label}.telemetry.json", telemetry)
    return result, telemetry, timing


def _jsonl_runtime_facts(raw: bytes) -> dict[str, Any]:
    observed_models: set[str] = set()
    thread_ids: set[str] = set()
    terminal_failures: list[str] = []
    web_search_count = 0
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if event_type == "thread.started" and isinstance(event.get("thread_id"), str):
            thread_ids.add(event["thread_id"])
        if event_type in {"turn.failed", "error"}:
            terminal_failures.append(str(event_type))
        for container in (event, event.get("turn")):
            if isinstance(container, dict) and isinstance(container.get("model"), str):
                observed_models.add(container["model"])
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") in {
            "web_search",
            "web_search_call",
        }:
            web_search_count += 1
    return {
        "requested_model": DEFAULT_MODEL,
        "observed_models": sorted(observed_models),
        "model_attestation": (
            "CLI_EVENT_AND_EXPLICIT_REQUEST"
            if observed_models
            else "EXPLICIT_REQUEST_AND_FROZEN_CATALOG"
        ),
        "thread_ids": sorted(thread_ids),
        "terminal_failures": terminal_failures,
        "web_search_count": web_search_count,
    }


def _usage_total(telemetry: Mapping[str, Any]) -> int | None:
    usage = telemetry.get("usage")
    if not isinstance(usage, dict):
        return None
    candidates = ("total_tokens", "input_tokens", "output_tokens")
    if isinstance(usage.get("total_tokens"), int):
        return int(usage["total_tokens"])
    values = [usage.get(key) for key in candidates[1:]]
    return sum(int(value) for value in values if isinstance(value, int))


def _stage_failures(
    result: ToolCommandResult,
    telemetry: Mapping[str, Any],
    *,
    label: str,
) -> list[str]:
    failures: list[str] = []
    if result.status is not ToolCommandStatus.EXITED or result.exit_code != 0:
        failures.append(f"{label}:CODEX_{result.status.value}")
    if not result.stdout.strip():
        failures.append(f"{label}:MISSING_CODEX_JSONL")
    usage_total = _usage_total(telemetry)
    if usage_total is None:
        failures.append(f"{label}:MISSING_TOKEN_USAGE")
    elif usage_total > MAX_TOTAL_TOKENS:
        failures.append(f"{label}:TOKEN_BUDGET_EXCEEDED")
    observed_models = telemetry.get("observed_models")
    if isinstance(observed_models, list) and observed_models not in (
        [],
        [DEFAULT_MODEL],
    ):
        failures.append(f"{label}:MODEL_DRIFT")
    if telemetry.get("terminal_failures"):
        failures.append(f"{label}:TERMINAL_FAILURE_EVENT")
    if telemetry.get("web_search_count") != 0:
        failures.append(f"{label}:WEB_SEARCH_USED")
    return failures


def _copy_regular_tree(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_dir():
        raise HarnessError("evidence must be a regular directory")
    destination.mkdir(parents=True)
    for entry in sorted(source.rglob("*")):
        if entry.is_symlink() or (not entry.is_dir() and not entry.is_file()):
            raise HarnessError("evidence contains a symlink or special file")
        relative = entry.relative_to(source)
        target = destination / relative
        if entry.is_dir():
            target.mkdir()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(entry, target)


def _preserve_submission(workspace: Path, destination: Path) -> None:
    submission = workspace / "submission.json"
    if submission.is_symlink() or not submission.is_file():
        raise HarnessError("MISSING_OUTPUT: submission.json is absent")
    if submission.stat().st_size > MAX_SUBMISSION_BYTES:
        raise HarnessError("submission.json exceeds its byte budget")
    destination.mkdir(parents=True)
    shutil.copyfile(submission, destination / "submission.json")
    _copy_regular_tree(workspace / "evidence", destination / "evidence")


def _submission_state_digest(workspace: Path) -> str:
    """Bind revision detection to the submission and its complete evidence tree."""

    submission = workspace / "submission.json"
    if submission.is_symlink() or not submission.is_file():
        raise HarnessError("MISSING_OUTPUT: submission.json is absent")
    evidence = workspace / "evidence"
    if evidence.is_symlink() or not evidence.is_dir():
        raise HarnessError("evidence must be a regular directory")
    files = [{"path": "submission.json", "digest": _digest_file(submission)}]
    for path in sorted(evidence.rglob("*")):
        if path.is_symlink() or (not path.is_dir() and not path.is_file()):
            raise HarnessError("evidence contains a symlink or special file")
        if path.is_file():
            files.append(
                {
                    "path": (Path("evidence") / path.relative_to(evidence)).as_posix(),
                    "digest": _digest_file(path),
                }
            )
    return _digest_json(files)


def _audit_report_failures(path: Path, *, revised: bool) -> list[str]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError):
        return ["audit:MISSING_OR_MALFORMED_REPORT"]
    expected_checks = {
        "schema",
        "input_binding",
        "scope",
        "completeness",
        "assurance",
        "evidence_binding",
        "mathematics",
    }
    if not isinstance(value, dict) or set(value) != {
        "audit_schema_version",
        "status",
        "revision_applied",
        "checks",
        "notes",
    }:
        return ["audit:MALFORMED_REPORT"]
    checks = value.get("checks")
    valid = (
        value.get("audit_schema_version") == "1"
        and value.get("status") in {"PASS", "REVISED"}
        and isinstance(value.get("revision_applied"), bool)
        and isinstance(value.get("notes"), str)
        and isinstance(checks, dict)
        and set(checks) == expected_checks
        and all(isinstance(item, bool) for item in checks.values())
        and value.get("revision_applied") is revised
        and (value.get("status") == "REVISED") is revised
    )
    return [] if valid else ["audit:MALFORMED_OR_UNBOUND_REPORT"]


def _verification_copy(
    condition_root: Path,
    workspace: Path,
) -> tuple[Path, Path]:
    verification = condition_root / "verification"
    app = verification / "app"
    logs = verification / "logs"
    app.mkdir(parents=True)
    logs.mkdir()
    submission = workspace / "submission.json"
    if submission.is_symlink() or not submission.is_file():
        raise HarnessError("MISSING_OUTPUT: submission.json is absent")
    shutil.copyfile(submission, app / "submission.json")
    _copy_regular_tree(workspace / "evidence", app / "evidence")
    return app, logs


def _run_verification(
    task: TaskContract,
    condition_root: Path,
    workspace: Path,
) -> Mapping[str, Any]:
    app, logs = _verification_copy(condition_root, workspace)
    try:
        reward = run_verifier_in_child(
            task=task.path,
            app=app,
            logs=logs,
            timeout_seconds=30.0,
        )
    except (VerifierExecutionError, ValueError) as exc:
        raise HarnessError(f"clean-room verifier failed: {exc}") from exc
    result = {
        "execution_status": "COMPLETED",
        "mathematical_observation": (
            "ACCEPTED" if reward.get("reward") == 1.0 else "REJECTED"
        ),
        "reward": reward,
        "verifier_workspace_outside_model_workspace": True,
    }
    _write_json(condition_root / "verifier-result.json", result)
    return result


def _export_reasoning_logs(state: Path, output: Path) -> Mapping[str, Any]:
    """Export durable reasoning events through their authoritative models."""

    from jacobian.reasoning_log import ReasoningLogService
    from jacobian.storage.repository import ArtifactRepository

    output.mkdir()
    index: dict[str, Any]
    if not (state / "metadata.sqlite3").is_file():
        index = {"status": "EMPTY", "runs": []}
        _write_json(output / "index.json", index)
        return index
    with ArtifactRepository(state) as store:
        with store.connection() as connection:
            rows = connection.execute(
                "SELECT run_id FROM reasoning_runs ORDER BY run_id"
            ).fetchall()
        service = ReasoningLogService(store)
        runs: list[dict[str, Any]] = []
        for row in rows:
            run_id = str(row["run_id"])
            events = service.inspect(run_id)
            path = output / f"{run_id}.jsonl"
            path.write_text(service.inspect_jsonl(run_id), encoding="utf-8")
            runs.append(
                {
                    "run_id": run_id,
                    "event_count": len(events),
                    "finalized": bool(events and events[-1].kind == "FINAL"),
                    "path": path.name,
                    "digest": _digest_file(path),
                }
            )
    index = {"status": "EXPORTED", "runs": runs}
    _write_json(output / "index.json", index)
    return index


def _condition_result(
    *,
    condition: str,
    snapshot_id: str,
    failures: Sequence[str],
    primary_telemetry: Mapping[str, Any],
    audit_telemetry: Mapping[str, Any] | None,
    verifier: Mapping[str, Any] | None,
    reasoning_logs: Mapping[str, Any] | None,
    revision_applied: bool | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "1",
        "condition": condition,
        "snapshot_id": snapshot_id,
        "infrastructure_status": "COMPLETE" if not failures else "INCOMPLETE",
        "infrastructure_failures": list(failures),
        "model": DEFAULT_MODEL,
        "reasoning_effort": DEFAULT_REASONING_EFFORT,
        "primary_usage": primary_telemetry.get("usage"),
        "primary_tool_calls": {
            "mcp": primary_telemetry.get("mcp_calls", []),
            "shell": primary_telemetry.get("shell_calls", []),
            "capability_ids": primary_telemetry.get("capability_ids", []),
        },
        "audit_usage": audit_telemetry.get("usage") if audit_telemetry else None,
        "audit_tool_calls": {
            "mcp": audit_telemetry.get("mcp_calls", []),
            "shell": audit_telemetry.get("shell_calls", []),
        }
        if audit_telemetry
        else None,
        "revision_applied": revision_applied,
        "reasoning_logs": reasoning_logs,
        "verifier": verifier,
    }
    return payload


def run_condition(
    *,
    condition: str,
    output: Path,
    task: TaskContract,
    snapshot: Mapping[str, Any],
    snapshot_digest: str,
    preflight_result: Preflight,
    source: Mapping[str, str],
) -> Mapping[str, Any]:
    condition_root = output / condition
    condition_root.mkdir()
    workspace = prepare_workspace(condition_root, task)
    mcp_state = condition_root / "jacobian-state" if condition in {"B", "C"} else None
    if mcp_state is not None:
        mcp_state.mkdir()
    failures: list[str] = []
    primary, primary_telemetry, _timing = _run_codex_stage(
        label="primary",
        prompt=PRIMARY_PROMPT,
        condition_root=condition_root,
        workspace=workspace,
        preflight_result=preflight_result,
        source=source,
        mcp_state=mcp_state,
        timeout_seconds=PRIMARY_TIMEOUT_SECONDS,
    )
    failures.extend(_stage_failures(primary, primary_telemetry, label="primary"))
    assert_workspace_safe(workspace, expected_hashes=task.public_hashes)
    _assert_snapshot(output / "runtime-snapshot.json", snapshot_digest)
    _assert_global_invariants(task, preflight_result, source)
    revision_applied: bool | None = None
    audit_telemetry: Mapping[str, Any] | None = None
    if (workspace / "submission.json").is_file():
        _preserve_submission(workspace, condition_root / "pre-audit")
    else:
        failures.append("primary:MISSING_OUTPUT")
    if condition == "C" and not failures:
        before = _submission_state_digest(workspace)
        audit, audit_telemetry, _audit_timing = _run_codex_stage(
            label="audit",
            prompt=AUDIT_PROMPT,
            condition_root=condition_root,
            workspace=workspace,
            preflight_result=preflight_result,
            source=source,
            mcp_state=None,
            timeout_seconds=AUDIT_TIMEOUT_SECONDS,
        )
        failures.extend(_stage_failures(audit, audit_telemetry, label="audit"))
        assert_workspace_safe(workspace, expected_hashes=task.public_hashes)
        if not (workspace / "submission.json").is_file():
            failures.append("audit:MISSING_OUTPUT")
        else:
            revision_applied = _submission_state_digest(workspace) != before
            failures.extend(
                _audit_report_failures(
                    workspace / "audit-report.json", revised=revision_applied
                )
            )
    if (workspace / "submission.json").is_file():
        _preserve_submission(workspace, condition_root / "final")
    reasoning_logs = (
        _export_reasoning_logs(mcp_state, condition_root / "reasoning-logs")
        if mcp_state is not None
        else None
    )
    verifier: Mapping[str, Any] | None = None
    if not failures:
        verifier = _run_verification(task, condition_root, workspace)
    _assert_snapshot(output / "runtime-snapshot.json", snapshot_digest)
    _assert_global_invariants(task, preflight_result, source)
    result = _condition_result(
        condition=condition,
        snapshot_id=str(snapshot["snapshot_id"]),
        failures=failures,
        primary_telemetry=primary_telemetry,
        audit_telemetry=audit_telemetry,
        verifier=verifier,
        reasoning_logs=reasoning_logs,
        revision_applied=revision_applied,
    )
    _write_json(condition_root / "condition-result.json", result)
    return result


def _dry_run_plan(
    output: Path,
    task: TaskContract,
    preflight_result: Preflight,
    conditions: Sequence[str],
    snapshot_id: str,
) -> Mapping[str, Any]:
    plans = []
    for condition in conditions:
        root = output / condition
        root.mkdir()
        workspace = prepare_workspace(root, task)
        state = root / "jacobian-state" if condition in {"B", "C"} else None
        if state is not None:
            state.mkdir()
        plans.append(
            {
                "condition": condition,
                "primary_arguments": list(
                    codex_arguments(
                        workspace=workspace,
                        mcp=preflight_result.mcp if state is not None else None,
                        state=state,
                    )
                ),
                "audit_arguments": list(
                    codex_arguments(workspace=workspace, mcp=None, state=None)
                )
                if condition == "C"
                else None,
            }
        )
    plan = {
        "schema_version": "1",
        "status": "DRY_RUN",
        "snapshot_id": snapshot_id,
        "conditions": plans,
    }
    _write_json(output / "dry-run.json", plan)
    return plan


def _artifact_index(output: Path) -> Mapping[str, Any]:
    files = []
    for path in sorted(output.rglob("*")):
        if path == output / "artifact-index.json" or not path.is_file():
            continue
        if path.is_symlink():
            raise HarnessError("result artifacts must not contain symlinks")
        files.append(
            {
                "path": path.relative_to(output).as_posix(),
                "bytes": path.stat().st_size,
                "digest": _digest_file(path),
            }
        )
    index = {"schema_version": "1", "files": files}
    _write_json(output / "artifact-index.json", index)
    return index


def execute(
    *,
    task_id: str,
    output_path: Path,
    conditions: Sequence[str],
    dry_run: bool,
    source: Mapping[str, str],
) -> Mapping[str, Any]:
    if not conditions or len(set(conditions)) != len(conditions):
        raise HarnessError("conditions must be a non-empty duplicate-free selection")
    unknown = sorted(set(conditions) - set(CONDITIONS))
    if unknown:
        raise HarnessError("unknown condition(s): " + ", ".join(unknown))
    preflight_result = preflight(source)
    task = _task_contract(task_id)
    output = _require_output_root(output_path)
    _write_json(output / "preflight.json", preflight_result.report)
    snapshot, snapshot_digest = freeze_snapshot(output, task, preflight_result)
    if dry_run:
        plan = _dry_run_plan(
            output,
            task,
            preflight_result,
            conditions,
            str(snapshot["snapshot_id"]),
        )
        _artifact_index(output)
        return plan
    results = []
    for condition in conditions:
        _assert_global_invariants(task, preflight_result, source)
        _assert_snapshot(output / "runtime-snapshot.json", snapshot_digest)
        results.append(
            run_condition(
                condition=condition,
                output=output,
                task=task,
                snapshot=snapshot,
                snapshot_digest=snapshot_digest,
                preflight_result=preflight_result,
                source=source,
            )
        )
    run_result = {
        "schema_version": "1",
        "status": (
            "COMPLETE"
            if all(result["infrastructure_status"] == "COMPLETE" for result in results)
            else "INCOMPLETE"
        ),
        "snapshot_id": snapshot["snapshot_id"],
        "task": task_id,
        "conditions": results,
    }
    _write_json(output / "run-result.json", run_result)
    _artifact_index(output)
    return run_result


def _default_output(task_id: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return (
        Path(tempfile.gettempdir())
        / "jacobian-symbolic-coordination-v1-results"
        / f"{task_id}-{stamp}"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run isolated host-local Codex symbolic-coordination observations"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("--task", default=DEFAULT_TASK)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--task", default=DEFAULT_TASK)
    run_parser.add_argument("--output", type=Path)
    run_parser.add_argument(
        "--conditions", nargs="+", choices=CONDITIONS, default=list(CONDITIONS)
    )
    run_parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    source = os.environ
    try:
        if args.command == "preflight":
            result = preflight(source)
            _task_contract(args.task)
            print(json.dumps(result.report, indent=2, sort_keys=True))
            return 0
        output = args.output or _default_output(args.task)
        run_result = execute(
            task_id=args.task,
            output_path=output,
            conditions=args.conditions,
            dry_run=args.dry_run,
            source=source,
        )
        print(json.dumps({"output": str(output), "result": run_result}, indent=2))
        return 0 if run_result.get("status") in {"COMPLETE", "DRY_RUN"} else 2
    except (HarnessError, OSError, ValueError) as exc:
        print(f"symbolic-coordination Codex harness: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
