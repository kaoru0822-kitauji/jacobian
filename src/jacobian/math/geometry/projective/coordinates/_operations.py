"""Domain functions for projective coordinate operations."""

from __future__ import annotations

from fractions import Fraction

from pydantic_core import PydanticCustomError

from jacobian._exact import CanonicalRational
from jacobian.canonical import format_canonical_integer
from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.geometry.projective.coordinates._models import (
    MAX_PROJECTIVE_COORDINATE_DIGITS,
    ChartTransitionRequest,
    ChartTransitionResult,
    RationalPointConstructRequest,
    RationalPointConstructResult,
    RationalProjectivePoint,
    StandardChartRequest,
    StandardChartResult,
)


def _validation_error(reason: str, message: str) -> PydanticCustomError:
    return PydanticCustomError(f"geometry.{reason}", message)


def _require_ratio_result_budget(
    coordinates: tuple[CanonicalRational, ...],
) -> None:
    if any(
        len(component.lstrip("-")) > MAX_PROJECTIVE_COORDINATE_DIGITS
        for coordinate in coordinates
        for component in (coordinate.num, coordinate.den)
    ):
        raise _validation_error(
            "projective_coordinate_components_exceed_digit_ratio",
            "projective coordinate components exceed the 16,384-digit ratio budget",
        )


def _admit(request: RationalPointConstructRequest | StandardChartRequest | ChartTransitionRequest) -> None:
    coordinates = (
        request.coordinates
        if isinstance(request, RationalPointConstructRequest)
        else request.point.coordinates
    )
    try:
        _require_ratio_result_budget(coordinates)
        if isinstance(request, RationalPointConstructRequest):
            if all(c.as_fraction() == 0 for c in coordinates):
                raise _validation_error(
                    "projective_point_least_nonzero_coordinate",
                    "projective point must have at least one nonzero coordinate",
                )
            return
        if isinstance(request, StandardChartRequest):
            if request.chart_index >= len(coordinates):
                raise _validation_error("chart_index_out_range", "chart_index out of range")
            if coordinates[request.chart_index].as_fraction() == 0:
                raise _validation_error(
                    "chart_coordinate_nonzero", "chart coordinate must be nonzero"
                )
            return
        n = len(coordinates)
        if request.chart_i >= n or request.chart_j >= n:
            raise _validation_error("chart_index_out_range", "chart index out of range")
        if coordinates[request.chart_i].as_fraction() == 0:
            raise _validation_error(
                "chart_i_coordinate_nonzero", "chart_i coordinate must be nonzero"
            )
    except PydanticCustomError as exc:
        raise OperationDomainValidationError(
            location=("request",), code=exc.type, message=exc.message()
        ) from exc


def _rational(frac: Fraction) -> CanonicalRational:
    return CanonicalRational(
        num=format_canonical_integer(frac.numerator),
        den=format_canonical_integer(frac.denominator),
    )


def compute_rational_point_construct(
    request: RationalPointConstructRequest,
) -> RationalPointConstructResult:
    """Canonicalize by scaling so first nonzero coordinate is 1."""
    _admit(request)
    coords = request.coordinates
    for _i, c in enumerate(coords):
        if c.as_fraction() != 0:
            inv = Fraction(1, 1) / c.as_fraction()
            scale = _rational(inv)
            canonical = tuple(_rational(v.as_fraction() * inv) for v in coords)
            return RationalPointConstructResult(
                point=RationalProjectivePoint(coordinates=canonical),
                scale=scale,
            )
    raise ValueError("all coordinates are zero")


def compute_standard_chart(request: StandardChartRequest) -> StandardChartResult:
    """Dehomogenize at the given chart index (divide by that coordinate)."""
    _admit(request)
    coords = request.point.coordinates
    chart = request.chart_index
    inv = Fraction(1, 1) / coords[chart].as_fraction()
    affine = tuple(
        _rational(coords[i].as_fraction() * inv)
        for i in range(len(coords))
        if i != chart
    )
    return StandardChartResult(
        affine_point=affine,
        chart_index=chart,
    )


def compute_chart_transition(request: ChartTransitionRequest) -> ChartTransitionResult:
    """Return the complete target-chart coordinates for the projective point."""
    _admit(request)
    coords = request.point.coordinates
    xj = coords[request.chart_j].as_fraction()
    if xj == 0:
        return ChartTransitionResult(
            status="OUTSIDE_TARGET_CHART",
            transition=None,
            chart_i=request.chart_i,
            chart_j=request.chart_j,
            projective_dimension=len(coords) - 1,
        )
    ratios = tuple(
        _rational(coords[i].as_fraction() / xj)
        for i in range(len(coords))
        if i != request.chart_j
    )
    return ChartTransitionResult(
        status="DEFINED",
        transition=ratios,
        chart_i=request.chart_i,
        chart_j=request.chart_j,
        projective_dimension=len(coords) - 1,
    )
