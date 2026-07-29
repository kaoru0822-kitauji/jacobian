from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityRequest,
)
from jacobian.contracts.geometry import (
    LinePairRequest,
    PointLineRequest,
    PointPairRequest,
    PointQuadrupleRequest,
    PointSetRequest,
    PointTripleRequest,
    PolygonRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.domains.geometry import GEOMETRY_BUNDLE

ZERO = {"num": "0", "den": "1"}
ONE = {"num": "1", "den": "1"}
TWO = {"num": "2", "den": "1"}
P0 = {"x": ZERO, "y": ZERO}
PX = {"x": TWO, "y": ZERO}
PY = {"x": ZERO, "y": TWO}
PXY = {"x": TWO, "y": TWO}


def test_segment_midpoint_example_is_directly_invocable(kernel) -> None:
    descriptor = next(
        descriptor
        for descriptor in kernel.capabilities.catalog().capabilities
        if descriptor.capability_id == "geometry.segment.compute.midpoint"
    )
    example = descriptor.invocation_examples[0]

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id=descriptor.capability_id,
            mode=example.mode,
            input=example.input,
        )
    )

    assert example.input == {
        "first": {"x": ZERO, "y": ZERO},
        "second": {"x": ONE, "y": ZERO},
    }
    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["result"] == {
        "point": {
            "x": {"num": "1", "den": "2"},
            "y": ZERO,
        }
    }


def test_geometry_capabilities_are_distinct_and_every_contract_completes(
    kernel,
) -> None:
    line_x = {"first": P0, "second": PX}
    line_y = {"first": P0, "second": PY}
    payloads = {
        PointPairRequest: {"first": P0, "second": PXY},
        PointTripleRequest: {"first": P0, "second": PX, "third": PY},
        PointQuadrupleRequest: {
            "first": P0,
            "second": PX,
            "third": PY,
            "fourth": PXY,
        },
        LinePairRequest: {"first_line": line_x, "second_line": line_y},
        PointLineRequest: {"point": PXY, "line": line_x},
        PolygonRequest: {"points": [P0, PX, PY]},
        PointSetRequest: {"points": [P0, PX, PY, PXY]},
    }
    ids = [operation.capability_id for operation in GEOMETRY_BUNDLE.capabilities]

    assert len(ids) == 13
    assert len(ids) == len(set(ids))
    for operation in GEOMETRY_BUNDLE.capabilities:
        result = kernel.capabilities.invoke(
            CapabilityRequest(
                capability_id=operation.capability_id,
                input=payloads[operation.request_model],
            )
        )
        assert result.execution.status is ExecutionStatus.COMPLETED, (
            operation.capability_id,
            result.diagnostics,
        )
        assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
        assert len(result.artifact_uris) == 2


def test_geometry_exact_outputs_are_inline_and_materialized(kernel) -> None:

    distance = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="geometry.points.compute.squared_distance",
            input={"first": P0, "second": PXY},
        )
    )
    circle = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="geometry.triangle.compute.circumcircle",
            input={"first": P0, "second": PX, "third": PY},
        )
    )

    assert distance.output["result"] == {"value": {"num": "8", "den": "1"}}
    assert circle.output["result"] == {
        "center": {"x": ONE, "y": ONE},
        "radius_squared": {"num": "2", "den": "1"},
    }
    assert (
        kernel.store.get(distance.output["result_uri"]).payload
        == distance.output["result"]
    )


def test_convex_hull_returns_segment_endpoints_for_two_points(
    kernel,
) -> None:

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="geometry.points.compute.convex_hull",
            input={"points": [PXY, P0]},
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["result"] == {"points": [P0, PXY]}


def test_convex_hull_returns_extreme_endpoints_for_collinear_points(
    kernel,
) -> None:
    middle = {"x": ONE, "y": ONE}

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="geometry.points.compute.convex_hull",
            input={"points": [middle, PXY, P0]},
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["result"] == {"points": [P0, PXY]}


def test_degenerate_geometry_fails_before_artifact_writes(kernel) -> None:

    invalid_line = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="geometry.lines.compute.intersection",
            input={
                "first_line": {"first": P0, "second": P0},
                "second_line": {"first": P0, "second": PX},
            },
        )
    )
    collinear_circle = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="geometry.triangle.compute.circumcircle",
            input={
                "first": P0,
                "second": {"x": ONE, "y": ONE},
                "third": PXY,
            },
        )
    )

    assert invalid_line.execution.status is ExecutionStatus.ERROR
    assert invalid_line.diagnostics[0].code == "INVALID_GEOMETRY_REQUEST"
    assert collinear_circle.execution.status is ExecutionStatus.ERROR
    assert collinear_circle.diagnostics[0].code == "GEOMETRY_OPERATION_NOT_APPLICABLE"
    assert invalid_line.artifact_uris == ()
    assert collinear_circle.artifact_uris == ()
