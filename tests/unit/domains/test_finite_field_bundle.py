from jacobian.domains.finite_fields import build_finite_field_bundle
from jacobian.domains.finite_fields.contracts import ProjectiveLineRequest
from jacobian.math.finite_fields import (
    Axis,
    CollisionCertificate,
    DirectionRankLedger,
    FiberPartition,
    FiniteDimensionalSubspace,
    FiniteFieldPresentation,
    FiniteLinearMap,
    FiniteMapTable,
    FinitePolynomialMap,
    OrbitDistribution,
    PermutationCertificate,
    ProjectiveLine,
    ProjectivePoint,
    RankResult,
)
from jacobian.operation_execution import execute_operation
from jacobian.operations import NonConclusion


def test_bundle_declares_atomic_port_bound_operations() -> None:
    bundle = build_finite_field_bundle()

    assert bundle.capability_ids == (
        "finite_field.projective_line.enumerate",
        "finite_field.restrict_scalars.compute",
        "finite_field.linear_map.rank.compute",
        "finite_field.direction_rank_ledger.compute",
        "finite_field.orbit_distribution.compute",
        "finite_field.polynomial_map.table.compute",
        "finite_field.polynomial_map.fibers.compute",
        "finite_field.polynomial_map.collision.compute",
        "finite_field.polynomial_map.permutation.compute",
    )
    (
        projective,
        restrict_operation,
        rank_operation,
        ledger,
        orbit,
        table,
        fibers,
        collision,
        permutation,
    ) = bundle.capabilities
    assert projective.output_ports[0].value_type is ProjectiveLine
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
    assert tuple(port.value_type for port in ledger.input_ports) == (
        FiniteDimensionalSubspace,
        ProjectiveLine,
    )
    assert ledger.output_ports[0].value_type is DirectionRankLedger
    assert orbit.input_ports[0].value_type is DirectionRankLedger
    assert orbit.output_ports[0].value_type is OrbitDistribution
    assert table.input_ports[0].value_type is FinitePolynomialMap
    assert table.output_ports[0].value_type is FiniteMapTable
    assert fibers.input_ports[0].value_type is FiniteMapTable
    assert fibers.output_ports[0].value_type is FiberPartition
    assert collision.output_ports[0].value_type is CollisionCertificate
    assert permutation.output_ports[0].value_type is PermutationCertificate


def test_projective_enumeration_refuses_large_output_before_allocation() -> None:
    operation = build_finite_field_bundle().capabilities[0]
    request = ProjectiveLineRequest(
        presentation=FiniteFieldPresentation(
            characteristic=2,
            modulus_coefficients=(1, 1, 1),
        ),
        axis=Axis(name="large", labels=tuple(f"x{index}" for index in range(7))),
    )

    terminal = execute_operation(operation.spec, request)

    assert isinstance(terminal, NonConclusion)
    assert terminal.diagnostic.code == "RESOURCE_LIMIT_EXCEEDED"
