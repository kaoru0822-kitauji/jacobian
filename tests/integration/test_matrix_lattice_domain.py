from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

from jacobian.bounded_process import BoundedProcessResult
from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel


def _q(value: int, denominator: int = 1) -> dict[str, str]:
    return {"num": str(value), "den": str(denominator)}


def _qq(rows: list[list[int]]) -> dict[str, object]:
    return {
        "domain": "QQ",
        "entries": [[_q(value) for value in row] for row in rows],
    }


def test_exact_matrix_domain_results_and_lineage(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    cases = (
        (
            "matrix.inverse.compute",
            {
                "matrix": {
                    "domain": "ZZ",
                    "entries": [["1", "2"], ["3", "4"]],
                }
            },
            {
                "inverse": {
                    "domain": "QQ",
                    "entries": [
                        [_q(-2), _q(1)],
                        [_q(3, 2), _q(-1, 2)],
                    ],
                },
                "convention": "TWO_SIDED_INVERSE_OVER_QQ",
            },
        ),
        (
            "matrix.trace.compute",
            {
                "matrix": {
                    "domain": "ZZ",
                    "entries": [["1", "2"], ["3", "4"]],
                }
            },
            {
                "trace": "5",
                "convention": "SUM_OF_DIAGONAL_ENTRIES",
            },
        ),
        (
            "matrix.normal_form.rref.compute",
            {"matrix": _qq([[1, 2, 3], [2, 4, 7]])},
            {
                "reduced_matrix": {
                    "domain": "QQ",
                    "entries": [
                        [_q(1), _q(2), _q(0)],
                        [_q(0), _q(0), _q(1)],
                    ],
                },
                "rank": 2,
                "pivot_columns": [0, 2],
                "free_columns": [1],
                "convention": "UNIQUE_RREF_OVER_QQ",
            },
        ),
        (
            "matrix.nullspace.compute",
            {"matrix": _qq([[1, 2, 3], [2, 4, 6]])},
            {
                "ambient_dimension": 3,
                "nullity": 2,
                "basis_vectors": [
                    [_q(-2), _q(1), _q(0)],
                    [_q(-3), _q(0), _q(1)],
                ],
                "free_columns": [1, 2],
                "convention": "RREF_FUNDAMENTAL_BASIS",
            },
        ),
        (
            "matrix.characteristic_polynomial.compute",
            {"matrix": _qq([[1, 2], [3, 4]])},
            {
                "variable": "lambda",
                "degree": 2,
                "coefficients_descending": [_q(1), _q(-5), _q(-2)],
                "monic": True,
                "convention": "DET_LAMBDA_I_MINUS_A",
            },
        ),
        (
            "matrix.normal_form.smith.compute",
            {
                "matrix": {
                    "domain": "ZZ",
                    "entries": [["2", "4", "4"], ["6", "6", "12"]],
                }
            },
            {
                "normal_form": {
                    "domain": "ZZ",
                    "entries": [["2", "0", "0"], ["0", "6", "0"]],
                },
                "rank": 2,
                "invariant_factors": ["2", "6"],
                "transformation_available": False,
                "convention": "POSITIVE_DIVISIBILITY_DIAGONAL",
            },
        ),
    )

    for capability_id, payload, expected in cases:
        result = kernel.capabilities.invoke(
            CapabilityRequest(capability_id=capability_id, input=payload)
        )
        assert result.execution.status is ExecutionStatus.COMPLETED
        assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
        assert result.output["result"] == expected
        assert len(result.artifact_uris) == 2
        source = kernel.store.get(result.artifact_uris[0])
        produced = kernel.store.get(result.artifact_uris[1])
        assert produced.manifest.parents == (source.artifact_uri,)
        assert result.relationships[0].source_artifact_uris == (source.artifact_uri,)
        assert result.relationships[0].target_artifact_uris == (produced.artifact_uri,)


def test_invalid_matrix_request_fails_before_operation_artifacts(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.characteristic_polynomial.compute",
            input={"matrix": _qq([[1, 2, 3], [4, 5, 6]])},
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.diagnostics[0].code == "INVALID_EXACT_MATRIX_REQUEST"
    assert result.artifact_uris == ()


def test_singular_matrix_inverse_is_not_applicable(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.inverse.compute",
            input={
                "matrix": {
                    "domain": "ZZ",
                    "entries": [["1", "2"], ["2", "4"]],
                }
            },
        )
    )

    assert result.execution.status is ExecutionStatus.NOT_APPLICABLE
    assert result.diagnostics[0].code == "MATRIX_OPERATION_NOT_APPLICABLE"
    assert result.artifact_uris == ()


def test_lattice_lll_returns_exact_left_transformation(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    source = [[4, 1], [1, 3]]
    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="lattice.basis.reduce",
            input={
                "basis": {
                    "domain": "ZZ",
                    "entries": [[str(value) for value in row] for row in source],
                },
                "resource_budget": {"wall_seconds": 10},
            },
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    reduced = [
        [int(value) for value in row]
        for row in result.output["result"]["reduced_basis"]["entries"]
    ]
    transformation = [
        [int(value) for value in row]
        for row in result.output["result"]["transformation"]["entries"]
    ]
    assert reduced == [
        [
            sum(
                transformation[row][inner] * source[inner][column] for inner in range(2)
            )
            for column in range(2)
        ]
        for row in range(2)
    ]
    assert result.output["result"]["delta"] == "0.99"
    assert result.output["result"]["eta"] == "0.51"
    assert len(result.artifact_uris) == 2


def test_lattice_lll_timeout_retains_no_operation_artifacts(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from jacobian.domains.matrix_lattice import lattice

    monkeypatch.setattr(
        lattice,
        "run_bounded_process",
        lambda *args, **kwargs: BoundedProcessResult(
            returncode=None,
            stdout=b"",
            stderr=b"",
            stdout_exceeded=False,
            stderr_exceeded=False,
            timed_out=True,
        ),
    )
    kernel = JacobianKernel(tmp_path)
    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="lattice.basis.reduce",
            input={
                "basis": {"domain": "ZZ", "entries": [["1"]]},
                "resource_budget": {"wall_seconds": 1},
            },
        )
    )

    assert result.execution.status is ExecutionStatus.TIMEOUT
    assert result.diagnostics[0].code == "FLINT_LLL_TIMEOUT"
    assert result.artifact_uris == ()
