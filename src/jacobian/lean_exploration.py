"""Pinned, replayable exploratory Lean capabilities."""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import signal
import subprocess
import threading
import time
import weakref
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from jacobian.artifacts import ArtifactService
from jacobian.capabilities import CapabilityInvocationError
from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityCompleteness,
    CapabilityCompletenessStatus,
    CapabilityDescriptor,
    CapabilityDiagnostic,
    CapabilityMode,
    CapabilityProviderRuntime,
    CapabilityRequest,
    CapabilityResult,
    CapabilityScope,
)
from jacobian.contracts.lean import LeanEnvironment
from jacobian.contracts.lean_exploration import (
    LeanPremiseCandidate,
    LeanPremiseRetrievalArtifact,
    LeanPremiseRetrievalOutput,
    LeanPremiseRetrievalRequest,
    LeanProofStateOutput,
    LeanProofStateRequest,
    LeanProofStateTransitionArtifact,
)
from jacobian.contracts.results import Execution, ExecutionStatus
from jacobian.references import LeanCheckerInstallation
from jacobian.schema_registry import SchemaRegistry
from jacobian.store import ArtifactStore

_FORBIDDEN = re.compile(
    r"\b(?:admit|axiom|elab|import|macro|native_decide|opaque|run_tac|"
    r"set_option|sorry|syntax|unsafe)\b|#",
    re.IGNORECASE,
)
_SUGGESTION = re.compile(
    r"Try this:\s*\n\s*\[apply\]\s*(?P<tactic>[^\r\n]+)",
)
_DECLARATION = re.compile(r"\b[A-Z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_']+)+\b")
_RESOURCE_POLL_SECONDS = 0.1


@dataclass(frozen=True, slots=True)
class LeanReplPolicy:
    """Bounds one reusable exploratory REPL process."""

    max_requests: int = 16
    max_age_seconds: float = 600
    max_rss_kb: int = 7 * 1024 * 1024
    timeout_seconds: float = 180

    def __post_init__(self) -> None:
        if self.max_requests < 1:
            raise ValueError("max_requests must be positive")
        if self.max_age_seconds <= 0 or self.timeout_seconds <= 0:
            raise ValueError("REPL time bounds must be positive")
        if self.max_rss_kb < 0:
            raise ValueError("max_rss_kb cannot be negative")


class PersistentLeanRepl:
    """Serialized, bounded client for one exploratory Lean REPL process."""

    def __init__(
        self,
        *,
        command: tuple[str, ...],
        cwd: Path,
        base_command: str | None,
        policy: LeanReplPolicy,
    ) -> None:
        self._command = command
        self._cwd = cwd
        self._base_command = base_command
        self._policy = policy
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._responses: queue.Queue[dict[str, Any] | BaseException] = queue.Queue()
        self._base_env: int | None = None
        self._started_at = 0.0
        self._requests = 0

    def execute(
        self,
        *,
        command: str,
        tactic: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Run one independent command and tactic from the immutable base env."""

        with self._lock:
            self._ensure_process()
            command_request: dict[str, Any] = {"cmd": command}
            if self._base_env is not None:
                command_request["env"] = self._base_env
            command_response = self._exchange(command_request)
            proof_state = _single_proof_state(command_response)
            tactic_response = self._exchange(
                {"tactic": tactic, "proofState": proof_state}
            )
            self._requests += 1
            return command_response, tactic_response

    def close(self) -> None:
        """Stop the process and discard all retained snapshots."""

        with self._lock:
            self._stop_process()

    def _ensure_process(self) -> None:
        if self._process is not None and self._expired():
            self._stop_process()
        if self._process is not None:
            return
        self._responses = queue.Queue()
        responses = self._responses
        self._process = subprocess.Popen(
            self._command,
            cwd=self._cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            start_new_session=(os.name == "posix"),
        )
        self._started_at = time.monotonic()
        self._requests = 0
        self._base_env = None
        threading.Thread(
            target=self._read_responses,
            args=(self._process, responses),
            name="jacobian-lean-repl-reader",
            daemon=True,
        ).start()
        if self._base_command is not None:
            response = self._exchange({"cmd": self._base_command})
            base_env = response.get("env")
            if not isinstance(base_env, int):
                self._stop_process()
                raise RuntimeError("Lean REPL did not return a base environment")
            self._base_env = base_env

    def _expired(self) -> bool:
        assert self._process is not None
        if self._process.poll() is not None:
            return True
        if self._requests >= self._policy.max_requests:
            return True
        if time.monotonic() - self._started_at >= self._policy.max_age_seconds:
            return True
        rss_kb = _process_rss_kb(self._process.pid)
        return self._policy.max_rss_kb > 0 and rss_kb > self._policy.max_rss_kb

    def _exchange(self, request: Mapping[str, Any]) -> dict[str, Any]:
        process = self._process
        if process is None or process.stdin is None:
            raise RuntimeError("Lean REPL is unavailable")
        try:
            process.stdin.write(json.dumps(request, sort_keys=True) + "\n\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self._stop_process()
            raise RuntimeError("Lean REPL stopped before receiving a request") from exc
        deadline = time.monotonic() + self._policy.timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._stop_process()
                raise RuntimeError("Lean REPL timed out")
            try:
                response = self._responses.get(
                    timeout=min(_RESOURCE_POLL_SECONDS, remaining)
                )
                break
            except queue.Empty:
                rss_kb = _process_rss_kb(process.pid)
                if self._policy.max_rss_kb > 0 and rss_kb > self._policy.max_rss_kb:
                    self._stop_process()
                    raise RuntimeError("Lean REPL exceeded its memory limit") from None
        if isinstance(response, BaseException):
            self._stop_process()
            raise RuntimeError(
                "Lean REPL stopped before returning a result"
            ) from response
        return response

    def _read_responses(
        self,
        process: subprocess.Popen[str],
        responses: queue.Queue[dict[str, Any] | BaseException],
    ) -> None:
        stdout = process.stdout
        if stdout is None:
            responses.put(RuntimeError("Lean REPL stdout is unavailable"))
            return
        block: list[str] = []
        try:
            for line in stdout:
                if line.strip():
                    block.append(line)
                    continue
                if not block:
                    continue
                value = json.loads("".join(block))
                if not isinstance(value, dict):
                    raise RuntimeError("Lean REPL returned a non-object response")
                responses.put(value)
                block = []
            if block:
                raise RuntimeError("Lean REPL returned an unterminated response")
            responses.put(RuntimeError("Lean REPL exited"))
        except (json.JSONDecodeError, OSError, RuntimeError) as exc:
            responses.put(exc)

    def _stop_process(self) -> None:
        process = self._process
        self._process = None
        self._base_env = None
        if process is None:
            return
        if process.stdin is not None:
            with suppress(OSError):
                process.stdin.close()
        if process.poll() is None:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait()
        if process.stdout is not None:
            process.stdout.close()


def _single_proof_state(response: Mapping[str, Any]) -> int:
    sorries = response.get("sorries")
    if (
        not isinstance(sorries, list)
        or len(sorries) != 1
        or not isinstance(sorries[0], Mapping)
        or not isinstance(sorries[0].get("proofState"), int)
    ):
        errors = _response_errors(response)
        if errors:
            return -1
        raise RuntimeError("Lean did not expose one replayable proof state")
    proof_state = sorries[0]["proofState"]
    assert isinstance(proof_state, int)
    return proof_state


def _process_rss_kb(pid: int) -> int:
    """Read current Linux RSS; return zero where procfs is unavailable."""

    try:
        status = Path(f"/proc/{pid}/status").read_text()
    except OSError:
        return 0
    match = re.search(r"^VmRSS:\s+(?P<rss>\d+)\s+kB$", status, re.MULTILINE)
    return int(match.group("rss")) if match else 0


class LeanExplorationReplRuntime:
    """Own bounded REPL sessions used only by exploratory capabilities."""

    def __init__(
        self,
        runtime: Path,
        installations: Mapping[LeanEnvironment, LeanCheckerInstallation],
        *,
        policy: LeanReplPolicy | None = None,
    ) -> None:
        self._runtime = runtime
        self._installations = installations
        self._policy = policy or LeanReplPolicy()
        self._sessions: dict[LeanEnvironment, PersistentLeanRepl] = {}
        self._lock = threading.Lock()
        self._finalizer = weakref.finalize(self, _close_repls, self._sessions)

    def execute(
        self,
        *,
        command: str,
        tactic: str,
        environment: LeanEnvironment,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Serialize exploration and reuse only an environment's base snapshot."""

        with self._lock:
            session = self._sessions.get(environment)
            if session is None:
                session = self._create_session(environment)
                self._sessions[environment] = session
            return session.execute(command=command, tactic=tactic)

    def close(self) -> None:
        """Stop every exploration process without affecting independent checkers."""

        self._finalizer()

    def _create_session(self, environment: LeanEnvironment) -> PersistentLeanRepl:
        elan = shutil.which("elan")
        if elan is None:
            raise RuntimeError("elan is unavailable")
        installation = self._installations[environment]
        repl = (
            self._runtime
            / ".lake"
            / "packages"
            / "repl"
            / ".lake"
            / "build"
            / "bin"
            / "repl"
        )
        if not repl.is_file():
            raise RuntimeError(
                "the pinned Lean REPL is unavailable; run `lake build repl` in lean/"
            )
        policy = self._policy
        if environment is LeanEnvironment.CORE:
            policy = replace(policy, timeout_seconds=min(policy.timeout_seconds, 30))
        return PersistentLeanRepl(
            command=(
                elan,
                "run",
                f"leanprover/lean4:v{installation.lean_version}",
                "lake",
                "env",
                str(repl),
            ),
            cwd=self._runtime,
            base_command=(
                "import Mathlib" if environment is LeanEnvironment.MATHLIB else None
            ),
            policy=policy,
        )


def _close_repls(
    sessions: Mapping[LeanEnvironment, PersistentLeanRepl],
) -> None:
    for session in sessions.values():
        session.close()


@dataclass(frozen=True, slots=True)
class LeanExplorationInstallation:
    semantics_uri: str
    transition_schema_uri: str
    retrieval_schema_uri: str


@dataclass(frozen=True, slots=True)
class _Resources:
    store: ArtifactStore
    artifacts: ArtifactService
    semantics_uri: str
    transition_schema_uri: str
    retrieval_schema_uri: str
    installations: Mapping[LeanEnvironment, LeanCheckerInstallation]
    runtime: Path
    provider_runtime: CapabilityProviderRuntime
    repl: LeanExplorationReplRuntime


def install_lean_exploration_capabilities(
    store: ArtifactStore,
    schemas: SchemaRegistry,
    artifacts: ArtifactService,
    installations: Mapping[LeanEnvironment, LeanCheckerInstallation],
    provider_runtime: CapabilityProviderRuntime,
) -> tuple[
    tuple[LeanProofStateAdapter, LeanPremiseRetrievalAdapter],
    LeanExplorationInstallation,
]:
    """Register replayable exploratory Lean adapters."""

    mathlib = installations[LeanEnvironment.MATHLIB]
    core = installations[LeanEnvironment.CORE]
    semantics_uri = store.register_descriptor(
        kind="semantics",
        name="jacobian.lean4-exploration",
        version="1",
        definition={
            "description": (
                "exploratory Lean proof-state transitions and premise suggestions"
            ),
            "lean_version": core.lean_version,
            "lean_commit": core.lean_commit,
            "mathlib_commit": mathlib.mathlib_commit,
            "verification": "none; completed source must pass lean.check",
        },
    )
    transition_schema_uri = schemas.register(
        name="jacobian.lean4-proof-state-transition",
        version="1",
        schema=LeanProofStateTransitionArtifact.model_json_schema(),
    )
    retrieval_schema_uri = schemas.register(
        name="jacobian.lean4-premise-retrieval",
        version="1",
        schema=LeanPremiseRetrievalArtifact.model_json_schema(),
    )
    runtime = Path(__file__).resolve().parents[2] / "lean"
    repl = LeanExplorationReplRuntime(runtime, installations)
    resources = _Resources(
        store=store,
        artifacts=artifacts,
        semantics_uri=semantics_uri,
        transition_schema_uri=transition_schema_uri,
        retrieval_schema_uri=retrieval_schema_uri,
        installations=installations,
        runtime=runtime,
        provider_runtime=provider_runtime,
        repl=repl,
    )
    return (
        (
            LeanProofStateAdapter(resources),
            LeanPremiseRetrievalAdapter(resources),
        ),
        LeanExplorationInstallation(
            semantics_uri=semantics_uri,
            transition_schema_uri=transition_schema_uri,
            retrieval_schema_uri=retrieval_schema_uri,
        ),
    )


class LeanProofStateAdapter:
    def __init__(self, resources: _Resources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="lean.proof_state.apply_tactic",
            version="1",
            title="Apply one Lean tactic",
            description=(
                "Replay an explicit proof prefix, apply one tactic, and expose the "
                "resulting Lean goals or a structured rejection."
            ),
            provider="jacobian.lean4",
            provider_runtime=resources.provider_runtime,
            modes=(CapabilityMode.EXPLORE,),
            input_schema=LeanProofStateRequest.model_json_schema(),
            output_schema=LeanProofStateOutput.model_json_schema(),
            tags=("lean", "proof-state", "tactic", "exploration"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        try:
            validated = LeanProofStateRequest.model_validate(request.input)
            _validate_source_parts(
                validated.statement,
                (*validated.proof_prefix, validated.tactic),
            )
        except (ValidationError, ValueError) as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_LEAN_TRANSITION_REQUEST",
                    stage="request_validation",
                    message="The Lean statement or tactic sequence is invalid.",
                    hint=(
                        "Use one proposition and bounded tactic bodies without "
                        "commands, imports, declarations, sorry, or run_tac."
                    ),
                )
            ) from exc
        started = time.monotonic()
        installation = self.resources.installations[validated.environment]
        command = _proof_state_command(
            statement=validated.statement,
            proof_prefix=validated.proof_prefix,
        )
        responses = _run_repl(
            self.resources,
            command=command,
            tactic=validated.tactic,
            environment=validated.environment,
        )
        command_response, tactic_response = responses
        errors = (
            *_response_errors(command_response),
            *_response_errors(tactic_response),
        )
        if errors:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="LEAN_TACTIC_REJECTED",
                    stage="tactic_application",
                    message=f"Lean rejected the tactic transition: {errors[0][:500]}",
                    hint=(
                        "Inspect the current goals, revise the tactic or prefix, "
                        "and retry. A rejection is not a mathematical conclusion."
                    ),
                )
            )
        goals_value = tactic_response.get("goals", [])
        if not isinstance(goals_value, list) or any(
            not isinstance(goal, str) for goal in goals_value
        ):
            raise RuntimeError("Lean REPL returned malformed goals")
        goals = tuple(goals_value)
        replay_source = "\n  ".join((*validated.proof_prefix, validated.tactic))
        messages = tuple(
            message
            for response in responses
            for message in _response_messages(response)
        )
        artifact_payload = LeanProofStateTransitionArtifact(
            environment=validated.environment,
            statement=validated.statement,
            proof_prefix=validated.proof_prefix,
            tactic=validated.tactic,
            replay_source=replay_source,
            goals=goals,
            goal_count=len(goals),
            completed=(tactic_response.get("proofStatus") == "Completed" and not goals),
            messages=messages,
            lean_version=installation.lean_version,
            lean_commit=installation.lean_commit,
            mathlib_commit=installation.mathlib_commit,
        )
        artifact = self.resources.artifacts.put(
            schema_uri=self.resources.transition_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload=artifact_payload.model_dump(mode="json"),
            summary="replayable exploratory Lean proof-state transition",
        )
        output = LeanProofStateOutput(
            **artifact_payload.model_dump(mode="python"),
            transition_uri=artifact.artifact_uri,
        )
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(
                status=ExecutionStatus.COMPLETED,
                runtime_ms=_runtime_ms(started),
            ),
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description="one tactic applied after one explicit Lean proof prefix",
                parameters={
                    "environment": validated.environment.value,
                    "statement": validated.statement,
                },
                artifact_uri=artifact.artifact_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.COMPLETE,
                basis="Lean returned the complete successor-goal list for this step",
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=(
                    "pinned Lean elaboration of one replayable tactic transition; "
                    "this does not verify the theorem"
                ),
            ),
            artifact_uris=(artifact.artifact_uri,),
        )


class LeanPremiseRetrievalAdapter:
    def __init__(self, resources: _Resources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="lean.retrieve.premises",
            version="1",
            title="Retrieve Lean premises",
            description=(
                "Ask pinned Mathlib exact? for bounded candidate tactics at one "
                "explicit proof prefix; an empty result is non-exhaustive."
            ),
            provider="jacobian.lean4",
            provider_runtime=resources.provider_runtime,
            modes=(CapabilityMode.EXPLORE,),
            input_schema=LeanPremiseRetrievalRequest.model_json_schema(),
            output_schema=LeanPremiseRetrievalOutput.model_json_schema(),
            tags=("lean", "mathlib", "premise-retrieval", "exploration"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        try:
            validated = LeanPremiseRetrievalRequest.model_validate(request.input)
            _validate_source_parts(validated.statement, validated.proof_prefix)
        except (ValidationError, ValueError) as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_LEAN_RETRIEVAL_REQUEST",
                    stage="request_validation",
                    message="The Lean premise-retrieval request is invalid.",
                )
            ) from exc
        started = time.monotonic()
        environment = LeanEnvironment.MATHLIB
        installation = self.resources.installations[environment]
        command = _proof_state_command(
            statement=validated.statement,
            proof_prefix=validated.proof_prefix,
        )
        command_response, tactic_response = _run_repl(
            self.resources,
            command=command,
            tactic="exact?",
            environment=environment,
        )
        command_errors = _response_errors(command_response)
        tactic_errors = _response_errors(tactic_response)
        if command_errors:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="LEAN_RETRIEVAL_FAILED",
                    stage="premise_retrieval",
                    message=(
                        "Lean rejected the statement or proof prefix: "
                        f"{command_errors[0][:500]}"
                    ),
                    hint="Correct the statement or proof prefix and retry.",
                )
            )
        diagnostics = "\n".join(_response_messages(tactic_response))
        suggestions = [
            match.group("tactic").strip() for match in _SUGGESTION.finditer(diagnostics)
        ][: validated.limit]
        if tactic_errors and not any(
            "`exact?` could not close the goal" in error for error in tactic_errors
        ):
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="LEAN_RETRIEVAL_FAILED",
                    stage="premise_retrieval",
                    message=f"Mathlib exact? failed: {tactic_errors[0][:500]}",
                    hint="Correct the statement or proof prefix and retry.",
                )
            )
        candidates = tuple(
            LeanPremiseCandidate(
                rank=index,
                tactic=suggestion,
                declaration_names=tuple(sorted(set(_DECLARATION.findall(suggestion)))),
            )
            for index, suggestion in enumerate(suggestions, start=1)
        )
        artifact_payload = LeanPremiseRetrievalArtifact(
            statement=validated.statement,
            proof_prefix=validated.proof_prefix,
            candidates=candidates,
            lean_version=installation.lean_version,
            lean_commit=installation.lean_commit,
            mathlib_commit=installation.mathlib_commit or "",
        )
        artifact = self.resources.artifacts.put(
            schema_uri=self.resources.retrieval_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload=artifact_payload.model_dump(mode="json"),
            summary="non-exhaustive pinned Mathlib premise suggestions",
        )
        output = LeanPremiseRetrievalOutput(
            **artifact_payload.model_dump(mode="python"),
            retrieval_uri=artifact.artifact_uri,
        )
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(
                status=ExecutionStatus.COMPLETED,
                runtime_ms=_runtime_ms(started),
            ),
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description="one explicit Lean goal under pinned Mathlib exact?",
                parameters={
                    "environment": "MATHLIB",
                    "statement": validated.statement,
                    "limit": validated.limit,
                },
                artifact_uri=artifact.artifact_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.PARTIAL,
                basis=(
                    "Mathlib exact? suggestions are bounded and non-exhaustive; "
                    "no suggestion is not a proof of absence"
                ),
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=(
                    "candidate tactics were emitted by pinned Mathlib exact?; "
                    "they remain unverified until lean.check accepts exact source"
                ),
            ),
            artifact_uris=(artifact.artifact_uri,),
        )


def _validate_source_parts(statement: str, tactics: tuple[str, ...]) -> None:
    if "\n" in statement or "\r" in statement or ":=" in statement:
        raise ValueError("statement must be one Lean expression")
    if _FORBIDDEN.search(statement):
        raise ValueError("statement contains a forbidden command")
    for tactic in tactics:
        if "\x00" in tactic or _FORBIDDEN.search(tactic):
            raise ValueError("tactic contains a forbidden command")


def _proof_state_command(*, statement: str, proof_prefix: tuple[str, ...]) -> str:
    proof = "\n".join(f"  {line}" for line in (*proof_prefix, "sorry"))
    return f"example : {statement} := by\n{proof}"


def _run_repl(
    resources: _Resources,
    *,
    command: str,
    tactic: str,
    environment: LeanEnvironment,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return resources.repl.execute(
        command=command,
        tactic=tactic,
        environment=environment,
    )


def _response_messages(response: Mapping[str, Any]) -> tuple[str, ...]:
    messages: list[str] = []
    message = response.get("message")
    if isinstance(message, str):
        messages.append(message)
    structured = response.get("messages")
    if isinstance(structured, list):
        for item in structured:
            if not isinstance(item, Mapping):
                continue
            data = item.get("data")
            if isinstance(data, str):
                messages.append(data)
    return tuple(messages)


def _response_errors(response: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    message = response.get("message")
    if isinstance(message, str):
        errors.append(message)
    structured = response.get("messages")
    if isinstance(structured, list):
        for item in structured:
            if not isinstance(item, Mapping) or item.get("severity") != "error":
                continue
            data = item.get("data")
            if isinstance(data, str):
                errors.append(data)
    return tuple(errors)


def _runtime_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))
