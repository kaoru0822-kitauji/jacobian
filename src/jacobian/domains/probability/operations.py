"""Exact finite probability operations backed by Python-FLINT."""

from flint import fmpq

from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.validated_analysis import (
    FiniteRawMomentContribution,
    FiniteRawMomentRequest,
    FiniteRawMomentResult,
)
from jacobian.operations import (
    ComputedOperation,
    ComputedOutcome,
    ComputedSuccess,
)


def _fmpq(value: CanonicalRational) -> fmpq:
    return fmpq(int(value.num), int(value.den))


def _wire(value: fmpq) -> CanonicalRational:
    return CanonicalRational(num=str(value.p), den=str(value.q))


def _raw_moment(
    request: FiniteRawMomentRequest,
) -> ComputedOutcome[FiniteRawMomentResult]:
    contributions: list[FiniteRawMomentContribution] = []
    total = fmpq(0)
    for atom in request.atoms:
        powered = _fmpq(atom.value) ** request.order
        contribution = _fmpq(atom.probability) * powered
        total += contribution
        contributions.append(
            FiniteRawMomentContribution(
                value=atom.value,
                probability=atom.probability,
                powered_value=_wire(powered),
                contribution=_wire(contribution),
            )
        )
    return ComputedSuccess(
        FiniteRawMomentResult(
            order=request.order,
            moment=_wire(total),
            contributions=tuple(contributions),
        )
    )


FINITE_MOMENT_CAPABILITIES = (
    ComputedOperation(
        capability_id="probability.finite_distribution.raw_moment.compute",
        title="Exact finite-distribution raw moment",
        description=(
            "Compute one bounded raw moment of a normalized finite exact "
            "rational distribution, preserving every atom contribution."
        ),
        request_model=FiniteRawMomentRequest,
        result_model=FiniteRawMomentResult,
        implementation=_raw_moment,
        relation_id="probability.finite_distribution.raw_moment.relation",
        tags=("probability", "moment", "finite", "exact", "python-flint"),
    ),
)

__all__ = ["FINITE_MOMENT_CAPABILITIES"]
