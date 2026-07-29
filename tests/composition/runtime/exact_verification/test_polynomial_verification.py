from __future__ import annotations

from tests.support.rationals import rational_payload as _q

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.exact_domain_checkers import install_exact_domain_verification
from jacobian.runtime.model import JacobianRuntime


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


def _poly_xy(*terms: tuple[tuple[int, int], int]) -> dict[str, object]:
    return {
        "variables": ["x", "y"],
        "polynomial": {
            "terms": [
                {
                    "coefficient": _q(coefficient),
                    "exponents": list(exponents),
                }
                for exponents, coefficient in terms
            ]
        },
    }


def _install_verification(
    fresh_complete_runtime: JacobianRuntime, *, authorize: bool
) -> tuple[object, ...]:
    adapters, _ = install_exact_domain_verification(
        fresh_complete_runtime.core.store,
        fresh_complete_runtime.core.schemas,
        fresh_complete_runtime.core.artifacts,
        fresh_complete_runtime.services.verification,
        fresh_complete_runtime.core.checkers,
        polynomial=fresh_complete_runtime.portfolio.domain_bundles["polynomial"],
        matrix=fresh_complete_runtime.portfolio.domain_bundles["matrix"],
        probability=fresh_complete_runtime.portfolio.domain_bundles.get("probability"),
        authorize=authorize,
    )
    for adapter in adapters:
        fresh_complete_runtime.core.capabilities.register(adapter)
    return adapters


def _computed_gcd(fresh_complete_runtime: JacobianRuntime):
    return fresh_complete_runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.compute.gcd",
            input={
                "left": _poly(-1, 0, 1),
                "right": _poly(0, 1, 1),
            },
        )
    )


def test_public_seam_verifies_exact_producer_result(fresh_complete_runtime) -> None:
    adapters = _install_verification(fresh_complete_runtime, authorize=True)
    provider_runtime = adapters[0].descriptor.provider_runtime
    assert provider_runtime is not None
    assert {
        component["provider"]
        for component in provider_runtime.configuration["components"]
    } == {"jacobian.exact-domain-checker-source", "python-flint"}
    computed = _computed_gcd(fresh_complete_runtime)

    verified = fresh_complete_runtime.core.capabilities.invoke(
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


def test_public_seam_rejects_validly_shaped_false_result(
    fresh_complete_runtime,
) -> None:
    _install_verification(fresh_complete_runtime, authorize=True)
    computed = _computed_gcd(fresh_complete_runtime)
    input_uri = computed.output["input_uri"]
    installed = fresh_complete_runtime.portfolio.domain_bundles["polynomial"]
    false_result = fresh_complete_runtime.core.artifacts.put(
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

    rejected = fresh_complete_runtime.core.capabilities.invoke(
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


def test_public_seam_reports_valid_multivariate_result_as_unsupported(
    fresh_complete_runtime,
) -> None:
    _install_verification(fresh_complete_runtime, authorize=True)
    computed = fresh_complete_runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.compute.resultant",
            input={
                "left": _poly_xy(((1, 0), 1), ((0, 1), 1)),
                "right": _poly_xy(((1, 0), 1), ((0, 0), 1)),
                "elimination_variable": "x",
            },
        )
    )

    checked = fresh_complete_runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.result.verify",
            mode=CapabilityMode.VERIFY,
            input={"result_uri": computed.output["result_uri"]},
        )
    )

    assert checked.execution.status is ExecutionStatus.COMPLETED
    assert checked.output["status"] == "UNSUPPORTED"
    assert checked.output["conclusion"] == "UNKNOWN"
    assert checked.output["witness_uri"] is None
    assert checked.output["verification_record_uri"] is None
    assert checked.assurance.level is CapabilityAssuranceLevel.COMPUTED
