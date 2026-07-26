from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityRequest,
)
from jacobian.kernel import JacobianKernel


def _term(coefficient: int, exponent: int) -> dict[str, object]:
    return {
        "coefficient": {"num": str(coefficient), "den": "1"},
        "exponents": [exponent],
    }


@pytest.mark.integration
def test_factor_compute_preserves_multiplicity_and_reconstructs_exactly(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    polynomial = {
        "terms": [
            _term(1, 2),
            _term(-2, 1),
            _term(1, 0),
        ]
    }

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.factor.compute",
            input={"variable": "x", "polynomial": polynomial},
        )
    )

    assert result.output["unit"] == {"num": "1", "den": "1"}
    assert len(result.output["factors"]) == 1
    assert result.output["factors"][0]["multiplicity"] == 2
    assert result.output["reconstructed"] == polynomial
    assert result.output["product_reconstruction"] == "EXACT"
    assert result.output["irreducibility_verification"] == "UNVERIFIED"
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED


@pytest.mark.integration
def test_factor_compute_handles_zero_without_irreducibility_claim(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.factor.compute",
            input={"variable": "x", "polynomial": {"terms": []}},
        )
    )

    assert result.output["unit"] == {"num": "0", "den": "1"}
    assert result.output["factors"] == []
    assert result.output["reconstructed"] == {"terms": []}
    assert result.output["irreducibility_verification"] == "UNVERIFIED"
