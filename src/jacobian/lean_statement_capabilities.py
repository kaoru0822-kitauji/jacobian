"""Atomic Lean statement proposal, repair, and comparison adapters.

Three domain-atomic capabilities, each producing exactly one inspectable
artifact:

* ``lean.statement.propose`` — either type-check one proposed Lean statement
  against an informal claim or directly elaborate one proposition. Returns
  durable environment-bound elaboration details; does NOT certify truth or
  that a formal statement matches an informal claim.

* ``lean.proof.repair_once`` — apply one deterministic syntactic repair
  to a failing Lean proof using compiler feedback. Returns a diff artifact
  and compile status; does NOT certify the repaired proof proves the
  theorem.

* ``lean.statement.compare`` — compare two Lean statements syntactically
  and by axiom set. Fail-closed: never claims semantic equivalence; if
  elaboration cannot be checked, reports that honestly.

When the Lean binary is not on PATH, each adapter returns honest
unavailable/diagnostic behavior rather than a silent success.
"""

from __future__ import annotations

import difflib
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from jacobian.artifacts import ArtifactService
from jacobian.canonical import canonicalize_json
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
    LeanElaborationDiagnostic,
    LeanElaborationOption,
    LeanProofRepairArtifact,
    LeanProofRepairOutput,
    LeanProofRepairRequest,
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
    elaborated_expression: str | None = None
    used_imports: tuple[str, ...] = ()
    used_declarations: tuple[str, ...] = ()
    options: tuple[LeanElaborationOption, ...] = ()


_DIRECT_ELABORATION_IMPORTS = ("Init.Prelude",)
_DIRECT_ELABORATION_OPTIONS = (
    LeanElaborationOption(name="pp.all", value="true"),
    LeanElaborationOption(name="pp.explicit", value="true"),
    LeanElaborationOption(name="pp.universes", value="true"),
)
_LEAN_NAME = re.compile(r"\b[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z0-9_']+)*\b")
_LEAN_KEYWORDS = frozenset(
    {
        "Prop",
        "Sort",
        "Type",
        "false",
        "fun",
        "let",
        "match",
        "true",
    }
)


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


def _elaborate_proposition(
    statement: str,
    *,
    timeout_seconds: int = _ELAPSED_TIMEOUT_SECONDS,
) -> _ElaborationResult:
    """Elaborate one expression against expected type ``Prop``."""

    if shutil.which("lean") is None:
        raise _LeanUnavailableError("lean is not on PATH")
    _validate_statement(statement)
    source = "\n".join(
        (
            "set_option pp.all true in",
            "set_option pp.explicit true in",
            "set_option pp.universes true in",
            f"#check ({statement} : Prop)",
        )
    )
    output = _execute_lean_source(source, timeout_seconds=timeout_seconds)
    messages = tuple(_parse_lean_messages(output))
    errors = tuple(message for message in messages if "error:" in message.lower())
    expression = None if errors else _parse_elaborated_expression(output)
    if not errors and expression is None:
        errors = ("error: Lean did not emit the elaborated proposition",)
        messages = (*messages, *errors)
    declarations = (
        tuple(
            sorted(
                name
                for name in set(_LEAN_NAME.findall(expression))
                if name not in _LEAN_KEYWORDS
            )
        )
        if expression is not None
        else ()
    )
    return _ElaborationResult(
        elaborates=expression is not None,
        sorry_count=0,
        messages=messages,
        errors=errors,
        elaborated_expression=expression,
        used_imports=_DIRECT_ELABORATION_IMPORTS,
        used_declarations=declarations,
        options=_DIRECT_ELABORATION_OPTIONS,
    )


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
    output = _execute_lean_source(source, timeout_seconds=timeout_seconds)
    messages = _parse_lean_messages(output)
    errors = tuple(m for m in messages if "error:" in m.lower())
    elaborates = len(errors) == 0
    return _ElaborationResult(
        elaborates=elaborates,
        sorry_count=1 if elaborates else 0,
        messages=tuple(messages),
        errors=errors,
    )


def _execute_lean_source(source: str, *, timeout_seconds: int) -> str:
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
    return (result.stdout or "") + (result.stderr or "")


def _parse_elaborated_expression(output: str) -> str | None:
    match = re.search(r"\binfo:\s*(.+?)\s*:\s*Prop(?:\s|$)", output, re.DOTALL)
    if match is None:
        return None
    return " ".join(match.group(1).split())


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


def _diagnostics(messages: tuple[str, ...]) -> tuple[LeanElaborationDiagnostic, ...]:
    diagnostics: list[LeanElaborationDiagnostic] = []
    for message in messages:
        lowered = message.lower()
        severity: Literal["ERROR", "WARNING", "INFO"] = (
            "ERROR"
            if "error:" in lowered
            else ("WARNING" if "warning:" in lowered else "INFO")
        )
        diagnostics.append(
            LeanElaborationDiagnostic(severity=severity, message=message)
        )
    return tuple(diagnostics)


def _environment_digest(
    *,
    environment: LeanEnvironment,
    lean_version: str,
    lean_commit: str,
    mathlib_commit: str | None,
    imports: tuple[str, ...],
    options: tuple[LeanElaborationOption, ...],
) -> str:
    payload = {
        "environment": environment.value,
        "lean_version": lean_version,
        "lean_commit": lean_commit,
        "mathlib_commit": mathlib_commit,
        "imports": list(imports),
        "options": [option.model_dump(mode="json") for option in options],
    }
    return "sha256:" + hashlib.sha256(canonicalize_json(payload)).hexdigest()


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
# Deterministic repair strategies (exactly one attempt).
# ---------------------------------------------------------------------------


def _attempt_repair(
    failing_proof: str,
    compiler_errors: tuple[str, ...],
) -> tuple[str, str]:
    """Return ``(repaired_proof, strategy_name)``.

    Picks exactly one deterministic strategy based on compiler feedback.
    If no strategy applies, returns the unchanged proof with strategy
    ``"none"``.
    """

    errors_text = " ".join(compiler_errors).lower()

    # Strategy 1: missing `by` keyword.
    if not failing_proof.strip().startswith("by") and (
        "expected" in errors_text or "tactic" in errors_text or "term" in errors_text
    ):
        return (f"by\n{_indent_proof(failing_proof)}", "add_by")

    # Strategy 2: unresolved goals — append sorry to close them.
    if "unsolved" in errors_text or "goal" in errors_text:
        indented = _indent_proof(failing_proof)
        if not indented.rstrip().endswith("sorry"):
            return (f"{indented}\n  sorry", "append_sorry")

    # Strategy 3: deprecated `rw` → `rewrite`.
    if re.search(r"\brw\b", failing_proof) and (
        "deprecated" in errors_text or "rw" in errors_text
    ):
        return (
            re.sub(r"\brw\b", "rewrite", failing_proof),
            "fix_rw_to_rewrite",
        )

    return (failing_proof, "none")


def _compute_diff(old: str, new: str) -> str:
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile="failing_proof",
        tofile="repaired_proof",
    )
    return "".join(diff)


# ---------------------------------------------------------------------------
# Installation metadata.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LeanStatementInstallation:
    semantics_uri: str
    proposal_schema_uri: str
    repair_schema_uri: str
    comparison_schema_uri: str


@dataclass(frozen=True, slots=True)
class _Resources:
    store: ArtifactStore
    artifacts: ArtifactService
    semantics_uri: str
    proposal_schema_uri: str
    repair_schema_uri: str
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
        LeanProofRepairAdapter,
        LeanStatementCompareAdapter,
    ],
    LeanStatementInstallation,
]:
    """Register schemas and return the three atomic Lean statement adapters."""

    if provider_runtime is None:
        provider_runtime = jacobian_provider_runtime(
            "jacobian.lean4",
            features=("lean-statement", "elaboration", "repair", "comparison"),
        )
    semantics_uri = store.register_descriptor(
        kind="semantics",
        name="jacobian.lean4-statement",
        version="1",
        definition={
            "description": (
                "atomic Lean statement proposal, direct proposition "
                "elaboration, proof repair, and statement comparison; "
                "none certify theoremhood, truth, or semantic intent"
            ),
            "verification": (
                "none; elaboration establishes a well-typed Prop expression "
                "in the bound environment but does not establish truth"
            ),
        },
    )
    proposal_schema_uri = schemas.register(
        name="jacobian.lean4-statement-proposal",
        version="2",
        schema=LeanStatementProposalArtifact.model_json_schema(),
    )
    repair_schema_uri = schemas.register(
        name="jacobian.lean4-proof-repair",
        version="1",
        schema=LeanProofRepairArtifact.model_json_schema(),
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
        repair_schema_uri=repair_schema_uri,
        comparison_schema_uri=comparison_schema_uri,
        provider_runtime=provider_runtime,
    )
    adapters = (
        LeanStatementProposalAdapter(resources),
        LeanProofRepairAdapter(resources),
        LeanStatementCompareAdapter(resources),
    )
    installation = LeanStatementInstallation(
        semantics_uri=semantics_uri,
        proposal_schema_uri=proposal_schema_uri,
        repair_schema_uri=repair_schema_uri,
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
                "Validate either a proposed statement against an informal "
                "claim or directly elaborate one proposition without an "
                "informal claim. Returns durable environment-bound elaboration "
                "details. It does not establish truth or semantic intent."
            ),
            provider="jacobian.lean4",
            provider_runtime=resources.provider_runtime,
            modes=(CapabilityMode.EXPLORE,),
            input_schema=LeanStatementProposalRequest.model_json_schema(),
            output_schema=LeanStatementProposalOutput.model_json_schema(),
            tags=("lean", "statement", "elaboration", "proposal", "proposition"),
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
            elaboration = (
                _elaborate_statement(validated.proposed_statement)
                if validated.operation == "PROPOSE"
                else _elaborate_proposition(validated.proposed_statement)
            )
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
        imports = elaboration.used_imports
        options = elaboration.options
        artifact_payload = LeanStatementProposalArtifact(
            operation=validated.operation,
            environment=validated.environment,
            environment_digest=_environment_digest(
                environment=validated.environment,
                lean_version=version,
                lean_commit=commit,
                mathlib_commit=None,
                imports=imports,
                options=options,
            ),
            informal_claim=validated.informal_claim,
            proposed_statement=validated.proposed_statement,
            elaborates=elaboration.elaborates,
            elaborated_expression=elaboration.elaborated_expression,
            sorry_count=elaboration.sorry_count,
            goals=(),
            messages=elaboration.messages,
            diagnostics=_diagnostics(elaboration.messages),
            used_imports=imports,
            used_declarations=elaboration.used_declarations,
            options=options,
            lean_version=version,
            lean_commit=commit,
            source_locator=validated.source_locator,
        )
        artifact = self.resources.artifacts.put(
            schema_uri=self.resources.proposal_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload=artifact_payload.model_dump(mode="json"),
            summary=(
                "Lean statement operation with elaboration status "
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
                description=(
                    "one Lean proposition directly elaborated against Prop"
                    if validated.operation == "ELABORATE_PROPOSITION"
                    else "one Lean statement elaborated with sorry as proof"
                ),
                parameters={
                    "operation": validated.operation,
                    "environment": validated.environment.value,
                    "proposed_statement": validated.proposed_statement,
                    "environment_digest": artifact_payload.environment_digest,
                },
                artifact_uri=artifact.artifact_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.COMPLETE,
                basis=(
                    "the pinned Lean frontend elaborated the proposition or "
                    "reported complete diagnostics for this bounded request"
                ),
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=(
                    "Lean elaboration reports whether the expression is a "
                    "well-typed proposition in the bound environment; it does "
                    "not establish truth, theoremhood, or semantic intent"
                ),
            ),
            artifact_uris=(artifact.artifact_uri,),
        )


# ---------------------------------------------------------------------------
# Adapter 2: lean.proof.repair_once
# ---------------------------------------------------------------------------


class LeanProofRepairAdapter:
    """Apply one deterministic repair to a failing Lean proof."""

    def __init__(self, resources: _Resources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="lean.proof.repair_once",
            version="1",
            title="Attempt one Lean proof repair from compiler feedback",
            description=(
                "Apply exactly one deterministic syntactic repair strategy "
                "based on compiler error messages. Returns a unified diff and "
                "compile status. Does NOT certify that the repaired proof "
                "proves the theorem."
            ),
            provider="jacobian.lean4",
            provider_runtime=resources.provider_runtime,
            modes=(CapabilityMode.EXPLORE,),
            input_schema=LeanProofRepairRequest.model_json_schema(),
            output_schema=LeanProofRepairOutput.model_json_schema(),
            tags=("lean", "proof", "repair", "diff"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        try:
            validated = LeanProofRepairRequest.model_validate(request.input)
            _validate_statement(validated.statement)
            _validate_proof(validated.failing_proof)
        except (ValidationError, ValueError) as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_LEAN_PROOF_REPAIR_REQUEST",
                    stage="request_validation",
                    message="The Lean proof repair request is invalid.",
                    hint=(
                        "Provide a single-line statement, a multi-line proof, "
                        "and optional compiler error messages."
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
                        "supported by lean.proof.repair_once."
                    ),
                    hint="Set environment to CORE for proof repair.",
                )
            )
        repaired_proof, strategy = _attempt_repair(
            validated.failing_proof,
            validated.compiler_errors,
        )
        diff = _compute_diff(validated.failing_proof, repaired_proof)
        compiles = False
        compile_checked = False
        sorry_count = 0
        messages: tuple[str, ...] = ()
        if strategy != "none":
            try:
                result = _check_proof(validated.statement, repaired_proof)
                compiles = result.elaborates
                compile_checked = True
                sorry_count = result.sorry_count
                messages = result.messages
            except _LeanUnavailableError:
                pass
        version, commit = _lean_version_info()
        artifact_payload = LeanProofRepairArtifact(
            environment=validated.environment,
            statement=validated.statement,
            failing_proof=validated.failing_proof,
            repaired_proof=repaired_proof,
            diff=diff,
            repair_strategy=strategy,
            compiles=compiles,
            compile_checked=compile_checked,
            sorry_count=sorry_count,
            messages=messages,
            lean_version=version,
            lean_commit=commit,
        )
        artifact = self.resources.artifacts.put(
            schema_uri=self.resources.repair_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload=artifact_payload.model_dump(mode="json"),
            summary=(
                f"one Lean proof repair attempt (strategy={strategy}, "
                f"compiles={compiles})"
            ),
        )
        output = LeanProofRepairOutput(
            **artifact_payload.model_dump(mode="python"),
            repair_uri=artifact.artifact_uri,
        )
        completeness_status = (
            CapabilityCompletenessStatus.COMPLETE
            if compile_checked
            else CapabilityCompletenessStatus.PARTIAL
        )
        completeness_basis = (
            "the repaired proof was elaborated by the pinned Lean kernel"
            if compile_checked
            else "the repair diff was produced but compile status was not "
            "checked because Lean is unavailable"
        )
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description="one deterministic repair attempt on one Lean proof",
                parameters={
                    "environment": validated.environment.value,
                    "statement": validated.statement,
                    "repair_strategy": strategy,
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
                    "deterministic syntactic repair with optional elaboration "
                    "check; this does not certify that the proof proves the "
                    "theorem"
                ),
            ),
            artifact_uris=(artifact.artifact_uri,),
        )


# ---------------------------------------------------------------------------
# Adapter 3: lean.statement.compare
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
