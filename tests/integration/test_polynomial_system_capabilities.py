from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.kernel import JacobianKernel


def _term(coefficient: int, exponent: int) -> dict[str, Any]:
    return {
        "coefficient": {"num": str(coefficient), "den": "1"},
        "exponents": [exponent],
    }


def _input(value: int) -> dict[str, Any]:
    return {
        "system": {
            "system_schema_version": "1",
            "domain": "QQ",
            "variables": ["x"],
            "equations": [{"terms": [_term(1, 2), _term(-4, 0)]}],
            "inequations": [{"terms": [_term(1, 1)]}],
        },
        "assignment": [{"num": str(value), "den": "1"}],
    }


@pytest.mark.integration
def test_solution_capability_verifies_valid_assignment(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.system.solution.verify",
            mode=CapabilityMode.VERIFY,
            input=_input(2),
        )
    )

    assert result.output["satisfies"] is True
    assert result.output["equation_residuals"] == [{"num": "0", "den": "1"}]
    assert result.output["inequation_values"] == [{"num": "2", "den": "1"}]
    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED


@pytest.mark.integration
def test_solution_capability_verifies_invalid_assignment(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.system.solution.verify",
            mode=CapabilityMode.VERIFY,
            input=_input(1),
        )
    )

    assert result.output["satisfies"] is False
    assert result.output["conclusion"] == "FALSE"
    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED


@pytest.mark.integration
def test_solution_capability_is_only_available_with_checker(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)

    ids = {
        descriptor.capability_id
        for descriptor in kernel.capabilities.catalog().capabilities
    }

    assert "polynomial.system.solution.verify" not in ids
