"""Bounded CaDiCaL exploration adapters for SAT evidence production."""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from jacobian.bounded_process import BoundedProcessResult, run_bounded_process
from jacobian.capabilities import CapabilityAdapter, CapabilityInvocationError
from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityCompleteness,
    CapabilityCompletenessStatus,
    CapabilityDescriptor,
    CapabilityDiagnostic,
    CapabilityMode,
    CapabilityProviderAvailability,
    CapabilityProviderDigestKind,
    CapabilityProviderRuntime,
    CapabilityRequest,
    CapabilityResult,
    CapabilityScope,
)
from jacobian.contracts.results import Execution, ExecutionStatus
from jacobian.contracts.sat import (
    CanonicalCnf,
    SatExplorationBudget,
    SatExplorationRequest,
    SatModelFindOutput,
    SatUnsatProofFindOutput,
)
from jacobian.provider_runtime import CADICAL_VERSION
from jacobian.sat import ResolvedSatCnf, SatArtifactError, SatArtifactService
from jacobian.schema_registry import model_schema

CADICAL_STDOUT_LIMIT = 16_000_000
CADICAL_STDERR_LIMIT = 64_000
CADICAL_PROOF_LIMIT = 6_000_000

_SolverStatus = Literal["SATISFIABLE", "UNSATISFIABLE", "UNKNOWN"]


@dataclass(frozen=True, slots=True)
class _CadicalRun:
    execution_status: ExecutionStatus
    runtime_ms: int
    solver_status: _SolverStatus | None = None
    model_literals: tuple[int, ...] = ()
    proof: bytes | None = None
    diagnostic: CapabilityDiagnostic | None = None


def install_cadical_capabilities(
    sat: SatArtifactService,
    runtime: CapabilityProviderRuntime,
    *,
    executable: str | Path | None = None,
) -> tuple[CapabilityAdapter, CapabilityAdapter]:
    """Install model and proof producers for one exact available runtime."""

    if (
        runtime.provider != "cadical"
        or runtime.availability is not CapabilityProviderAvailability.AVAILABLE
        or runtime.version != CADICAL_VERSION
        or runtime.digest is None
        or runtime.digest_kind is not CapabilityProviderDigestKind.EXECUTABLE
    ):
        raise ValueError("CaDiCaL capabilities require the pinned available runtime")
    configured = runtime.configuration.get("executable")
    selected = executable if executable is not None else configured
    if not isinstance(selected, (str, Path)):
        raise ValueError("CaDiCaL runtime does not identify its executable")
    resolved = Path(selected).resolve(strict=True)
    if (
        configured is not None
        and Path(str(configured)).resolve(strict=True) != resolved
    ):
        raise ValueError("CaDiCaL executable differs from its runtime identity")
    backend = _CadicalBackend(runtime=runtime, executable=resolved)
    return (
        CadicalModelFindAdapter(sat=sat, backend=backend),
        CadicalUnsatProofFindAdapter(sat=sat, backend=backend),
    )


class _CadicalBackend:
    def __init__(
        self,
        *,
        runtime: CapabilityProviderRuntime,
        executable: Path,
    ) -> None:
        self.runtime = runtime
        self.executable = executable

    def run_model(
        self,
        cnf: CanonicalCnf,
        budget: SatExplorationBudget,
    ) -> _CadicalRun:
        return self._run(cnf, budget, produce_proof=False)

    def run_proof(
        self,
        cnf: CanonicalCnf,
        budget: SatExplorationBudget,
    ) -> _CadicalRun:
        return self._run(cnf, budget, produce_proof=True)

    def _run(
        self,
        cnf: CanonicalCnf,
        budget: SatExplorationBudget,
        *,
        produce_proof: bool,
    ) -> _CadicalRun:
        started = time.monotonic()
        changed = self._runtime_changed()
        if changed:
            return _run_failure(
                started,
                code="CADICAL_RUNTIME_CHANGED",
                stage="provider_identity",
                message=(
                    "The CaDiCaL executable no longer matches the runtime digest "
                    "advertised by the capability."
                ),
            )
        with tempfile.TemporaryDirectory(prefix="jacobian-cadical-") as directory:
            root = Path(directory)
            cnf_path = root / "input.cnf"
            proof_path = root / "proof.drat"
            cnf_path.write_bytes(cnf.to_dimacs_bytes())
            command = [str(self.executable), "-q"]
            if produce_proof:
                command.append("--no-binary")
            if budget.conflicts is not None:
                command.extend(("-c", str(budget.conflicts)))
            command.append(str(cnf_path))
            if produce_proof:
                command.append(str(proof_path))
            try:
                completed = run_bounded_process(
                    command,
                    input_bytes=b"",
                    timeout_seconds=float(budget.wall_seconds),
                    environment={
                        **os.environ,
                        "LANG": "C",
                        "LC_ALL": "C",
                        "TZ": "UTC",
                    },
                    stdout_limit=CADICAL_STDOUT_LIMIT,
                    stderr_limit=CADICAL_STDERR_LIMIT,
                )
            except OSError:
                return _run_failure(
                    started,
                    code="CADICAL_EXECUTION_FAILED",
                    stage="solver_execution",
                    message="The pinned CaDiCaL process could not be started.",
                )
            operational = _operational_failure(started, completed)
            if operational is not None:
                return operational
            if self._runtime_changed():
                return _run_failure(
                    started,
                    code="CADICAL_RUNTIME_CHANGED",
                    stage="provider_identity",
                    message=(
                        "The CaDiCaL executable changed while the operation was "
                        "running; no solver evidence was retained."
                    ),
                )
            try:
                solver_status, model_literals = _parse_solver_output(
                    completed.stdout,
                    completed.returncode,
                )
            except ValueError:
                return _run_failure(
                    started,
                    code="INVALID_CADICAL_OUTPUT",
                    stage="solver_output",
                    message=(
                        "CaDiCaL returned output inconsistent with its documented "
                        "competition status protocol."
                    ),
                )
            proof: bytes | None = None
            if produce_proof and solver_status == "UNSATISFIABLE":
                try:
                    proof = _read_proof_file(proof_path)
                except FileNotFoundError:
                    return _run_failure(
                        started,
                        code="CADICAL_PROOF_MISSING",
                        stage="proof_capture",
                        message=(
                            "CaDiCaL reported UNSATISFIABLE without creating the "
                            "requested DRAT proof file."
                        ),
                    )
                except OverflowError:
                    return _run_failure(
                        started,
                        code="CADICAL_PROOF_LIMIT_EXCEEDED",
                        stage="proof_capture",
                        message=(
                            "The raw CaDiCaL proof exceeded the configured durable "
                            "artifact limit and was not read or retained."
                        ),
                    )
                except OSError:
                    return _run_failure(
                        started,
                        code="INVALID_CADICAL_PROOF_FILE",
                        stage="proof_capture",
                        message=(
                            "The CaDiCaL proof output was not a safe bounded regular "
                            "file and was not retained."
                        ),
                    )
            return _CadicalRun(
                execution_status=ExecutionStatus.COMPLETED,
                runtime_ms=_runtime_ms(started),
                solver_status=solver_status,
                model_literals=model_literals,
                proof=proof,
            )

    def _runtime_changed(self) -> bool:
        try:
            current = _sha256_file(self.executable)
        except OSError:
            return True
        return current != self.runtime.digest


class CadicalModelFindAdapter:
    """Attempt to produce one total assignment without validating it."""

    def __init__(
        self,
        *,
        sat: SatArtifactService,
        backend: _CadicalBackend,
    ) -> None:
        self.sat = sat
        self.backend = backend
        self._descriptor = CapabilityDescriptor(
            capability_id="sat.model.find",
            version="1",
            title="Find a SAT assignment",
            description=(
                "Ask pinned CaDiCaL to produce one total assignment for an exact "
                "canonical CNF; the candidate remains unverified."
            ),
            provider="cadical",
            provider_runtime=backend.runtime,
            modes=(CapabilityMode.EXPLORE,),
            input_schema=model_schema(SatExplorationRequest),
            output_schema=model_schema(SatModelFindOutput),
            tags=("sat", "cnf", "assignment", "exploration", "cadical"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        validated, resolved = _resolve_request(self.sat, request)
        run = self.backend.run_model(resolved.cnf, validated.resource_budget)
        if run.execution_status is not ExecutionStatus.COMPLETED:
            return _failed_result(self.descriptor, request, resolved, run)
        assert run.solver_status is not None
        assignment_uri: str | None = None
        if run.solver_status == "SATISFIABLE":
            try:
                values = _total_assignment(
                    run.model_literals,
                    variable_count=len(resolved.cnf.variables),
                )
            except ValueError:
                return _failed_result(
                    self.descriptor,
                    request,
                    resolved,
                    _CadicalRun(
                        execution_status=ExecutionStatus.ERROR,
                        runtime_ms=run.runtime_ms,
                        diagnostic=CapabilityDiagnostic(
                            code="INVALID_CADICAL_MODEL",
                            stage="model_capture",
                            message=(
                                "CaDiCaL reported SATISFIABLE without a unique total "
                                "assignment for every declared variable."
                            ),
                        ),
                    ),
                )
            assignment_uri = self.sat.put_assignment(
                cnf_uri=resolved.artifact.artifact_uri,
                values=values,
                producer=self.backend.runtime,
                resource_budget=validated.resource_budget.artifact_budget(),
            ).artifact_uri
        output = SatModelFindOutput(
            status=(
                "ASSIGNMENT_PRODUCED"
                if assignment_uri is not None
                else "NO_ASSIGNMENT_PRODUCED"
            ),
            solver_status=run.solver_status,
            cnf_uri=resolved.artifact.artifact_uri,
            assignment_uri=assignment_uri,
            detail=(
                "CaDiCaL produced a total assignment candidate; it remains "
                "unverified until sat.model.verify accepts it."
                if assignment_uri is not None
                else (
                    f"CaDiCaL reported {run.solver_status} without producing an "
                    "assignment; no SAT or UNSAT conclusion follows."
                )
            ),
        )
        artifacts = [resolved.artifact.artifact_uri]
        if assignment_uri is not None:
            artifacts.append(assignment_uri)
        return _completed_result(
            self.descriptor,
            request,
            resolved,
            run,
            output.model_dump(mode="json"),
            tuple(artifacts),
            basis=(
                "the pinned solver produced a bound candidate, but only an "
                "independent assignment checker can verify it"
                if assignment_uri is not None
                else "the bounded solver attempt completed without a model; no "
                "opposite mathematical conclusion follows"
            ),
        )


class CadicalUnsatProofFindAdapter:
    """Attempt to preserve raw text DRAT without validating the proof."""

    def __init__(
        self,
        *,
        sat: SatArtifactService,
        backend: _CadicalBackend,
    ) -> None:
        self.sat = sat
        self.backend = backend
        self._descriptor = CapabilityDescriptor(
            capability_id="sat.unsat_proof.find",
            version="1",
            title="Find a SAT UNSAT proof",
            description=(
                "Ask pinned CaDiCaL to emit raw text DRAT for an exact canonical "
                "CNF; preserving the proof does not establish UNSAT."
            ),
            provider="cadical",
            provider_runtime=backend.runtime,
            modes=(CapabilityMode.EXPLORE,),
            input_schema=model_schema(SatExplorationRequest),
            output_schema=model_schema(SatUnsatProofFindOutput),
            tags=("sat", "cnf", "unsat", "proof", "exploration", "cadical"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        validated, resolved = _resolve_request(self.sat, request)
        run = self.backend.run_proof(resolved.cnf, validated.resource_budget)
        if run.execution_status is not ExecutionStatus.COMPLETED:
            return _failed_result(self.descriptor, request, resolved, run)
        assert run.solver_status is not None
        proof_uri: str | None = None
        if run.solver_status == "UNSATISFIABLE":
            assert run.proof is not None
            proof_uri = self.sat.put_proof(
                cnf_uri=resolved.artifact.artifact_uri,
                proof=run.proof,
                producer=self.backend.runtime,
                resource_budget=validated.resource_budget.artifact_budget(),
            ).artifact_uri
        output = SatUnsatProofFindOutput(
            status="PROOF_PRODUCED" if proof_uri is not None else "NO_PROOF_PRODUCED",
            solver_status=run.solver_status,
            cnf_uri=resolved.artifact.artifact_uri,
            proof_uri=proof_uri,
            detail=(
                "CaDiCaL produced raw text DRAT bytes; they remain unverified until "
                "an independent proof checker accepts them."
                if proof_uri is not None
                else (
                    f"CaDiCaL reported {run.solver_status} without producing an "
                    "UNSAT proof; no SAT or UNSAT conclusion follows."
                )
            ),
        )
        artifacts = [resolved.artifact.artifact_uri]
        if proof_uri is not None:
            artifacts.append(proof_uri)
        return _completed_result(
            self.descriptor,
            request,
            resolved,
            run,
            output.model_dump(mode="json"),
            tuple(artifacts),
            basis=(
                "the pinned solver produced bound raw proof bytes, but only an "
                "independent proof checker can establish UNSAT"
                if proof_uri is not None
                else "the bounded solver attempt completed without a proof; no "
                "opposite mathematical conclusion follows"
            ),
        )


def _resolve_request(
    sat: SatArtifactService,
    request: CapabilityRequest,
) -> tuple[SatExplorationRequest, ResolvedSatCnf]:
    try:
        validated = SatExplorationRequest.model_validate(request.input)
        resolved = sat.resolve_cnf(validated.cnf_uri)
    except (SatArtifactError, ValidationError) as exc:
        raise CapabilityInvocationError(
            CapabilityDiagnostic(
                code="INVALID_SAT_EXPLORATION_REQUEST",
                stage="artifact_resolution",
                message=str(exc),
                path="cnf_uri",
                schema_uri=sat.installation.cnf_schema_uri,
                expected="one valid canonical CNF artifact and enforceable budget",
                hint=(
                    "Create the instance with SatArtifactService.put_cnf and use "
                    "only the advertised wall-time and conflict limits."
                ),
            )
        ) from exc
    return validated, resolved


def _completed_result(
    descriptor: CapabilityDescriptor,
    request: CapabilityRequest,
    resolved: ResolvedSatCnf,
    run: _CadicalRun,
    output: dict[str, object],
    artifact_uris: tuple[str, ...],
    *,
    basis: str,
) -> CapabilityResult:
    return CapabilityResult(
        capability_id=descriptor.capability_id,
        capability_version=descriptor.version,
        mode=request.mode,
        execution=Execution(
            status=ExecutionStatus.COMPLETED,
            runtime_ms=run.runtime_ms,
        ),
        output=output,
        scope=_scope(resolved),
        completeness=CapabilityCompleteness(
            status=CapabilityCompletenessStatus.UNKNOWN,
            basis=(
                "this bounded producer makes no exhaustive search or mathematical "
                "completeness claim"
            ),
            assurance_level=CapabilityAssuranceLevel.COMPUTED,
        ),
        assurance=CapabilityAssurance(
            level=CapabilityAssuranceLevel.COMPUTED,
            basis=basis,
        ),
        artifact_uris=artifact_uris,
    )


def _failed_result(
    descriptor: CapabilityDescriptor,
    request: CapabilityRequest,
    resolved: ResolvedSatCnf,
    run: _CadicalRun,
) -> CapabilityResult:
    assert run.diagnostic is not None
    return CapabilityResult(
        capability_id=descriptor.capability_id,
        capability_version=descriptor.version,
        mode=request.mode,
        execution=Execution(
            status=run.execution_status,
            runtime_ms=run.runtime_ms,
            detail=run.diagnostic.message,
        ),
        scope=_scope(resolved),
        completeness=CapabilityCompleteness(
            status=CapabilityCompletenessStatus.UNKNOWN,
            basis=(
                "the producer did not complete with usable evidence; no coverage "
                "or mathematical conclusion follows"
            ),
            assurance_level=CapabilityAssuranceLevel.HEURISTIC,
        ),
        diagnostics=(run.diagnostic,),
        assurance=CapabilityAssurance(
            level=CapabilityAssuranceLevel.HEURISTIC,
            basis=(
                "the producer did not complete with usable bound evidence; no "
                "mathematical conclusion follows"
            ),
        ),
        artifact_uris=(resolved.artifact.artifact_uri,),
    )


def _scope(resolved: ResolvedSatCnf) -> CapabilityScope:
    return CapabilityScope(
        description="the full exact canonical CNF supplied to the producer",
        parameters={
            "declared_scope": "FULL_CNF",
            "variable_count": len(resolved.cnf.variables),
            "clause_count": len(resolved.cnf.clauses),
            "projection_format": resolved.cnf.projection_format,
            "projection_version": resolved.cnf.projection_version,
        },
        artifact_uri=resolved.artifact.artifact_uri,
    )


def _operational_failure(
    started: float,
    completed: BoundedProcessResult,
) -> _CadicalRun | None:
    if completed.stdout_exceeded or completed.stderr_exceeded:
        return _run_failure(
            started,
            code="CADICAL_OUTPUT_LIMIT_EXCEEDED",
            stage="solver_output",
            message=(
                "CaDiCaL exceeded a bounded output stream limit; no solver "
                "evidence was retained."
            ),
        )
    if completed.timed_out:
        return _run_failure(
            started,
            status=ExecutionStatus.TIMEOUT,
            code="CADICAL_TIMEOUT",
            stage="solver_execution",
            message=(
                "CaDiCaL exceeded the declared wall-time budget; no mathematical "
                "conclusion follows."
            ),
        )
    if completed.returncode not in {0, 10, 20}:
        return _run_failure(
            started,
            code="CADICAL_EXECUTION_FAILED",
            stage="solver_execution",
            message=(
                "CaDiCaL exited outside the documented UNKNOWN, SAT, and UNSAT "
                "competition status codes."
            ),
        )
    return None


def _run_failure(
    started: float,
    *,
    code: str,
    stage: str,
    message: str,
    status: ExecutionStatus = ExecutionStatus.ERROR,
) -> _CadicalRun:
    return _CadicalRun(
        execution_status=status,
        runtime_ms=_runtime_ms(started),
        diagnostic=CapabilityDiagnostic(
            code=code,
            stage=stage,
            message=message,
        ),
    )


def _parse_solver_output(
    stdout: bytes,
    returncode: int | None,
) -> tuple[_SolverStatus, tuple[int, ...]]:
    try:
        text = stdout.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("solver output is not ASCII") from exc
    declared: list[_SolverStatus] = []
    model_tokens: list[int] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line == "c" or line.startswith("c "):
            continue
        if line in {"s SATISFIABLE", "s UNSATISFIABLE", "s UNKNOWN"}:
            declared.append(line.removeprefix("s "))  # type: ignore[arg-type]
            continue
        if line.startswith("v "):
            try:
                model_tokens.extend(int(token) for token in line[2:].split())
            except ValueError as exc:
                raise ValueError("model contains a noninteger token") from exc
            continue
        raise ValueError("unexpected solver output line")
    expected_by_returncode: dict[int, _SolverStatus] = {
        0: "UNKNOWN",
        10: "SATISFIABLE",
        20: "UNSATISFIABLE",
    }
    if returncode not in expected_by_returncode:
        raise ValueError("unexpected solver exit status")
    expected = expected_by_returncode[returncode]
    if len(declared) > 1 or (declared and declared[0] != expected):
        raise ValueError("solver text status and exit status disagree")
    if not declared and expected != "UNKNOWN":
        raise ValueError("decisive solver exit omitted its text status")
    if expected != "SATISFIABLE" and model_tokens:
        raise ValueError("non-SAT solver output carried model literals")
    return expected, tuple(model_tokens)


def _total_assignment(
    model_literals: tuple[int, ...],
    *,
    variable_count: int,
) -> tuple[bool, ...]:
    if not model_literals or model_literals[-1] != 0:
        raise ValueError("model is not terminated")
    if 0 in model_literals[:-1]:
        raise ValueError("model terminates before its final token")
    values: dict[int, bool] = {}
    for literal in model_literals[:-1]:
        variable = abs(literal)
        if variable < 1 or variable > variable_count or variable in values:
            raise ValueError("model variable is duplicate or out of range")
        values[variable] = literal > 0
    if set(values) != set(range(1, variable_count + 1)):
        raise ValueError("model is not total")
    return tuple(values[index] for index in range(1, variable_count + 1))


def _read_proof_file(path: Path) -> bytes:
    path_metadata = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(path_metadata.st_mode):
        raise OSError("proof output is not a regular file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError("proof output is not a regular file")
        if metadata.st_size > CADICAL_PROOF_LIMIT:
            raise OverflowError("proof output exceeds its durable artifact limit")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            proof = stream.read(CADICAL_PROOF_LIMIT + 1)
        if len(proof) > CADICAL_PROOF_LIMIT:
            raise OverflowError("proof output grew beyond its durable artifact limit")
        return proof
    finally:
        os.close(descriptor)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def _runtime_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))
