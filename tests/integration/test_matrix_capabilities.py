from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityRequest,
)
from jacobian.kernel import JacobianKernel


def _rational(value: int | Fraction) -> dict[str, str]:
    exact = Fraction(value)
    return {"num": str(exact.numerator), "den": str(exact.denominator)}


def _matrix(rows: list[list[int | Fraction]]) -> dict[str, Any]:
    return {
        "matrix_schema_version": "1",
        "domain": "QQ",
        "entries": [[_rational(value) for value in row] for row in rows],
    }


@pytest.mark.integration
def test_matrix_determinant_compute_is_exact_and_unverified(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.determinant.compute",
            input={
                "matrix": _matrix(
                    [
                        [Fraction(1, 2), 1],
                        [3, Fraction(5, 2)],
                    ]
                )
            },
        )
    )

    assert result.output["determinant"] == {"num": "-7", "den": "4"}
    assert result.output["method"] == "FRACTION_FREE_BAREISS"
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert len(result.artifact_uris) == 2


@pytest.mark.integration
def test_matrix_rank_compute_returns_pivot_evidence(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.rank.compute",
            input={
                "matrix": _matrix(
                    [
                        [1, 2, 3],
                        [2, 4, 6],
                        [0, 1, 1],
                    ]
                )
            },
        )
    )

    assert result.output["rank"] == 2
    assert result.output["pivot_columns"] == [0, 1]
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert len(result.artifact_uris) == 2


@pytest.mark.integration
def test_matrix_determinant_rejects_rectangular_input(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.determinant.compute",
            input={"matrix": _matrix([[1, 2, 3], [4, 5, 6]])},
        )
    )

    assert result.execution.status.value == "ERROR"
    assert result.diagnostics[0].code == "INVALID_EXACT_MATRIX_REQUEST"
