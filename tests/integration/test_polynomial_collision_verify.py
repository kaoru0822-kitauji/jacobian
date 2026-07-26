from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.kernel import JacobianKernel


def _rational(value: int) -> dict[str, str]:
    return {"num": str(value), "den": "1"}


def _request(image: int) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id="polynomial.map.collision.verify",
        mode=CapabilityMode.VERIFY,
        input={
            "map": {
                "variables": ["x"],
                "coordinates": [
                    {
                        "terms": [
                            {
                                "coefficient": _rational(1),
                                "exponents": [2],
                            }
                        ]
                    }
                ],
            },
            "first_point": [_rational(-1)],
            "second_point": [_rational(1)],
            "claimed_image": [_rational(image)],
        },
    )


@pytest.mark.integration
def test_direct_collision_verifier_promotes_only_independent_replay(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(_request(1))

    assert result.output["collision_verified"] is True
    assert result.output["conclusion"] == "FALSE"
    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert result.output["verification_record_uri"] in result.artifact_uris


@pytest.mark.integration
def test_direct_collision_verifier_fails_closed_for_wrong_image(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(_request(2))

    assert result.output["collision_verified"] is False
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.assurance.level is CapabilityAssuranceLevel.HEURISTIC
    assert result.output["verification_record_uri"] is None


def test_direct_collision_verifier_requires_authorized_reference_checker(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)

    assert "polynomial.map.collision.verify" not in {
        item.capability_id for item in kernel.capabilities.catalog().capabilities
    }
