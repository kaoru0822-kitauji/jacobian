from __future__ import annotations

import subprocess
from fractions import Fraction
from itertools import permutations
from pathlib import Path
from random import Random
from typing import Any

import pytest
import sympy

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityProviderAvailability,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel
from jacobian.matrix_determinant_capabilities import (
    install_matrix_determinant_checker,
)


def _rational(value: int | Fraction) -> dict[str, str]:
    exact = Fraction(value)
    return {"num": str(exact.numerator), "den": str(exact.denominator)}


def _matrix(rows: list[list[int | Fraction]]) -> dict[str, Any]:
    return {
        "matrix_schema_version": "1",
        "domain": "QQ",
        "entries": [[_rational(value) for value in row] for row in rows],
    }


def _reference_determinant(rows: list[list[Fraction]]) -> Fraction:
    total = Fraction(0)
    for permutation in permutations(range(len(rows))):
        inversions = sum(
            permutation[left] > permutation[right]
            for left in range(len(rows))
            for right in range(left + 1, len(rows))
        )
        term = Fraction(-1 if inversions % 2 else 1)
        for row, column in enumerate(permutation):
            term *= rows[row][column]
        total += term
    return total


def _kernel_with_determinant_checker(root: Path) -> JacobianKernel:
    kernel = JacobianKernel(root)
    adapter, _installation = install_matrix_determinant_checker(
        kernel.store,
        kernel.schemas,
        kernel.artifacts,
        kernel.matrix,
        kernel.verification,
        kernel.checkers,
        authorize_checker=True,
    )
    assert adapter is not None
    kernel.register_capability(adapter)
    return kernel


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        pytest.param([[Fraction(-3, 7)]], Fraction(-3, 7), id="one-by-one"),
        pytest.param([[0, 2], [3, 4]], Fraction(-6), id="row-swap-sign"),
        pytest.param([[1, 2], [2, 4]], Fraction(0), id="singular"),
        pytest.param(
            [[Fraction(1, 2), 1], [3, Fraction(5, 2)]],
            Fraction(-7, 4),
            id="rational",
        ),
    ],
)
def test_matrix_determinant_compute_is_exact_and_unverified(
    tmp_path: Path,
    rows: list[list[int | Fraction]],
    expected: Fraction,
) -> None:
    kernel = JacobianKernel(tmp_path)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.determinant.compute",
            input={"matrix": _matrix(rows)},
        )
    )

    assert result.output["determinant"] == _rational(expected)
    assert result.output["method"] == "FRACTION_FREE_BAREISS"
    assert result.output["backend"] == "sympy"
    assert result.output["backend_version"] == sympy.__version__
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert len(result.artifact_uris) == 2
    determinant_artifact = kernel.store.get(result.output["determinant_uri"])
    assert determinant_artifact.payload["backend"] == "sympy"
    assert determinant_artifact.payload["backend_version"] == sympy.__version__


def test_matrix_determinant_verify_independently_recomputes_exact_value(
    tmp_path: Path,
) -> None:
    kernel = _kernel_with_determinant_checker(tmp_path)
    computed = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.determinant.compute",
            input={
                "matrix": _matrix(
                    [
                        [1, 0, 1],
                        [2, -1, 3],
                        [4, 3, 2],
                    ]
                )
            },
        )
    )

    verified = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.determinant.verify",
            mode=CapabilityMode.VERIFY,
            input={"determinant_uri": computed.output["determinant_uri"]},
        )
    )

    assert verified.execution.status is ExecutionStatus.COMPLETED
    assert verified.output["status"] == "VERIFIED_DETERMINANT"
    assert verified.output["conclusion"] == "TRUE"
    assert verified.output["verification_record_uri"].startswith("artifact://sha256/")
    assert verified.assurance.level is CapabilityAssuranceLevel.VERIFIED


def test_matrix_determinant_verify_rejects_wrong_bound_value(tmp_path: Path) -> None:
    kernel = _kernel_with_determinant_checker(tmp_path)
    computed = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.determinant.compute",
            input={"matrix": _matrix([[1, 2], [3, 4]])},
        )
    )
    source_uri = computed.output["matrix_uri"]
    wrong = kernel.artifacts.put(
        schema_uri=kernel.matrix.determinant_schema_uri,
        semantics_uri=kernel.matrix.semantics_uri,
        payload={
            **kernel.store.get(computed.output["determinant_uri"]).payload,
            "determinant": _rational(2),
        },
        parents=(source_uri,),
        summary="deliberately incorrect determinant candidate",
    )

    rejected = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.determinant.verify",
            mode=CapabilityMode.VERIFY,
            input={"determinant_uri": wrong.artifact_uri},
        )
    )

    assert rejected.execution.status is ExecutionStatus.COMPLETED
    assert rejected.output["status"] == "REJECTED"
    assert rejected.output["conclusion"] == "UNKNOWN"
    assert rejected.output["verification_record_uri"] is None
    assert rejected.assurance.level is not CapabilityAssuranceLevel.VERIFIED


def test_matrix_determinant_verify_timeout_is_not_a_conclusion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = _kernel_with_determinant_checker(tmp_path)
    computed = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.determinant.compute",
            input={"matrix": _matrix([[1]])},
        )
    )
    monkeypatch.setattr(
        kernel.verification,
        "_run_checker",
        lambda **_kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired("determinant-checker", 1)
        ),
    )

    timed_out = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.determinant.verify",
            mode=CapabilityMode.VERIFY,
            input={"determinant_uri": computed.output["determinant_uri"]},
        )
    )

    assert timed_out.execution.status is ExecutionStatus.TIMEOUT
    assert timed_out.output["status"] == "TIMEOUT"
    assert timed_out.output["conclusion"] == "UNKNOWN"
    assert timed_out.output["verification_record_uri"] is None
    assert timed_out.assurance.level is not CapabilityAssuranceLevel.VERIFIED


def test_matrix_rank_compute_returns_rectangular_pivot_evidence(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.rank.compute",
            input={
                "matrix": _matrix(
                    [
                        [1, 2, 3, 4],
                        [2, 4, 6, 8],
                        [0, 1, 1, 0],
                    ]
                )
            },
        )
    )

    assert result.output["rank"] == 2
    assert result.output["pivot_columns"] == [0, 1]
    assert result.output["backend"] == "sympy"
    assert result.output["backend_version"] == sympy.__version__
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert len(result.artifact_uris) == 2
    rank_artifact = kernel.store.get(result.output["rank_uri"])
    assert rank_artifact.payload["backend"] == "sympy"
    assert rank_artifact.payload["backend_version"] == sympy.__version__


def test_matrix_determinant_rejects_rectangular_input(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.determinant.compute",
            input={"matrix": _matrix([[1, 2, 3], [4, 5, 6]])},
        )
    )

    assert result.execution.status.value == "ERROR"
    assert result.diagnostics[0].code == "INVALID_EXACT_MATRIX_REQUEST"


@pytest.mark.differential
def test_matrix_determinant_matches_independent_bounded_oracle(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    random = Random(20260726)

    for size in range(1, 5):
        for _ in range(6):
            rows = [
                [
                    Fraction(random.randint(-5, 5), random.randint(1, 5))
                    for _ in range(size)
                ]
                for _ in range(size)
            ]
            result = kernel.capabilities.invoke(
                CapabilityRequest(
                    capability_id="matrix.determinant.compute",
                    input={"matrix": _matrix(rows)},
                )
            )

            assert result.output["determinant"] == _rational(
                _reference_determinant(rows)
            )


def test_matrix_capabilities_report_sympy_provider_identity(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    descriptors = {
        descriptor.capability_id: descriptor
        for descriptor in kernel.capabilities.catalog().capabilities
    }

    for capability_id in ("matrix.determinant.compute", "matrix.rank.compute"):
        descriptor = descriptors[capability_id]
        assert descriptor.provider == "jacobian.sympy"
        assert descriptor.provider_runtime.provider == "jacobian.sympy"
        assert (
            descriptor.provider_runtime.availability
            is CapabilityProviderAvailability.AVAILABLE
        )
        assert descriptor.provider_runtime.version == sympy.__version__
