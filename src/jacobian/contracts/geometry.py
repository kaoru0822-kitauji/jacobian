"""Exact rational planar-geometry wire contracts."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from jacobian.contracts.common import ArtifactUri
from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.results import ContractModel


class RationalPoint2D(ContractModel):
    x: CanonicalRational
    y: CanonicalRational


class PointPairRequest(ContractModel):
    first: RationalPoint2D
    second: RationalPoint2D


class LineRequest(ContractModel):
    first: RationalPoint2D
    second: RationalPoint2D

    @model_validator(mode="after")
    def require_distinct_points(self) -> Self:
        if self.first == self.second:
            raise ValueError("a line requires two distinct points")
        return self


class LinePairRequest(ContractModel):
    first_line: LineRequest
    second_line: LineRequest


class PointLineRequest(ContractModel):
    point: RationalPoint2D
    line: LineRequest


class PointTripleRequest(ContractModel):
    first: RationalPoint2D
    second: RationalPoint2D
    third: RationalPoint2D


class PointQuadrupleRequest(PointTripleRequest):
    fourth: RationalPoint2D


class PointSetRequest(ContractModel):
    points: tuple[RationalPoint2D, ...] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def require_unique_points(self) -> Self:
        keys = tuple(
            (point.x.num, point.x.den, point.y.num, point.y.den)
            for point in self.points
        )
        if len(keys) != len(set(keys)):
            raise ValueError("point-set coordinates must be unique")
        return self


class PolygonRequest(PointSetRequest):
    points: tuple[RationalPoint2D, ...] = Field(min_length=3, max_length=128)


class GeometryBooleanResult(ContractModel):
    holds: bool


class GeometryRationalResult(ContractModel):
    value: CanonicalRational


class GeometryPointResult(ContractModel):
    point: RationalPoint2D


class GeometryOrientationResult(ContractModel):
    orientation: Literal[-1, 0, 1]


class GeometryLineIntersectionResult(ContractModel):
    status: Literal["POINT", "PARALLEL", "COINCIDENT"]
    point: RationalPoint2D | None = None

    @model_validator(mode="after")
    def bind_point_status(self) -> Self:
        if (self.status == "POINT") is (self.point is None):
            raise ValueError("only POINT intersections carry one point")
        return self


class GeometryPointSetResult(ContractModel):
    points: tuple[RationalPoint2D, ...]


class GeometryCircleResult(ContractModel):
    center: RationalPoint2D
    radius_squared: CanonicalRational


class GeometryOperationOutput(ContractModel):
    input_uri: ArtifactUri
    result_uri: ArtifactUri
    result: dict[str, object]
    backend_version: str


class GeometryVerificationRequest(ContractModel):
    result_uri: ArtifactUri


class GeometryVerificationOutput(ContractModel):
    status: Literal["VERIFIED_RESULT", "REJECTED", "TIMEOUT", "CANCELLED", "ERROR"]
    conclusion: Literal["TRUE", "UNKNOWN"]
    operation_id: Literal[
        "geometry.points.compute.squared_distance",
        "geometry.segment.compute.midpoint",
        "geometry.triangle.compute.orientation",
        "geometry.triangle.compute.centroid",
    ]
    input_uri: ArtifactUri
    result_uri: ArtifactUri
    witness_uri: ArtifactUri
    checker_id: str
    verification_record_uri: ArtifactUri | None = None
    detail: str
