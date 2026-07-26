"""Exact rational planar-geometry capability adapters."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, cast

import sympy
from pydantic import ValidationError
from sympy.geometry import Circle, Line2D, Point2D, Polygon
from sympy.geometry.util import convex_hull

from jacobian.artifacts import ArtifactService
from jacobian.capabilities import CapabilityInvocationError
from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityCompleteness,
    CapabilityCompletenessStatus,
    CapabilityDescriptor,
    CapabilityDiagnostic,
    CapabilityMode,
    CapabilityRelationship,
    CapabilityRequest,
    CapabilityResult,
    CapabilityScope,
)
from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.geometry import (
    GeometryBooleanResult,
    GeometryCircleResult,
    GeometryLineIntersectionResult,
    GeometryOperationOutput,
    GeometryOrientationResult,
    GeometryPointResult,
    GeometryPointSetResult,
    GeometryRationalResult,
    LinePairRequest,
    LineRequest,
    PointLineRequest,
    PointPairRequest,
    PointQuadrupleRequest,
    PointSetRequest,
    PointTripleRequest,
    PolygonRequest,
    RationalPoint2D,
)
from jacobian.contracts.results import ContractModel, Execution, ExecutionStatus
from jacobian.provider_runtime import known_provider_runtime
from jacobian.schema_registry import SchemaRegistry, model_schema
from jacobian.store import ArtifactStore

Compute = Callable[[ContractModel], ContractModel]


@dataclass(frozen=True, slots=True)
class GeometrySpec:
    capability_id: str
    title: str
    description: str
    request_model: type[ContractModel]
    result_model: type[ContractModel]
    compute: Compute
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GeometryResources:
    artifacts: ArtifactService
    semantics_uri: str
    input_schema_uris: dict[type[ContractModel], str]
    result_schema_uris: dict[str, str]


def _fraction(value: Any) -> Fraction:
    rational = sympy.Rational(value)
    return Fraction(int(rational.p), int(rational.q))


def _wire_rational(value: Any) -> CanonicalRational:
    fraction = _fraction(value)
    return CanonicalRational(
        num=str(fraction.numerator),
        den=str(fraction.denominator),
    )


def _point(value: RationalPoint2D) -> Point2D:
    return Point2D(
        sympy.Rational(int(value.x.num), int(value.x.den)),
        sympy.Rational(int(value.y.num), int(value.y.den)),
    )


def _wire_point(value: Point2D) -> RationalPoint2D:
    return RationalPoint2D(
        x=_wire_rational(value.x),
        y=_wire_rational(value.y),
    )


def _pair_points(request: ContractModel) -> tuple[Point2D, Point2D]:
    pair = cast(PointPairRequest, request)
    return _point(pair.first), _point(pair.second)


def _line(value: LineRequest) -> Line2D:
    return Line2D(_point(value.first), _point(value.second))


def _squared_distance(request: ContractModel) -> ContractModel:
    first, second = _pair_points(request)
    return GeometryRationalResult(value=_wire_rational(first.distance(second) ** 2))


def _midpoint(request: ContractModel) -> ContractModel:
    first, second = _pair_points(request)
    return GeometryPointResult(point=_wire_point(first.midpoint(second)))


def _collinear(request: ContractModel) -> ContractModel:
    triple = cast(PointTripleRequest, request)
    return GeometryBooleanResult(
        holds=Point2D.is_collinear(
            _point(triple.first),
            _point(triple.second),
            _point(triple.third),
        )
    )


def _concyclic(request: ContractModel) -> ContractModel:
    points = cast(PointQuadrupleRequest, request)
    return GeometryBooleanResult(
        holds=Point2D.is_concyclic(
            _point(points.first),
            _point(points.second),
            _point(points.third),
            _point(points.fourth),
        )
    )


def _line_predicate(
    predicate: Callable[[Line2D, Line2D], bool],
) -> Compute:
    def compute(request: ContractModel) -> ContractModel:
        pair = cast(LinePairRequest, request)
        return GeometryBooleanResult(
            holds=predicate(_line(pair.first_line), _line(pair.second_line))
        )

    return compute


def _line_intersection(request: ContractModel) -> ContractModel:
    pair = cast(LinePairRequest, request)
    first, second = _line(pair.first_line), _line(pair.second_line)
    if first.equals(second):
        return GeometryLineIntersectionResult(status="COINCIDENT")
    intersections = first.intersection(second)
    if not intersections:
        return GeometryLineIntersectionResult(status="PARALLEL")
    point = intersections[0]
    if not isinstance(point, Point2D):
        raise ValueError("line intersection did not produce one exact point")
    return GeometryLineIntersectionResult(status="POINT", point=_wire_point(point))


def _projection(request: ContractModel) -> ContractModel:
    value = cast(PointLineRequest, request)
    projected = _line(value.line).projection(_point(value.point))
    if not isinstance(projected, Point2D):
        raise ValueError("line projection did not produce one exact point")
    return GeometryPointResult(point=_wire_point(projected))


def _orientation(request: ContractModel) -> ContractModel:
    triple = cast(PointTripleRequest, request)
    first, second, third = (
        _point(triple.first),
        _point(triple.second),
        _point(triple.third),
    )
    determinant = (second.x - first.x) * (third.y - first.y) - (second.y - first.y) * (
        third.x - first.x
    )
    return GeometryOrientationResult(
        orientation=cast(Any, int(sympy.sign(determinant)))
    )


def _centroid(request: ContractModel) -> ContractModel:
    triple = cast(PointTripleRequest, request)
    points = [_point(triple.first), _point(triple.second), _point(triple.third)]
    return GeometryPointResult(
        point=_wire_point(
            Point2D(
                sum(point.x for point in points) / 3,
                sum(point.y for point in points) / 3,
            )
        )
    )


def _circumcircle(request: ContractModel) -> ContractModel:
    triple = cast(PointTripleRequest, request)
    points = [_point(triple.first), _point(triple.second), _point(triple.third)]
    if Point2D.is_collinear(*points):
        raise ValueError("a circumcircle requires three noncollinear points")
    circle = Circle(*points)
    return GeometryCircleResult(
        center=_wire_point(circle.center),
        radius_squared=_wire_rational(circle.radius**2),
    )


def _signed_area(request: ContractModel) -> ContractModel:
    polygon = cast(PolygonRequest, request)
    value = Polygon(*(_point(point) for point in polygon.points)).area
    return GeometryRationalResult(value=_wire_rational(value))


def _convex_hull(request: ContractModel) -> ContractModel:
    point_set = cast(PointSetRequest, request)
    hull = convex_hull(*(_point(point) for point in point_set.points))
    if isinstance(hull, Point2D):
        points = (hull,)
    elif isinstance(hull, Line2D):
        points = tuple(cast(tuple[Point2D, Point2D], hull.points))
    else:
        points = tuple(cast(Polygon, hull).vertices)
    return GeometryPointSetResult(points=tuple(_wire_point(point) for point in points))


def _spec(
    capability_id: str,
    title: str,
    description: str,
    request_model: type[ContractModel],
    result_model: type[ContractModel],
    compute: Compute,
    *tags: str,
) -> GeometrySpec:
    return GeometrySpec(
        capability_id,
        title,
        description,
        request_model,
        result_model,
        compute,
        tags,
    )


SPECS = (
    _spec(
        "geometry.points.compute.squared_distance",
        "Compute squared distance",
        "Compute exact squared Euclidean distance between two rational points.",
        PointPairRequest,
        GeometryRationalResult,
        _squared_distance,
        "geometry",
        "distance",
    ),
    _spec(
        "geometry.segment.compute.midpoint",
        "Construct segment midpoint",
        "Construct the exact midpoint of two rational endpoints.",
        PointPairRequest,
        GeometryPointResult,
        _midpoint,
        "geometry",
        "construction",
    ),
    _spec(
        "geometry.points.decide.collinear",
        "Decide collinearity",
        "Decide exact collinearity of three rational points.",
        PointTripleRequest,
        GeometryBooleanResult,
        _collinear,
        "geometry",
        "incidence",
    ),
    _spec(
        "geometry.points.decide.concyclic",
        "Decide concyclicity",
        "Decide whether four rational points lie on one circle.",
        PointQuadrupleRequest,
        GeometryBooleanResult,
        _concyclic,
        "geometry",
        "circle",
    ),
    _spec(
        "geometry.lines.decide.parallel",
        "Decide parallel lines",
        "Decide whether two exact lines are parallel.",
        LinePairRequest,
        GeometryBooleanResult,
        _line_predicate(lambda a, b: bool(a.is_parallel(b))),
        "geometry",
        "line",
    ),
    _spec(
        "geometry.lines.decide.perpendicular",
        "Decide perpendicular lines",
        "Decide whether two exact lines are perpendicular.",
        LinePairRequest,
        GeometryBooleanResult,
        _line_predicate(lambda a, b: bool(a.is_perpendicular(b))),
        "geometry",
        "line",
    ),
    _spec(
        "geometry.lines.compute.intersection",
        "Intersect exact lines",
        "Return the exact point, parallel status, or coincident status for two lines.",
        LinePairRequest,
        GeometryLineIntersectionResult,
        _line_intersection,
        "geometry",
        "intersection",
    ),
    _spec(
        "geometry.line.compute.projection",
        "Project point onto line",
        "Construct the exact orthogonal projection of a rational point onto a line.",
        PointLineRequest,
        GeometryPointResult,
        _projection,
        "geometry",
        "construction",
    ),
    _spec(
        "geometry.triangle.compute.orientation",
        "Compute triangle orientation",
        "Return clockwise, collinear, or counterclockwise orientation as -1, 0, or 1.",
        PointTripleRequest,
        GeometryOrientationResult,
        _orientation,
        "geometry",
        "orientation",
    ),
    _spec(
        "geometry.triangle.compute.centroid",
        "Construct triangle centroid",
        "Construct the exact centroid of three rational points.",
        PointTripleRequest,
        GeometryPointResult,
        _centroid,
        "geometry",
        "construction",
    ),
    _spec(
        "geometry.triangle.compute.circumcircle",
        "Construct triangle circumcircle",
        "Construct the exact circumcenter and squared radius of a nondegenerate rational triangle.",
        PointTripleRequest,
        GeometryCircleResult,
        _circumcircle,
        "geometry",
        "circle",
    ),
    _spec(
        "geometry.polygon.compute.signed_area",
        "Compute polygon signed area",
        "Compute exact oriented area of a simple rational polygon.",
        PolygonRequest,
        GeometryRationalResult,
        _signed_area,
        "geometry",
        "polygon",
    ),
    _spec(
        "geometry.points.compute.convex_hull",
        "Construct planar convex hull",
        "Construct the exact convex hull vertices of a finite rational point set.",
        PointSetRequest,
        GeometryPointSetResult,
        _convex_hull,
        "geometry",
        "convexity",
    ),
)


def _schema_with_result(result_model: type[ContractModel]) -> dict[str, Any]:
    result_schema = model_schema(result_model)
    definitions = result_schema.pop("$defs", {})
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "input_uri": {
                "type": "string",
                "pattern": r"^artifact://sha256/[0-9a-f]{64}$",
            },
            "result_uri": {
                "type": "string",
                "pattern": r"^artifact://sha256/[0-9a-f]{64}$",
            },
            "result": result_schema,
            "backend_version": {"type": "string"},
        },
        "required": ["input_uri", "result_uri", "result", "backend_version"],
        "additionalProperties": False,
    }
    if definitions:
        schema["$defs"] = definitions
    return schema


def install_geometry_capabilities(
    store: ArtifactStore,
    schemas: SchemaRegistry,
    artifacts: ArtifactService,
) -> tuple[GeometryAdapter, ...]:
    semantics_uri = store.register_descriptor(
        kind="semantics",
        name="jacobian.exact-rational-plane-geometry",
        version="1",
        definition={
            "description": "Euclidean plane geometry over exact rational coordinates",
            "degeneracy": "operation-specific and fail-closed",
            "assurance": "computed; no independent checker",
        },
    )
    request_models = {spec.request_model for spec in SPECS}
    input_schema_uris = {
        model: schemas.register_model(
            name=f"jacobian.geometry-input.{model.__name__}",
            version="1",
            model=model,
        )
        for model in request_models
    }
    result_schema_uris = {
        spec.capability_id: schemas.register(
            name=f"jacobian.geometry-result.{spec.capability_id}",
            version="1",
            schema=model_schema(spec.result_model),
        )
        for spec in SPECS
    }
    resources = GeometryResources(
        artifacts=artifacts,
        semantics_uri=semantics_uri,
        input_schema_uris=input_schema_uris,
        result_schema_uris=result_schema_uris,
    )
    return tuple(GeometryAdapter(spec, resources) for spec in SPECS)


class GeometryAdapter:
    def __init__(self, spec: GeometrySpec, resources: GeometryResources) -> None:
        self.spec = spec
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id=spec.capability_id,
            version="1",
            title=spec.title,
            description=spec.description,
            provider="jacobian.sympy",
            provider_runtime=known_provider_runtime(
                "jacobian.sympy",
                features=("exact-rational-geometry",),
            ),
            modes=(CapabilityMode.EXPLORE,),
            input_schema=model_schema(spec.request_model),
            output_schema=_schema_with_result(spec.result_model),
            tags=spec.tags,
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        try:
            validated = self.spec.request_model.model_validate(request.input)
        except ValidationError as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_GEOMETRY_REQUEST",
                    stage="geometry_input_validation",
                    message="Input does not satisfy the exact planar-geometry contract.",
                    hint="Use canonical rationals and inspect the operation's point/line schema.",
                )
            ) from exc
        started = time.monotonic()
        try:
            result = self.spec.compute(validated)
        except (TypeError, ValueError) as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="GEOMETRY_OPERATION_NOT_APPLICABLE",
                    stage="geometry_computation",
                    message=str(exc),
                    hint="Check the operation's nondegeneracy preconditions.",
                )
            ) from exc
        result_payload = result.model_dump(mode="json")
        input_uri = self.resources.artifacts.put(
            schema_uri=self.resources.input_schema_uris[self.spec.request_model],
            semantics_uri=self.resources.semantics_uri,
            payload=validated.model_dump(mode="json"),
            summary=f"{self.spec.capability_id} exact input",
        ).artifact_uri
        result_uri = self.resources.artifacts.put(
            schema_uri=self.resources.result_schema_uris[self.spec.capability_id],
            semantics_uri=self.resources.semantics_uri,
            payload=result_payload,
            parents=(input_uri,),
            summary=f"{self.spec.capability_id} exact result",
        ).artifact_uri
        output = GeometryOperationOutput(
            input_uri=input_uri,
            result_uri=result_uri,
            result=result_payload,
            backend_version=sympy.__version__,
        )
        return CapabilityResult(
            capability_id=self.spec.capability_id,
            capability_version="1",
            mode=request.mode,
            execution=Execution(
                status=ExecutionStatus.COMPLETED,
                runtime_ms=max(0, round((time.monotonic() - started) * 1000)),
            ),
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description="the complete supplied exact rational geometry input",
                parameters={"input_uri": input_uri},
                artifact_uri=input_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.COMPLETE,
                basis="exact symbolic computation covered the supplied finite input; not independently verified",
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            relationships=(
                CapabilityRelationship(
                    relation_id=self.spec.capability_id.replace(
                        ".compute.", ".relation."
                    ).replace(".decide.", ".relation."),
                    source_artifact_uris=(input_uri,),
                    target_artifact_uris=(result_uri,),
                ),
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis="exact SymPy rational geometry; no independent checker invoked",
            ),
            artifact_uris=(input_uri, result_uri),
        )
