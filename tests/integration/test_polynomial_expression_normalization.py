from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

import jacobian.provider_runtime as provider_runtime
from jacobian.bounded_process import BoundedProcessResult
from jacobian.canonical import canonicalize_json
from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityInstallTier,
    CapabilityMode,
    CapabilityProviderAvailability,
    CapabilityRequest,
    CapabilityResult,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel
from jacobian.polynomial_expression_capabilities import (
    install_polynomial_expression_checker,
)

pytestmark = pytest.mark.usefixtures("initialized_kernel_store")


def _q(num: int | str, den: int | str = 1) -> dict[str, str]:
    return {"num": str(num), "den": str(den)}


def _variable(name: str) -> dict[str, Any]:
    return {"kind": "variable", "name": name}


def _expression(
    node: dict[str, Any],
    *,
    variables: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "variables": variables or ["x", "y"],
        "expression": node,
    }


def _invoke(
    kernel: JacobianKernel,
    capability_id: str,
    payload: dict[str, Any],
    *,
    mode: CapabilityMode,
) -> CapabilityResult:
    return kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id=capability_id,
            mode=mode,
            input=payload,
        )
    )


def _kernel_with_checker(root: Path) -> JacobianKernel:
    kernel = JacobianKernel(root)
    adapter, _installation = install_polynomial_expression_checker(
        kernel.store,
        kernel.schemas,
        kernel.artifacts,
        kernel.polynomial_expressions,
        kernel.verification,
        kernel.checkers,
        authorize_checker=True,
    )
    assert adapter is not None
    kernel.register_capability(adapter)
    return kernel


def _difference_of_squares_plus_half_x() -> dict[str, Any]:
    return _expression(
        {
            "kind": "add",
            "operands": [
                {
                    "kind": "multiply",
                    "operands": [
                        {
                            "kind": "add",
                            "operands": [_variable("x"), _variable("y")],
                        },
                        {
                            "kind": "add",
                            "operands": [
                                _variable("x"),
                                {"kind": "negate", "operand": _variable("y")},
                            ],
                        },
                    ],
                },
                {
                    "kind": "multiply",
                    "operands": [
                        {"kind": "rational", "value": _q(1, 2)},
                        _variable("x"),
                    ],
                },
            ],
        }
    )


def test_sympy_normalizes_typed_multivariate_expression(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)

    result = _invoke(
        kernel,
        "polynomial.expression.normalize",
        {
            "expression": _difference_of_squares_plus_half_x(),
            "resource_budget": {"wall_seconds": 5},
        },
        mode=CapabilityMode.EXPLORE,
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["status"] == "NORMALIZATION_PRODUCED"
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["verification"] == "UNVERIFIED"
    assert result.output["normalized"] == {
        "terms": [
            {"coefficient": _q(1), "exponents": [2, 0]},
            {"coefficient": _q(1, 2), "exponents": [1, 0]},
            {"coefficient": _q(-1), "exponents": [0, 2]},
        ]
    }
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.relationships[0].relation_id == (
        "polynomial.relation.expression-normalization-of"
    )

    resolved = kernel.polynomial_expressions.resolve_normalization(
        result.output["normalization_uri"]
    )
    assert (
        resolved.candidate.source.expression_artifact_uri
        == result.output["expression_uri"]
    )
    assert result.output["expression_uri"] in resolved.artifact.manifest.parents


def test_sympy_normalization_preserves_exact_zero(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    result = _invoke(
        kernel,
        "polynomial.expression.normalize",
        {
            "expression": _expression(
                {
                    "kind": "add",
                    "operands": [
                        _variable("x"),
                        {"kind": "negate", "operand": _variable("x")},
                    ],
                },
                variables=["x"],
            )
        },
        mode=CapabilityMode.EXPLORE,
    )

    assert result.output["normalized"] == {"terms": []}
    assert result.output["status"] == "NORMALIZATION_PRODUCED"


def test_sympy_normalization_runtime_has_exact_profile(tmp_path: Path) -> None:
    runtime = JacobianKernel(tmp_path).sympy_polynomial_normalization_runtime

    assert runtime.availability is CapabilityProviderAvailability.AVAILABLE
    assert runtime.version == "1.14.0"
    assert runtime.install_tier is CapabilityInstallTier.T0
    assert runtime.digest is not None and runtime.digest.startswith("sha256:")
    assert runtime.configuration == {
        "distribution": "sympy",
        "domain": "QQ",
        "operation": "Poly(expression, *variables, domain=QQ).terms()",
        "expression_schema_version": "1",
        "maximum_variables": 4,
        "maximum_nodes": 128,
        "maximum_depth": 16,
        "maximum_expanded_terms": 1024,
        "maximum_exponent_per_variable": 127,
        "maximum_coefficient_digit_budget": 4096,
    }


def test_sympy_normalization_runtime_rejects_unpinned_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    available = provider_runtime.sympy_polynomial_normalization_provider_runtime()
    wrong = available.model_copy(update={"version": "1.13.3"})
    monkeypatch.setattr(
        provider_runtime,
        "python_distribution_provider_runtime",
        lambda *_args, **_kwargs: wrong,
    )

    rejected = provider_runtime.sympy_polynomial_normalization_provider_runtime(
        refresh=True
    )

    assert rejected.availability is CapabilityProviderAvailability.UNAVAILABLE
    assert rejected.version is None
    assert rejected.digest is None
    assert "pinned 1.14.0" in rejected.diagnostic


@pytest.mark.parametrize(
    "expression",
    [
        {
            "variables": ["x"],
            "expression": {"kind": "variable", "name": "undeclared"},
        },
        {
            "variables": ["x"],
            "expression": {
                "kind": "formula",
                "value": "__import__('os').system('id')",
            },
        },
        {
            "variables": ["x"],
            "expression": {
                "kind": "power",
                "base": {
                    "kind": "add",
                    "operands": [_variable("x") for _ in range(16)],
                },
                "exponent": 4,
            },
        },
    ],
    ids=("undeclared_variable", "formula_string", "expansion_blowup"),
)
def test_normalization_rejects_inputs_outside_typed_ast_contract(
    tmp_path: Path,
    expression: dict[str, Any],
) -> None:
    result = _invoke(
        JacobianKernel(tmp_path),
        "polynomial.expression.normalize",
        {"expression": expression},
        mode=CapabilityMode.EXPLORE,
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.output["error"]["stage"] in {
        "capability_input_validation",
        "input_validation",
    }


def test_independent_checker_verifies_full_ast_relation(tmp_path: Path) -> None:
    kernel = _kernel_with_checker(tmp_path)
    computed = _invoke(
        kernel,
        "polynomial.expression.normalize",
        {"expression": _difference_of_squares_plus_half_x()},
        mode=CapabilityMode.EXPLORE,
    )
    verified = _invoke(
        kernel,
        "polynomial.expression_normalization.verify",
        {"normalization_uri": computed.output["normalization_uri"]},
        mode=CapabilityMode.VERIFY,
    )

    assert verified.execution.status is ExecutionStatus.COMPLETED
    assert verified.output["status"] == "VERIFIED_NORMALIZATION"
    assert verified.output["conclusion"] == "TRUE"
    assert verified.output["verification_record_uri"].startswith("artifact://sha256/")
    assert verified.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert verified.relationships[0].status.value == "VERIFIED"


def test_independent_checker_rejects_wrong_bound_coefficients(
    tmp_path: Path,
) -> None:
    kernel = _kernel_with_checker(tmp_path)
    expression_uri = kernel.polynomial_expressions.put_expression(
        _expression(_variable("x"), variables=["x"])
    ).artifact_uri
    candidate = kernel.polynomial_expressions.put_normalization(
        expression_uri=expression_uri,
        normalized={"terms": []},
        producer=kernel.sympy_polynomial_normalization_runtime,
        resource_budget={"wall_seconds": 5},
    )

    rejected = _invoke(
        kernel,
        "polynomial.expression_normalization.verify",
        {"normalization_uri": candidate.artifact_uri},
        mode=CapabilityMode.VERIFY,
    )

    assert rejected.execution.status is ExecutionStatus.COMPLETED
    assert rejected.output["status"] == "REJECTED"
    assert rejected.output["conclusion"] == "UNKNOWN"
    assert rejected.output["verification_record_uri"] is None
    assert rejected.assurance.level is not CapabilityAssuranceLevel.VERIFIED


def test_sympy_normalization_timeout_is_operational(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path)
    monkeypatch.setattr(
        "jacobian.sympy_polynomial_normalization.run_bounded_process",
        lambda *_args, **_kwargs: BoundedProcessResult(
            returncode=None,
            stdout=b"",
            stderr=b"",
            stdout_exceeded=False,
            stderr_exceeded=False,
            timed_out=True,
        ),
    )

    result = _invoke(
        kernel,
        "polynomial.expression.normalize",
        {"expression": _expression(_variable("x"), variables=["x"])},
        mode=CapabilityMode.EXPLORE,
    )

    assert result.execution.status is ExecutionStatus.TIMEOUT
    assert result.output["status"] == "NO_NORMALIZATION_PRODUCED"
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["normalization_uri"] is None
    assert result.assurance.level is not CapabilityAssuranceLevel.VERIFIED


def test_sympy_worker_gets_only_fixed_environment_and_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JACOBIAN_SYMPY_SECRET", "must-not-propagate")
    observed: dict[str, Any] = {}

    def fake_worker(*_args: Any, **kwargs: Any) -> BoundedProcessResult:
        observed.update(kwargs)
        stdout = (
            canonicalize_json(
                {
                    "protocol": "jacobian.sympy-polynomial-normalization/v1",
                    "status": "NORMALIZATION_PRODUCED",
                    "backend_version": "1.14.0",
                    "normalized": {
                        "terms": [
                            {
                                "coefficient": _q(1),
                                "exponents": [1],
                            }
                        ]
                    },
                }
            )
            + b"\n"
        )
        return BoundedProcessResult(
            returncode=0,
            stdout=stdout,
            stderr=b"",
            stdout_exceeded=False,
            stderr_exceeded=False,
            timed_out=False,
        )

    kernel = JacobianKernel(tmp_path)
    monkeypatch.setattr(
        "jacobian.sympy_polynomial_normalization.run_bounded_process",
        fake_worker,
    )
    result = _invoke(
        kernel,
        "polynomial.expression.normalize",
        {
            "expression": _expression(_variable("x"), variables=["x"]),
            "resource_budget": {"wall_seconds": 7},
        },
        mode=CapabilityMode.EXPLORE,
    )

    assert result.output["status"] == "NORMALIZATION_PRODUCED"
    assert observed["timeout_seconds"] == 7.0
    assert observed["environment"] == {
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
        "PYTHONHASHSEED": "0",
    }
    assert "JACOBIAN_SYMPY_SECRET" in os.environ
    assert "JACOBIAN_SYMPY_SECRET" not in observed["environment"]


def test_normalization_output_is_discarded_if_runtime_identity_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path)
    original = kernel.sympy_polynomial_normalization_runtime
    changed = original.model_copy(update={"digest": "sha256:" + "f" * 64})
    observations = iter((original, changed))
    monkeypatch.setattr(
        (
            "jacobian.sympy_polynomial_normalization."
            "sympy_polynomial_normalization_provider_runtime"
        ),
        lambda **_kwargs: next(observations),
    )
    monkeypatch.setattr(
        "jacobian.sympy_polynomial_normalization.run_bounded_process",
        lambda *_args, **_kwargs: BoundedProcessResult(
            returncode=0,
            stdout=canonicalize_json(
                {
                    "protocol": "jacobian.sympy-polynomial-normalization/v1",
                    "status": "NORMALIZATION_PRODUCED",
                    "backend_version": "1.14.0",
                    "normalized": {
                        "terms": [
                            {
                                "coefficient": _q(1),
                                "exponents": [1],
                            }
                        ]
                    },
                }
            )
            + b"\n",
            stderr=b"",
            stdout_exceeded=False,
            stderr_exceeded=False,
            timed_out=False,
        ),
    )

    result = _invoke(
        kernel,
        "polynomial.expression.normalize",
        {"expression": _expression(_variable("x"), variables=["x"])},
        mode=CapabilityMode.EXPLORE,
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.output["status"] == "NO_NORMALIZATION_PRODUCED"
    assert result.output["normalization_uri"] is None
    assert "changed during execution" in result.output["detail"]


def test_invalid_worker_protocol_retains_no_normalization_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path)
    monkeypatch.setattr(
        "jacobian.sympy_polynomial_normalization.run_bounded_process",
        lambda *_args, **_kwargs: BoundedProcessResult(
            returncode=0,
            stdout=b'{"status":"NORMALIZATION_PRODUCED"}\n',
            stderr=b"",
            stdout_exceeded=False,
            stderr_exceeded=False,
            timed_out=False,
        ),
    )

    result = _invoke(
        kernel,
        "polynomial.expression.normalize",
        {"expression": _expression(_variable("x"), variables=["x"])},
        mode=CapabilityMode.EXPLORE,
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.output["status"] == "NO_NORMALIZATION_PRODUCED"
    assert result.output["normalization_uri"] is None
    assert result.output["conclusion"] == "UNKNOWN"


def test_normalization_checker_timeout_is_operational(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = _kernel_with_checker(tmp_path)
    computed = _invoke(
        kernel,
        "polynomial.expression.normalize",
        {"expression": _expression(_variable("x"), variables=["x"])},
        mode=CapabilityMode.EXPLORE,
    )
    monkeypatch.setattr(
        "jacobian.verification.run_bounded_process",
        lambda *_args, **_kwargs: BoundedProcessResult(
            returncode=None,
            stdout=b"",
            stderr=b"",
            stdout_exceeded=False,
            stderr_exceeded=False,
            timed_out=True,
        ),
    )

    result = _invoke(
        kernel,
        "polynomial.expression_normalization.verify",
        {"normalization_uri": computed.output["normalization_uri"]},
        mode=CapabilityMode.VERIFY,
    )

    assert result.execution.status is ExecutionStatus.TIMEOUT
    assert result.output["status"] == "TIMEOUT"
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["verification_record_uri"] is None
    assert result.assurance.level is not CapabilityAssuranceLevel.VERIFIED
