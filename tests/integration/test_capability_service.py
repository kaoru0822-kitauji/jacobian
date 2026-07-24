from __future__ import annotations

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
from jacobian.contracts.results import Execution, ExecutionStatus
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
    assert {hit.assurance_level for hit in kernel.memory.search(limit=10).hits} >= {
        CapabilityAssuranceLevel.HEURISTIC,
        CapabilityAssuranceLevel.VERIFIED,
    }


@pytest.mark.integration
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
