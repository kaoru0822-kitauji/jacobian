from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from tests.helpers.capabilities import invoke_capability as _invoke
from tests.helpers.rationals import rational_payload as _q

from jacobian.bounded_process import BoundedProcessResult
from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityMode,
    CapabilityProviderAvailability,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel
from jacobian.linear_capabilities import (
    install_linear_rational_inconsistency_checker,
)

pytestmark = pytest.mark.usefixtures("initialized_kernel_store")


def _system(coefficients: list[list[int]], rhs: list[int]) -> dict[str, Any]:
    return {
        "variables": [f"x{index}" for index in range(len(coefficients[0]))],
        "coefficients": {
            "entries": [[_q(value) for value in row] for row in coefficients]
        },
        "rhs": [_q(value) for value in rhs],
    }


def _kernel_with_checker(root: Path) -> JacobianKernel:
    kernel = JacobianKernel(root)
    adapter, _installation = install_linear_rational_inconsistency_checker(
        kernel.store,
        kernel.schemas,
        kernel.artifacts,
        kernel.linear,
        kernel.verification,
        kernel.checkers,
        authorize_checker=True,
    )
    assert adapter is not None
    kernel.register_capability(adapter)
    return kernel


def test_python_flint_finds_normalized_unverified_inconsistency_witness(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    assert (
        kernel.python_flint_runtime.availability
        is CapabilityProviderAvailability.AVAILABLE
    )
    result = _invoke(
        kernel,
        "linear.rational_inconsistency.find",
        {
            "system": _system([[1, 1], [2, 2]], [1, 3]),
            "resource_budget": {"wall_seconds": 5},
        },
        mode=CapabilityMode.EXPLORE,
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["status"] == "CERTIFICATE_PRODUCED"
    assert result.output["left_witness"] == [_q(-2), _q(1)]
    assert result.output["rhs_pairing"] == _q(1)
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["verification"] == "UNVERIFIED"
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert (
        result.relationships[0].relation_id
        == "linear.relation.inconsistency-certificate-of"
    )
    resolved = kernel.linear.resolve_inconsistency(result.output["certificate_uri"])
    assert (
        resolved.certificate.system.system_artifact_uri == result.output["system_uri"]
    )
    assert result.output["system_uri"] in resolved.artifact.manifest.parents


def test_no_certificate_is_not_a_consistency_conclusion(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    result = _invoke(
        kernel,
        "linear.rational_inconsistency.find",
        {"system": _system([[1, 0], [0, 1]], [2, 3])},
        mode=CapabilityMode.EXPLORE,
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["status"] == "NO_CERTIFICATE_PRODUCED"
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["certificate_uri"] is None
    assert result.completeness.status is CapabilityCompletenessStatus.UNKNOWN


def test_independent_checker_verifies_inconsistency(tmp_path: Path) -> None:
    kernel = _kernel_with_checker(tmp_path)
    found = _invoke(
        kernel,
        "linear.rational_inconsistency.find",
        {"system": _system([[1, 1], [2, 2]], [1, 3])},
        mode=CapabilityMode.EXPLORE,
    )
    verified = _invoke(
        kernel,
        "linear.rational_inconsistency.verify",
        {"certificate_uri": found.output["certificate_uri"]},
        mode=CapabilityMode.VERIFY,
    )

    assert verified.output["status"] == "VERIFIED_INCONSISTENT"
    assert verified.output["conclusion"] == "TRUE"
    assert verified.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert verified.relationships[0].status.value == "VERIFIED"
    assert verified.output["verification_record_uri"].startswith("artifact://sha256/")


def test_inconsistency_timeout_retains_no_certificate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path)
    monkeypatch.setattr(
        "jacobian.flint_linear.run_bounded_process",
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
        "linear.rational_inconsistency.find",
        {"system": _system([[1]], [1])},
        mode=CapabilityMode.EXPLORE,
    )

    assert result.execution.status is ExecutionStatus.TIMEOUT
    assert result.output["status"] == "NO_CERTIFICATE_PRODUCED"
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["certificate_uri"] is None
    assert result.assurance.level is not CapabilityAssuranceLevel.VERIFIED
