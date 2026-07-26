from __future__ import annotations

from pathlib import Path

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.exact_domain_checkers import install_exact_domain_verification
from jacobian.kernel import JacobianKernel


def _q(numerator: int, denominator: int = 1) -> dict[str, str]:
    return {"num": str(numerator), "den": str(denominator)}


def _poly(*coefficients_ascending: int) -> dict[str, object]:
    return {
        "variables": ["x"],
        "polynomial": {
            "terms": [
                {"coefficient": _q(coefficient), "exponents": [exponent]}
                for exponent, coefficient in reversed(
                    tuple(enumerate(coefficients_ascending))
                )
                if coefficient
            ]
        },
    }


def _install_verification(
    kernel: JacobianKernel, *, authorize: bool
) -> tuple[object, ...]:
    adapters, _ = install_exact_domain_verification(
        kernel.store,
        kernel.schemas,
        kernel.artifacts,
        kernel.verification,
        kernel.checkers,
        polynomial=kernel.domain_bundles["polynomial"],
        matrix=kernel.domain_bundles["matrix_lattice"],
        authorize=authorize,
    )
    for adapter in adapters:
        kernel.register_capability(adapter)
    return adapters


def _computed_gcd(kernel: JacobianKernel):
    return kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.compute.gcd",
            input={
                "left": _poly(-1, 0, 1),
                "right": _poly(0, 1, 1),
            },
        )
    )


def test_public_seam_verifies_exact_producer_result(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    _install_verification(kernel, authorize=True)
    computed = _computed_gcd(kernel)

    verified = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.result.verify",
            mode=CapabilityMode.VERIFY,
            input={"result_uri": computed.output["result_uri"]},
        )
    )

    assert verified.execution.status is ExecutionStatus.COMPLETED
    assert verified.output["status"] == "VERIFIED"
    assert verified.output["operation_id"] == "polynomial.compute.gcd"
    assert verified.output["result_uri"] == computed.output["result_uri"]
    assert verified.output["verification_record_uri"] is not None
    assert verified.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert len(verified.artifact_uris) == 4


def test_public_seam_rejects_validly_shaped_false_result(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    _install_verification(kernel, authorize=True)
    computed = _computed_gcd(kernel)
    input_uri = computed.output["input_uri"]
    installed = kernel.domain_bundles["polynomial"]
    false_result = kernel.artifacts.put(
        schema_uri=installed.result_schema_uris["polynomial.compute.gcd"],
        semantics_uri=installed.semantics_uri,
        parents=(input_uri,),
        payload={
            "gcd": _poly(1),
            "bezout": {
                "left_multiplier": _poly(),
                "right_multiplier": _poly(),
            },
            "normalization": "MONIC",
        },
        summary="adversarial false GCD candidate",
    )

    rejected = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.result.verify",
            mode=CapabilityMode.VERIFY,
            input={"result_uri": false_result.artifact_uri},
        )
    )

    assert rejected.execution.status is ExecutionStatus.COMPLETED
    assert rejected.output["status"] == "REJECTED"
    assert rejected.output["conclusion"] == "UNKNOWN"
    assert rejected.output["verification_record_uri"] is None
    assert rejected.assurance.level is CapabilityAssuranceLevel.COMPUTED


def test_operator_can_leave_exact_result_verification_unavailable(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)

    adapters = _install_verification(kernel, authorize=False)

    assert adapters == ()
    assert {"polynomial.result.verify", "matrix.result.verify"}.isdisjoint({
        descriptor.capability_id
        for descriptor in kernel.capabilities.catalog().capabilities
    })
