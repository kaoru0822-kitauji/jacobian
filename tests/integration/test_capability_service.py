from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from jacobian.capabilities import CapabilityError
from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityDescriptor,
    CapabilityMode,
    CapabilityRequest,
    CapabilityResult,
)
from jacobian.contracts.checkers import CheckerDecision
from jacobian.contracts.results import (
    Arithmetic,
    Conclusion,
    Coverage,
    Execution,
    ExecutionStatus,
    Method,
)
from jacobian.kernel import JacobianKernel


@dataclass(frozen=True)
class ComputedAdapter:
    descriptor = CapabilityDescriptor(
        capability_id="example.double",
        version="1",
        title="Double an integer",
        description="Small adapter used to prove no MCP or kernel edit is required.",
        provider="tests",
        modes=(CapabilityMode.EXPLORE,),
        input_schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        tags=("test",),
    )

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            output={"value": int(request.input["value"]) * 2},
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis="deterministic integer arithmetic",
            ),
        )


@dataclass(frozen=True)
class ForgedVerifiedAdapter:
    descriptor = CapabilityDescriptor(
        capability_id="example.forged",
        version="1",
        title="Forge a result",
        description="Adversarial adapter used to test the assurance boundary.",
        provider="tests",
        modes=(CapabilityMode.VERIFY,),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.VERIFIED,
                basis="adapter says so",
                verification_record_uri="artifact://sha256/" + "f" * 64,
            ),
        )


@dataclass(frozen=True)
class MisboundVerifiedAdapter:
    verification_record_uri: str
    evidence_uri: str
    descriptor = CapabilityDescriptor(
        capability_id="example.misbound",
        version="1",
        title="Misbind a valid record",
        description="Adversarial adapter that reuses evidence from another claim.",
        provider="tests",
        modes=(CapabilityMode.VERIFY,),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            output={
                "conclusion": "FALSE",
                "verification_record_uri": self.verification_record_uri,
            },
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.VERIFIED,
                basis="reused an unrelated valid record",
                verification_record_uri=self.verification_record_uri,
            ),
            artifact_uris=(self.evidence_uri,),
        )


@pytest.mark.integration
def test_external_adapter_invocation_is_recorded_and_retrievable(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    kernel.register_capability(ComputedAdapter())

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="example.double",
            input={"value": 21},
        )
    )

    assert result.output == {"value": 42}
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.episode_uri is not None
    hits = kernel.memory.search(query="double computed").hits
    assert [hit.episode_uri for hit in hits] == [result.episode_uri]


@pytest.mark.integration
def test_external_adapter_loads_from_an_operator_entrypoint(tmp_path: Path) -> None:
    kernel = JacobianKernel(
        tmp_path,
        capability_adapter_entrypoints=(
            "tests.fixtures.capability_functions:create_adapter",
        ),
    )

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="fixture.increment",
            input={"value": 4},
        )
    )

    assert result.output == {"value": 5}


@pytest.mark.integration
def test_adapter_cannot_promote_without_a_local_verification_record(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    kernel.register_capability(ForgedVerifiedAdapter())

    with pytest.raises(CapabilityError, match="verification record"):
        kernel.capabilities.invoke(
            CapabilityRequest(
                capability_id="example.forged",
                mode=CapabilityMode.VERIFY,
                input={},
            )
        )


@pytest.mark.integration
def test_adapter_cannot_reuse_a_record_without_its_bound_artifacts(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    legitimate = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="reference.solve",
            mode=CapabilityMode.VERIFY,
            input={
                "reference_name": "erdos_straus",
                "predicate": {
                    "name": "erdos_straus_range",
                    "parameters": {"lower_bound": 2, "upper_bound": 5},
                },
                "candidate": {"lower_bound": 2, "upper_bound": 5},
                "witness_role": "SUPPORTS_CLAIM",
            },
        )
    )
    record_uri = legitimate.assurance.verification_record_uri
    assert record_uri is not None
    record = kernel.store.get(record_uri)
    evidence_uri = str(record.payload["evidence_uri"])
    kernel.register_capability(
        MisboundVerifiedAdapter(
            verification_record_uri=record_uri,
            evidence_uri=evidence_uri,
        )
    )

    with pytest.raises(CapabilityError, match="bound artifacts"):
        kernel.capabilities.invoke(
            CapabilityRequest(
                capability_id="example.misbound",
                mode=CapabilityMode.VERIFY,
                input={},
            )
        )


@pytest.mark.integration
def test_reference_capability_has_distinct_explore_and_verify_lanes(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    payload = {
        "reference_name": "erdos_straus",
        "predicate": {
            "name": "erdos_straus_range",
            "parameters": {"lower_bound": 2, "upper_bound": 20},
        },
        "candidate": {"lower_bound": 2, "upper_bound": 20},
        "witness_role": "SUPPORTS_CLAIM",
        "evaluation_wall_seconds": 30,
        "witness_wall_seconds": 30,
    }

    explored = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="reference.solve",
            mode=CapabilityMode.EXPLORE,
            input=payload,
        )
    )
    verified = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="reference.solve",
            mode=CapabilityMode.VERIFY,
            input=payload,
        )
    )

    assert explored.assurance.level is CapabilityAssuranceLevel.HEURISTIC
    assert explored.output["verification_record_uri"] is None
    assert verified.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert verified.assurance.verification_record_uri is not None
    assert verified.assurance.verification_record_uri in verified.artifact_uris
    assert verified.output["artifacts"]["verification_record"] == (
        verified.assurance.verification_record_uri
    )
    assert verified.output["verification"]["checker_id"].startswith("checker://sha256/")
    assert verified.output["verification"]["arithmetic"] == "EXACT_INTEGER"
    assert verified.output["verification"]["input"] == {
        "status": "ACCEPTED",
        "errors": [],
        "warnings": [],
    }
    assert (
        "checked exact three-unit-fraction decompositions"
        in (verified.output["verification"]["checker_detail"])
    )
    assert verified.output["stages"]["independent_verification"] == "COMPLETED"
    assert "bounds" not in verified.scope
    assert {hit.assurance_level for hit in kernel.memory.search(limit=10).hits} >= {
        CapabilityAssuranceLevel.HEURISTIC,
        CapabilityAssuranceLevel.VERIFIED,
    }


@pytest.mark.integration
def test_invalid_reference_candidate_is_actionable_and_not_remembered(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="reference.solve",
            mode=CapabilityMode.VERIFY,
            input={
                "reference_name": "erdos_straus",
                "predicate": {
                    "name": "erdos_straus_range",
                    "parameters": {"lower_bound": 2, "upper_bound": 20},
                },
                "candidate": {"minimum": 2, "maximum": 20},
                "witness_role": "SUPPORTS_CLAIM",
            },
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.assurance.level is CapabilityAssuranceLevel.HEURISTIC
    assert result.assurance.verification_record_uri is None
    assert result.episode_uri is None
    assert result.diagnostics[0].code == "INVALID_CANDIDATE"
    assert result.diagnostics[0].stage == "candidate_validation"
    assert result.diagnostics[0].path == "$"
    assert result.diagnostics[0].schema_uri is not None
    assert "capability.describe" in result.diagnostics[0].hint
    assert result.output["error"]["code"] == "INVALID_CANDIDATE"
    assert kernel.memory.search(limit=10).hits == ()


@pytest.mark.integration
def test_unknown_reference_error_is_classified_and_not_remembered(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="reference.solve",
            input={
                "reference_name": "not-installed",
                "predicate": {"name": "anything", "parameters": {}},
                "candidate": {},
                "witness_role": "SUPPORTS_CLAIM",
            },
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.diagnostics[0].code == "UNKNOWN_REFERENCE"
    assert result.diagnostics[0].stage == "reference_resolution"
    assert result.episode_uri is None
    assert kernel.memory.search(limit=10).hits == ()


@pytest.mark.integration
@pytest.mark.skipif(
    shutil.which("lean") is None,
    reason="Lean is not installed",
)
def test_lean_capability_returns_bound_verified_result(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="lean.check",
            mode=CapabilityMode.VERIFY,
            input={
                "statement": "1 + 1 = 2",
                "proof": "rfl",
                "environment": "CORE",
            },
        )
    )

    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert result.assurance.verification_record_uri is not None
    assert result.output["conclusion"] == "TRUE"


@pytest.mark.integration
def test_reference_capability_projects_checker_rejection_detail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    monkeypatch.setattr(
        kernel.verification,
        "_run_checker",
        lambda **_: CheckerDecision(
            accepted=False,
            conclusion=Conclusion.UNKNOWN,
            arithmetic=Arithmetic.EXACT_INTEGER,
            method=Method.EXHAUSTIVE_FINITE,
            coverage=Coverage.EXHAUSTIVE,
            detail="candidate is not globally maximal",
        ),
    )

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="reference.solve",
            mode=CapabilityMode.VERIFY,
            input={
                "reference_name": "matrices",
                "predicate": {
                    "name": "maximize_absolute_determinant",
                    "parameters": {"scope": {"rows": 2, "cols": 2, "entries": [-1, 1]}},
                },
                "candidate": {
                    "rows": 2,
                    "cols": 2,
                    "entries": [[1, 1], [1, -1]],
                },
                "witness_role": "SUPPORTS_CLAIM",
            },
        )
    )

    assert result.assurance.level is CapabilityAssuranceLevel.HEURISTIC
    assert result.output["verification"]["input"]["status"] == "REJECTED"
    assert result.output["verification"]["input"]["errors"] == [
        "candidate is not globally maximal"
    ]
    assert (
        result.output["verification"]["checker_detail"]
        == "candidate is not globally maximal"
    )


@pytest.mark.integration
def test_reference_checker_timeout_is_projected_and_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    def time_out(**_: object) -> CheckerDecision:
        raise subprocess.TimeoutExpired(cmd=["checker"], timeout=1)

    monkeypatch.setattr(kernel.verification, "_run_checker", time_out)
    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="reference.solve",
            mode=CapabilityMode.VERIFY,
            input={
                "reference_name": "matrices",
                "predicate": {
                    "name": "maximize_absolute_determinant",
                    "parameters": {"scope": {"rows": 2, "cols": 2, "entries": [-1, 1]}},
                },
                "candidate": {
                    "rows": 2,
                    "cols": 2,
                    "entries": [[1, 1], [1, -1]],
                },
                "witness_role": "SUPPORTS_CLAIM",
            },
        )
    )

    assert result.execution.status is ExecutionStatus.TIMEOUT
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["verification"]["execution"]["detail"] == "checker timed out"
    assert result.assurance.verification_record_uri is None


@pytest.mark.integration
def test_lean_capability_projects_repairable_checker_diagnostics(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="lean.check",
            mode=CapabilityMode.VERIFY,
            input={
                "statement": "1 + 1 = 2",
                "proof": "sorry",
                "environment": "CORE",
            },
        )
    )

    assert result.output["input"]["status"] == "REJECTED"
    assert "forbidden Lean command" in result.output["input"]["errors"][0]
    assert result.output["diagnostics"] == result.output["input"]["errors"]
    assert result.assurance.verification_record_uri is None
