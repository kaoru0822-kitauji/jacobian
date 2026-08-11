from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from tests.support.exact_domain import open_exact_domain_services

from jacobian.contracts.capabilities import CapabilityRequest
from jacobian.domains.finite_fields import build_finite_field_bundle
from jacobian.domains.finite_fields.contracts import (
    LinearMapRankRequest,
    RestrictScalarsRequest,
)
from jacobian.math.finite_fields import (
    Axis,
    AxisBoundMatrix,
    FiniteDimensionalSubspace,
    FiniteFieldElement,
    FiniteFieldPresentation,
    FiniteLinearMap,
    ProjectivePoint,
)
from jacobian.math.prime_field_linear_algebra import PrimeFieldMatrix

pytestmark = pytest.mark.requires_provider("flint")


def _request() -> LinearMapRankRequest:
    presentation = FiniteFieldPresentation(
        characteristic=2,
        modulus_coefficients=(1, 1, 1),
    )
    axis = Axis(name="b", labels=("b1",))
    direction = ProjectivePoint(
        presentation=presentation,
        axis=axis,
        coordinates=(
            FiniteFieldElement(presentation=presentation, coordinates=(1, 0)),
        ),
    )
    linear_map = FiniteLinearMap(
        source_axis=Axis(name="source", labels=("B1",)),
        target_axis=Axis(name="target", labels=("y1", "y2")),
        matrix=PrimeFieldMatrix(prime=2, entries=((1,), (0,)), columns=1),
    )
    return LinearMapRankRequest(direction=direction, linear_map=linear_map)


def _restriction_request() -> RestrictScalarsRequest:
    presentation = FiniteFieldPresentation(
        characteristic=2,
        modulus_coefficients=(1, 1, 1),
    )
    row_axis = Axis(name="b", labels=("b1",))
    column_axis = Axis(name="y", labels=("y1",))
    basis_axis = Axis(name="basis", labels=("B1",))
    one = FiniteFieldElement(presentation=presentation, coordinates=(1, 0))
    a = FiniteFieldElement(presentation=presentation, coordinates=(0, 1))
    subspace = FiniteDimensionalSubspace(
        presentation=presentation,
        basis_axis=basis_axis,
        basis=(
            AxisBoundMatrix(
                presentation=presentation,
                row_axis=row_axis,
                column_axis=column_axis,
                entries=((a,),),
            ),
        ),
    )
    direction = ProjectivePoint(
        presentation=presentation,
        axis=row_axis,
        coordinates=(one,),
    )
    return RestrictScalarsRequest(subspace=subspace, direction=direction)


def test_operator_authorized_sympy_replay_accepts_rank_and_rejects_forgery(
    tmp_path: Path,
) -> None:
    request = _request()
    input_payload = request.model_dump(mode="json")

    with open_exact_domain_services(
        tmp_path,
        build_finite_field_bundle(),
    ) as services:
        computed = services.core.capabilities.invoke(
            CapabilityRequest(
                capability_id="finite_field.linear_map.rank.compute",
                input=input_payload,
            )
        )
        candidate = computed.output["result"]
        verified = services.core.capabilities.invoke(
            CapabilityRequest(
                capability_id="finite_field.linear_map.rank.verify",
                input={"input": input_payload, "candidate": candidate},
            )
        )
        forged = {**candidate, "rank": 0}
        rejected = services.core.capabilities.invoke(
            CapabilityRequest(
                capability_id="finite_field.linear_map.rank.verify",
                input={"input": input_payload, "candidate": forged},
            )
        )

    assert computed.output["result"]["rank"] == 1
    assert verified.output["status"] == "VERIFIED"
    assert verified.output["verification_record_uri"] in verified.artifact_uris
    assert rejected.output["status"] == "REJECTED"
    assert rejected.output["verification_record_uri"] is None


def test_operator_authorized_sympy_replay_checks_restriction_of_scalars(
    tmp_path: Path,
) -> None:
    request = _restriction_request()
    input_payload = request.model_dump(mode="json")

    with open_exact_domain_services(
        tmp_path,
        build_finite_field_bundle(),
    ) as services:
        computed = services.core.capabilities.invoke(
            CapabilityRequest(
                capability_id="finite_field.restrict_scalars.compute",
                input=input_payload,
            )
        )
        candidate = computed.output["result"]
        verified = services.core.capabilities.invoke(
            CapabilityRequest(
                capability_id="finite_field.restrict_scalars.verify",
                input={"input": input_payload, "candidate": candidate},
            )
        )
        forged = deepcopy(candidate)
        forged["matrix"]["entries"] = [[1], [0]]
        rejected = services.core.capabilities.invoke(
            CapabilityRequest(
                capability_id="finite_field.restrict_scalars.verify",
                input={"input": input_payload, "candidate": forged},
            )
        )

    assert candidate["matrix"]["entries"] == [[0], [1]]
    assert verified.output["status"] == "VERIFIED"
    assert rejected.output["status"] == "REJECTED"
    assert rejected.output["verification_record_uri"] is None
