from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityResult,
)
from jacobian.contracts.results import Execution, ExecutionStatus

RECORD_URI = "artifact://sha256/" + "a" * 64


@pytest.mark.contract
def test_explore_lane_cannot_claim_verified_assurance() -> None:
    with pytest.raises(ValidationError, match="exploration lane"):
        CapabilityResult(
            capability_id="example.solve",
            capability_version="1",
            mode=CapabilityMode.EXPLORE,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.VERIFIED,
                basis="untrusted adapter claim",
                verification_record_uri=RECORD_URI,
            ),
        )


@pytest.mark.contract
def test_nonverified_assurance_cannot_smuggle_a_record_uri() -> None:
    with pytest.raises(ValidationError, match="only verified"):
        CapabilityAssurance(
            level=CapabilityAssuranceLevel.COMPUTED,
            basis="ordinary deterministic computation",
            verification_record_uri=RECORD_URI,
        )
