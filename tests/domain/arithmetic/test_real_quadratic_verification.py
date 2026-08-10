from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from tests.support.services import DomainTestServices, open_domain_services

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.domains.arithmetic import build_arithmetic_bundle
from jacobian.exact_domain_checkers import install_exact_domain_verification
from jacobian.portfolio.domain_installation import DomainBundleInstaller
from jacobian.portfolio.model import PortfolioPlan
from jacobian.runtime.config import CheckerAuthorityMode


@pytest.fixture
def arithmetic_services(tmp_path: Path) -> Iterator[DomainTestServices]:
    bundle = build_arithmetic_bundle()
    with open_domain_services(
        tmp_path / "state",
        checker_authority=CheckerAuthorityMode.INSTALL_BUNDLED,
    ) as services:
        installed = DomainBundleInstaller(services.installation).install(
            PortfolioPlan(domain_bundles=(bundle,))
        )
        adapters, _ = install_exact_domain_verification(
            services.core.store,
            services.core.schemas,
            services.core.artifacts,
            services.application.verification,
            services.core.checkers,
            bundles={"arithmetic": (bundle, installed.installed["arithmetic"])},
            authorize=services.installation.authorizes_bundled_checkers,
        )
        for adapter in adapters:
            services.installation.register_capability(adapter)
        yield services


def _q(numerator: int, denominator: int = 1) -> dict[str, str]:
    return {"num": str(numerator), "den": str(denominator)}


def _value(
    rational_numerator: int,
    radical_numerator: int,
    *,
    rational_denominator: int = 1,
    radical_denominator: int = 1,
) -> dict[str, object]:
    return {
        "rational_part": _q(rational_numerator, rational_denominator),
        "radical_coefficient": _q(radical_numerator, radical_denominator),
        "radicand": 3,
    }


def test_pang_m4_quadratic_order_is_independently_verified(
    arithmetic_services: DomainTestServices,
) -> None:
    payload = {
        "left": _value(0, 3, radical_denominator=8),
        "right": _value(
            1,
            1,
            rational_denominator=2,
            radical_denominator=20,
        ),
    }
    computed = arithmetic_services.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="arithmetic.real_quadratic.order.compute",
            input=payload,
        )
    )
    verified = arithmetic_services.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="arithmetic.real_quadratic.order.verify",
            mode=CapabilityMode.VERIFY,
            input={"input": payload, "candidate": computed.output["result"]},
        )
    )

    assert computed.execution.status is ExecutionStatus.COMPLETED
    assert computed.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert computed.output["result"] == {
        "result_schema_version": "1",
        "left": _value(0, 3, radical_denominator=8),
        "right": _value(
            1,
            1,
            rational_denominator=2,
            radical_denominator=20,
        ),
        "difference": _value(
            -1,
            13,
            rational_denominator=2,
            radical_denominator=40,
        ),
        "order": "GT",
        "sign_basis": "OPPOSING_SIGNS_SQUARED_MAGNITUDES",
        "sign_certificate": {
            "rational_part_squared": _q(1, 4),
            "radical_part_squared": _q(507, 1600),
            "magnitude_order": "LT",
        },
        "arithmetic": "EXACT_REAL_QUADRATIC",
    }
    assert verified.execution.status is ExecutionStatus.COMPLETED
    assert verified.output["status"] == "VERIFIED"
    assert verified.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert verified.output["verification_record_uri"] in verified.artifact_uris


def test_real_quadratic_checker_rejects_a_result_for_different_input(
    arithmetic_services: DomainTestServices,
) -> None:
    payload = {"left": _value(0, 1), "right": _value(0, -1)}
    different = arithmetic_services.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="arithmetic.real_quadratic.order.compute",
            input={"left": payload["right"], "right": payload["left"]},
        )
    )

    rejected = arithmetic_services.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="arithmetic.real_quadratic.order.verify",
            mode=CapabilityMode.VERIFY,
            input={"input": payload, "candidate": different.output["result"]},
        )
    )

    assert rejected.execution.status is ExecutionStatus.COMPLETED
    assert rejected.output["status"] == "REJECTED"
    assert rejected.output["conclusion"] == "UNKNOWN"
    assert rejected.output["verification_record_uri"] is None
    assert rejected.assurance.level is CapabilityAssuranceLevel.COMPUTED
