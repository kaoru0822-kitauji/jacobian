"""Installed finite-field operations over the authoritative native values."""

from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.domains.finite_fields.checkers import (
    FINITE_FIELD_EXACT_REPLAY_CHECKERS,
)
from jacobian.domains.finite_fields.contracts import (
    DirectionRankLedgerRequest,
    LinearMapRankRequest,
    OrbitDistributionRequest,
    ProjectiveLineRequest,
    RestrictScalarsRequest,
)
from jacobian.math.finite_fields import (
    Axis,
    DirectionRankLedger,
    FiniteDimensionalSubspace,
    FiniteFieldPresentation,
    FiniteLinearMap,
    OrbitDistribution,
    ProjectiveLine,
    ProjectivePoint,
    RankResult,
    direction_rank_ledger,
    linear_map_rank,
    orbit_distribution,
    projective_line,
    restrict_scalars,
)
from jacobian.operation_bindings import inline_operation
from jacobian.operation_ports import InputPort, OutputPort
from jacobian.operations import (
    SUPPORTED,
    DomainBundle,
    DomainDiagnostics,
    DomainSemantics,
    OperationSpec,
    PreflightResult,
    PreflightStatus,
)
from jacobian.provider_runtime import SYMPY_VERSION, known_provider_runtime
from jacobian.providers.flint_runtime import python_flint_finite_field_provider_runtime

_MAX_PROJECTIVE_POINTS = 4096


def _enumerate_projective_line(request: ProjectiveLineRequest) -> ProjectiveLine:
    return projective_line(request.presentation, request.axis)


def _projective_line_preflight(request: ProjectiveLineRequest) -> PreflightResult:
    count = (request.presentation.order ** len(request.axis.labels) - 1) // (
        request.presentation.order - 1
    )
    if count > _MAX_PROJECTIVE_POINTS:
        return PreflightResult(
            PreflightStatus.RESOURCE_LIMIT_EXCEEDED,
            f"projective line has {count} directions; limit is {_MAX_PROJECTIVE_POINTS}",
        )
    return SUPPORTED


def _restrict(request: RestrictScalarsRequest) -> FiniteLinearMap:
    return restrict_scalars(request.subspace, request.direction)


def _rank(request: LinearMapRankRequest) -> RankResult:
    return linear_map_rank(request.direction, request.linear_map)


def _ledger(request: DirectionRankLedgerRequest) -> DirectionRankLedger:
    return direction_rank_ledger(request.subspace, request.directions)


def _orbit_distribution(request: OrbitDistributionRequest) -> OrbitDistribution:
    return orbit_distribution(request.ledger)


def build_finite_field_bundle() -> DomainBundle:
    provider = known_provider_runtime(
        "jacobian.sympy",
        features=("finite-field-presentation", "projective-enumeration"),
    )
    flint_provider = python_flint_finite_field_provider_runtime()
    projective_line_operation = inline_operation(
        OperationSpec(
            operation_id="finite_field.projective_line.enumerate",
            version="1",
            request_type=ProjectiveLineRequest,
            result_type=ProjectiveLine,
            execute=_enumerate_projective_line,
            preflight=_projective_line_preflight,
            title="Enumerate an exact finite projective line",
            description="Return every normalized direction in deterministic order.",
            tags=("finite-field", "projective"),
        ),
        input_ports=(
            InputPort(
                name="presentation",
                value_type=FiniteFieldPresentation,
                request_field="presentation",
            ),
            InputPort(name="axis", value_type=Axis, request_field="axis"),
        ),
        output_ports=(OutputPort(name="directions", value_type=ProjectiveLine),),
    )
    restrict_operation = inline_operation(
        OperationSpec(
            operation_id="finite_field.restrict_scalars.compute",
            version="1",
            request_type=RestrictScalarsRequest,
            result_type=FiniteLinearMap,
            execute=_restrict,
            title="Restrict a finite-field matrix action to its prime field",
            description="Construct the exact prime-field map B -> B^T b.",
            tags=("finite-field", "linear-map", "restriction-of-scalars"),
        ),
        provider_runtime=flint_provider,
        input_ports=(
            InputPort(
                name="subspace",
                value_type=FiniteDimensionalSubspace,
                request_field="subspace",
            ),
            InputPort(
                name="direction",
                value_type=ProjectivePoint,
                request_field="direction",
            ),
        ),
        output_ports=(OutputPort(name="linear_map", value_type=FiniteLinearMap),),
    )
    rank_operation = inline_operation(
        OperationSpec(
            operation_id="finite_field.linear_map.rank.compute",
            version="1",
            request_type=LinearMapRankRequest,
            result_type=RankResult,
            execute=_rank,
            title="Compute finite linear-map rank over the prime field",
            description="Return the exact rank bound to its direction and map.",
            tags=("finite-field", "linear-map", "rank", "exact"),
        ),
        provider_runtime=flint_provider,
        input_ports=(
            InputPort(
                name="direction",
                value_type=ProjectivePoint,
                request_field="direction",
            ),
            InputPort(
                name="linear_map",
                value_type=FiniteLinearMap,
                request_field="linear_map",
            ),
        ),
        output_ports=(OutputPort(name="rank", value_type=RankResult),),
    )
    ledger_operation = inline_operation(
        OperationSpec(
            operation_id="finite_field.direction_rank_ledger.compute",
            version="1",
            request_type=DirectionRankLedgerRequest,
            result_type=DirectionRankLedger,
            execute=_ledger,
            title="Compute ranks for a complete finite projective line",
            description="Return every direction with its restricted map and rank.",
            tags=("finite-field", "rank"),
        ),
        provider_runtime=flint_provider,
        input_ports=(
            InputPort(
                name="subspace",
                value_type=FiniteDimensionalSubspace,
                request_field="subspace",
            ),
            InputPort(
                name="directions",
                value_type=ProjectiveLine,
                request_field="directions",
            ),
        ),
        output_ports=(OutputPort(name="ledger", value_type=DirectionRankLedger),),
    )
    orbit_operation = inline_operation(
        OperationSpec(
            operation_id="finite_field.orbit_distribution.compute",
            version="1",
            request_type=OrbitDistributionRequest,
            result_type=OrbitDistribution,
            execute=_orbit_distribution,
            title="Aggregate a complete direction-rank ledger",
            description="Return exact orbit-size counts bound to the full ledger.",
            tags=("finite-field", "orbit"),
        ),
        input_ports=(
            InputPort(
                name="ledger",
                value_type=DirectionRankLedger,
                request_field="ledger",
            ),
        ),
        output_ports=(OutputPort(name="distribution", value_type=OrbitDistribution),),
    )
    return DomainBundle(
        domain_id="finite_fields",
        schema_namespace="jacobian.finite-fields",
        semantics=DomainSemantics(
            name="jacobian.exact-finite-field-linear-algebra",
            version="1",
            definition={
                "field_identity": "exact modulus, generator, and ordered power basis",
                "linear_map": "explicit restriction of scalars to the prime field",
            },
        ),
        provider_runtime=provider,
        backend_version=f"sympy-{SYMPY_VERSION}",
        capabilities=(
            projective_line_operation,
            restrict_operation,
            rank_operation,
            ledger_operation,
            orbit_operation,
        ),
        checker_declarations=FINITE_FIELD_EXACT_REPLAY_CHECKERS,
        diagnostics=DomainDiagnostics(
            invalid_request=CapabilityDiagnostic(
                code="INVALID_FINITE_FIELD_REQUEST",
                stage="finite_field_input_validation",
                message="Input does not satisfy the exact finite-field contract.",
                hint="Use values with identical presentations, axes, and bases.",
            )
        ),
    )


__all__ = ["build_finite_field_bundle"]
