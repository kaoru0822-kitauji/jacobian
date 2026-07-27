"""Atomic Lean statement proposal and comparison adapters.

Two domain-atomic capabilities, each producing exactly one inspectable
artifact:

* ``lean.statement.propose`` — type-check one proposed Lean statement
  against an informal claim. Returns elaboration status; does NOT certify
  that the formal statement matches the informal claim.

* ``lean.statement.compare`` — compare two Lean statements syntactically
  and by axiom set. Fail-closed: never claims semantic equivalence; if
  elaboration cannot be checked, reports that honestly.

When the Lean binary is not on PATH, each adapter returns honest
unavailable/diagnostic behavior rather than a silent success.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path

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
from jacobian.contracts.lean_statement import (
    LeanStatementComparisonArtifact,
    LeanStatementComparisonOutput,
    LeanStatementComparisonRequest,
    LeanStatementProposalArtifact,
    LeanStatementProposalOutput,
    LeanStatementProposalRequest,
)
from jacobian.contracts.results import Execution, ExecutionStatus
from jacobian.provider_runtime import jacobian_provider_runtime
from jacobian.schema_registry import SchemaRegistry
from jacobian.store import ArtifactStore

# ---------------------------------------------------------------------------
# Security: block dangerous Lean commands in user-supplied text.
# Statements block sorry/admit (the statement is the claim, not a proof).
# Proofs block only structural commands that could escape the proof block.
# ---------------------------------------------------------------------------

_FORBIDDEN_STATEMENT = re.compile(
    r"\b(?:admit|axiom|elab|import|macro|native_decide|opaque|run_tac|"
    r"set_option|sorry|syntax|unsafe)\b|#",
    re.IGNORECASE,
)

_FORBIDDEN_PROOF = re.compile(
    r"\b(?:import|macro|syntax|unsafe|set_option|run_tac|native_decide)\b|#",
    re.IGNORECASE,
)

_ELAPSED_TIMEOUT_SECONDS = 30


class _LeanUnavailableError(RuntimeError):
    """Lean is not available on PATH or timed out during elaboration."""


# ---------------------------------------------------------------------------
# Elaboration probe — thin subprocess wrapper around the `lean` binary.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _ElaborationResult:
    elaborates: bool
    sorry_count: int
    messages: tuple[str, ...]
    errors: tuple[str, ...]


@cache
def _lean_version_info() -> tuple[str, str]:
    """Return (version, commit) from ``lean --version``; ``unknown`` on failure."""

    lean_bin = shutil.which("lean")
    if lean_bin is None:
        return ("unknown", "unknown")
    try:
        result = subprocess.run(
            [lean_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ("unknown", "unknown")
    output = result.stdout + result.stderr
    version_match = re.search(r"version\s+([^\s,]+)", output)
    commit_match = re.search(r"commit\s+([^\s,)]+)", output)
    return (
        version_match.group(1) if version_match else "unknown",
        commit_match.group(1) if commit_match else "unknown",
    )


def _elaborate_statement(
    statement: str,
    *,
    timeout_seconds: int = _ELAPSED_TIMEOUT_SECONDS,
) -> _ElaborationResult:
    """Elaborate ``example : {statement} := by sorry`` via the ``lean`` binary."""

    lean_bin = shutil.which("lean")
    if lean_bin is None:
        raise _LeanUnavailableError("lean is not on PATH")
    _validate_statement(statement)
    source = f"example : {statement} := by sorry"
    return _run_lean_source(source, timeout_seconds=timeout_seconds)


def _check_proof(
    statement: str,
    proof: str,
    *,
    timeout_seconds: int = _ELAPSED_TIMEOUT_SECONDS,
) -> _ElaborationResult:
    """Check whether ``example : {statement} := by {proof}`` elaborates."""

    lean_bin = shutil.which("lean")
    if lean_bin is None:
        raise _LeanUnavailableError("lean is not on PATH")
    _validate_statement(statement)
    _validate_proof(proof)
    source = f"example : {statement} := by\n{_indent_proof(proof)}"
    return _run_lean_source(source, timeout_seconds=timeout_seconds)


def _run_lean_source(
    source: str,
    *,
    timeout_seconds: int,
) -> _ElaborationResult:
    fd, temp_path = tempfile.mkstemp(suffix=".lean")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(source)
        lean_bin = shutil.which("lean")
        if lean_bin is None:
            raise _LeanUnavailableError("lean is not on PATH")
        result = subprocess.run(
            [lean_bin, temp_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise _LeanUnavailableError(f"lean timed out after {timeout_seconds}s") from exc
    finally:
        Path(temp_path).unlink(missing_ok=True)
    output = (result.stdout or "") + (result.stderr or "")
    messages = _parse_lean_messages(output)
    errors = tuple(m for m in messages if "error:" in m.lower())
    elaborates = len(errors) == 0
    return _ElaborationResult(
        elaborates=elaborates,
        sorry_count=1 if elaborates else 0,
        messages=tuple(messages),
        errors=errors,
    )


def _parse_lean_messages(output: str) -> list[str]:
    messages: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(
            r"^.*:\d+:\d+:\s*(error|warning|info):", stripped
        ) or stripped.lower().startswith(("error:", "warning:", "info:")):
            messages.append(stripped)
    return messages


def _indent_proof(proof: str) -> str:
    lines = proof.splitlines()
    return "\n".join(f"  {line}" for line in lines)


# ---------------------------------------------------------------------------
# Validation helpers.
# ---------------------------------------------------------------------------


def _validate_statement(statement: str) -> None:
    if "\n" in statement or "\r" in statement:
        raise ValueError("statement must be one Lean expression")
    if ":=" in statement:
        raise ValueError("statement must not contain ':='")
    if _FORBIDDEN_STATEMENT.search(statement):
        raise ValueError("statement contains a forbidden command")


def _validate_proof(proof: str) -> None:
    if "\x00" in proof:
        raise ValueError("proof contains a null byte")
    if _FORBIDDEN_PROOF.search(proof):
        raise ValueError("proof contains a dangerous command")


# ---------------------------------------------------------------------------
# Installation metadata.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LeanStatementInstallation:
    semantics_uri: str
    proposal_schema_uri: str
    comparison_schema_uri: str


@dataclass(frozen=True, slots=True)
class _Resources:
    store: ArtifactStore
    artifacts: ArtifactService
    semantics_uri: str
    proposal_schema_uri: str
    comparison_schema_uri: str
    provider_runtime: CapabilityProviderRuntime


def install_lean_statement_capabilities(
    store: ArtifactStore,
    schemas: SchemaRegistry,
    artifacts: ArtifactService,
    provider_runtime: CapabilityProviderRuntime | None = None,
) -> tuple[
    tuple[
        LeanStatementProposalAdapter,
        LeanStatementCompareAdapter,
    ],
    LeanStatementInstallation,
]:
    """Register schemas and return the three atomic Lean statement adapters."""

    if provider_runtime is None:
        provider_runtime = jacobian_provider_runtime(
            "jacobian.lean4",
            features=("lean-statement", "elaboration", "comparison"),
        )
    semantics_uri = store.register_descriptor(
        kind="semantics",
        name="jacobian.lean4-statement",
        version="1",
        definition={
            "description": (
                "atomic Lean statement proposal and statement comparison; "
                "neither certifies semantic intent"
            ),
            "verification": "none; type-checking does not certify intent",
        },
    )
    proposal_schema_uri = schemas.register(
        name="jacobian.lean4-statement-proposal",
        version="1",
        schema=LeanStatementProposalArtifact.model_json_schema(),
    )
    comparison_schema_uri = schemas.register(
        name="jacobian.lean4-statement-comparison",
        version="1",
        schema=LeanStatementComparisonArtifact.model_json_schema(),
    )
    resources = _Resources(
        store=store,
        artifacts=artifacts,
        semantics_uri=semantics_uri,
        proposal_schema_uri=proposal_schema_uri,
        comparison_schema_uri=comparison_schema_uri,
        provider_runtime=provider_runtime,
    )
    adapters = (
        LeanStatementProposalAdapter(resources),
        LeanStatementCompareAdapter(resources),
    )
    installation = LeanStatementInstallation(
        semantics_uri=semantics_uri,
        proposal_schema_uri=proposal_schema_uri,
        comparison_schema_uri=comparison_schema_uri,
    )
    return adapters, installation


# ---------------------------------------------------------------------------
# Adapter 1: lean.statement.propose
# ---------------------------------------------------------------------------


class LeanStatementProposalAdapter:
    """Type-check one proposed Lean statement; no semantic certification."""

    def __init__(self, resources: _Resources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="lean.statement.propose",
            version="1",
            title="Propose one Lean statement with type-check status",
            description=(
                "Validate that a proposed Lean statement elaborates under the "
                "pinned Lean kernel. Returns elaboration status, sorry count, "
                "and compiler messages. Does NOT certify that the formal "
                "statement matches the informal claim."
            ),
            provider="jacobian.lean4",
            provider_runtime=resources.provider_runtime,
            modes=(CapabilityMode.EXPLORE,),
            input_schema=LeanStatementProposalRequest.model_json_schema(),
            output_schema=LeanStatementProposalOutput.model_json_schema(),
            tags=("lean", "statement", "elaboration", "proposal"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        try:
            validated = LeanStatementProposalRequest.model_validate(request.input)
            _validate_statement(validated.proposed_statement)
        except (ValidationError, ValueError) as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_LEAN_STATEMENT_PROPOSAL",
                    stage="request_validation",
                    message="The Lean statement proposal is invalid.",
                    hint=(
                        "Provide one single-line Lean expression without sorry, "
                        "admit, import, or other forbidden commands."
                    ),
                )
            ) from exc
        if validated.environment is not LeanEnvironment.CORE:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="LEAN_ENVIRONMENT_UNSUPPORTED",
                    stage="environment_resolution",
                    message=(
                        f"Environment {validated.environment.value} is not "
                        "supported by lean.statement.propose; use CORE or "
                        "lean.check for MATHLIB statements."
                    ),
                    hint="Set environment to CORE for statement type-checking.",
                )
            )
        try:
            elaboration = _elaborate_statement(validated.proposed_statement)
        except _LeanUnavailableError as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="LEAN_BACKEND_UNAVAILABLE",
                    stage="elaboration",
                    message=str(exc),
                    hint=(
                        "Install Lean or elan and ensure the `lean` binary is on "
                        "PATH, then retry."
                    ),
                )
            ) from exc
        version, commit = _lean_version_info()
        artifact_payload = LeanStatementProposalArtifact(
            environment=validated.environment,
            informal_claim=validated.informal_claim,
            proposed_statement=validated.proposed_statement,
            elaborates=elaboration.elaborates,
            sorry_count=elaboration.sorry_count,
            goals=(),
            messages=elaboration.messages,
            lean_version=version,
            lean_commit=commit,
            source_locator=validated.source_locator,
        )
        artifact = self.resources.artifacts.put(
            schema_uri=self.resources.proposal_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload=artifact_payload.model_dump(mode="json"),
            summary=(
                "Lean statement proposal with type-check status "
                f"(elaborates={elaboration.elaborates})"
            ),
        )
        output = LeanStatementProposalOutput(
            **artifact_payload.model_dump(mode="python"),
            proposal_uri=artifact.artifact_uri,
        )
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description="one Lean statement elaborated with sorry as proof",
                parameters={
                    "environment": validated.environment.value,
                    "proposed_statement": validated.proposed_statement,
                },
                artifact_uri=artifact.artifact_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.COMPLETE,
                basis=(
                    "the pinned Lean kernel elaborated the statement or "
                    "reported elaboration errors"
                ),
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=(
                    "Lean elaboration confirms the statement type-checks; "
                    "this does not certify that the formal statement matches "
                    "the informal claim"
                ),
            ),
            artifact_uris=(artifact.artifact_uri,),
        )


# ---------------------------------------------------------------------------
# Adapter 2: lean.statement.compare
# ---------------------------------------------------------------------------


class LeanStatementCompareAdapter:
    """Compare two Lean statements syntactically and by axiom set."""

    def __init__(self, resources: _Resources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="lean.statement.compare",
            version="1",
            title="Compare two Lean statements and axiom sets (fail-closed)",
            description=(
                "Compare two Lean statements by syntactic identity and axiom "
                "set identity. Optionally elaborates both to report "
                "elaboration status. Never claims semantic equivalence; "
                "fail-closed when elaboration cannot be checked."
            ),
            provider="jacobian.lean4",
            provider_runtime=resources.provider_runtime,
            modes=(CapabilityMode.EXPLORE,),
            input_schema=LeanStatementComparisonRequest.model_json_schema(),
            output_schema=LeanStatementComparisonOutput.model_json_schema(),
            tags=("lean", "statement", "comparison", "axiom-set"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        try:
            validated = LeanStatementComparisonRequest.model_validate(request.input)
            _validate_statement(validated.statement_a)
            _validate_statement(validated.statement_b)
        except (ValidationError, ValueError) as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_LEAN_STATEMENT_COMPARISON",
                    stage="request_validation",
                    message="The Lean statement comparison request is invalid.",
                    hint=(
                        "Provide two single-line Lean expressions without "
                        "sorry, admit, import, or other forbidden commands."
                    ),
                )
            ) from exc
        if validated.environment is not LeanEnvironment.CORE:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="LEAN_ENVIRONMENT_UNSUPPORTED",
                    stage="environment_resolution",
                    message=(
                        f"Environment {validated.environment.value} is not "
                        "supported by lean.statement.compare."
                    ),
                    hint="Set environment to CORE for statement comparison.",
                )
            )
        statements_identical = _normalize_whitespace(
            validated.statement_a
        ) == _normalize_whitespace(validated.statement_b)
        axiom_sets_identical = set(validated.axiom_set_a) == set(validated.axiom_set_b)
        both_elaborate = False
        elaboration_checked = False
        elaboration_messages_a: tuple[str, ...] = ()
        elaboration_messages_b: tuple[str, ...] = ()
        try:
            result_a = _elaborate_statement(validated.statement_a)
            result_b = _elaborate_statement(validated.statement_b)
            elaboration_checked = True
            both_elaborate = result_a.elaborates and result_b.elaborates
            elaboration_messages_a = result_a.messages
            elaboration_messages_b = result_b.messages
        except _LeanUnavailableError:
            pass
        version, commit = _lean_version_info()
        artifact_payload = LeanStatementComparisonArtifact(
            environment=validated.environment,
            statement_a=validated.statement_a,
            statement_b=validated.statement_b,
            axiom_set_a=validated.axiom_set_a,
            axiom_set_b=validated.axiom_set_b,
            statements_identical=statements_identical,
            axiom_sets_identical=axiom_sets_identical,
            both_elaborate=both_elaborate,
            elaboration_checked=elaboration_checked,
            elaboration_messages_a=elaboration_messages_a,
            elaboration_messages_b=elaboration_messages_b,
            lean_version=version,
            lean_commit=commit,
        )
        artifact = self.resources.artifacts.put(
            schema_uri=self.resources.comparison_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload=artifact_payload.model_dump(mode="json"),
            summary=(
                f"Lean statement comparison (identical={statements_identical}, "
                f"axioms_identical={axiom_sets_identical}, "
                f"elaboration_checked={elaboration_checked})"
            ),
        )
        output = LeanStatementComparisonOutput(
            **artifact_payload.model_dump(mode="python"),
            comparison_uri=artifact.artifact_uri,
        )
        completeness_status = (
            CapabilityCompletenessStatus.COMPLETE
            if elaboration_checked
            else CapabilityCompletenessStatus.PARTIAL
        )
        completeness_basis = (
            "both statements were elaborated and compared syntactically and "
            "by axiom set"
            if elaboration_checked
            else "syntactic and axiom-set comparison completed; elaboration "
            "was not checked because Lean is unavailable"
        )
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description=(
                    "syntactic and axiom-set comparison of two Lean statements"
                ),
                parameters={
                    "environment": validated.environment.value,
                    "statement_a": validated.statement_a,
                    "statement_b": validated.statement_b,
                },
                artifact_uri=artifact.artifact_uri,
            ),
            completeness=CapabilityCompleteness(
                status=completeness_status,
                basis=completeness_basis,
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=(
                    "deterministic syntactic and axiom-set comparison; "
                    "this does not certify semantic equivalence of the "
                    "statements"
                ),
            ),
            artifact_uris=(artifact.artifact_uri,),
        )


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())
