from jacobian.domains.finite_fields import build_finite_field_bundle
from jacobian.math.finite_fields import (
    FiniteDimensionalSubspace,
    FiniteLinearMap,
    ProjectivePoint,
    RankResult,
)


def test_bundle_declares_two_atomic_port_bound_operations() -> None:
    bundle = build_finite_field_bundle()

    assert bundle.capability_ids == (
        "finite_field.restrict_scalars.compute",
        "finite_field.linear_map.rank",
    )
    restrict_operation, rank_operation = bundle.capabilities
    assert tuple(port.value_type for port in restrict_operation.input_ports) == (
        FiniteDimensionalSubspace,
        ProjectivePoint,
    )
    assert restrict_operation.output_ports[0].value_type is FiniteLinearMap
    assert tuple(port.value_type for port in rank_operation.input_ports) == (
        ProjectivePoint,
        FiniteLinearMap,
    )
    assert rank_operation.output_ports[0].value_type is RankResult
