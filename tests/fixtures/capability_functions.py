from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityDescriptor,
    CapabilityMode,
    CapabilityRequest,
    CapabilityResult,
)
from jacobian.contracts.results import Execution, ExecutionStatus


@dataclass(frozen=True)
class FixtureAdapter:
    descriptor = CapabilityDescriptor(
        capability_id="fixture.increment",
        version="1",
        title="Increment an integer",
        description="External fixture adapter loaded through an operator entrypoint.",
        provider="tests.fixture",
        modes=(CapabilityMode.EXPLORE,),
        input_schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
    )

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            output={"value": int(request.input["value"]) + 1},
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis="fixture integer arithmetic",
            ),
        )


def create_adapter(_kernel: Any) -> FixtureAdapter:
    return FixtureAdapter()
