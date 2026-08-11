"""Installed finite-field operations over the authoritative native values."""

from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.domains.finite_fields.contracts import (
    LinearMapRankRequest,
    RestrictScalarsRequest,
)
from jacobian.math.finite_fields import (
    FiniteDimensionalSubspace,
    FiniteLinearMap,
    ProjectivePoint,
    RankResult,
    linear_map_rank,
    restrict_scalars,
)
from jacobian.operation_bindings import inline_operation
from jacobian.operation_ports import InputPort, OutputPort
from jacobian.operations import (
    DomainBundle,
    DomainDiagnostics,
    DomainSemantics,
    OperationSpec,
)
from jacobian.provider_runtime import PYTHON_FLINT_VERSION
from jacobian.providers.flint_runtime import python_flint_finite_field_provider_runtime


def _restrict(request: RestrictScalarsRequest) -> FiniteLinearMap:
    return restrict_scalars(request.subspace, request.direction)


def _rank(request: LinearMapRankRequest) -> RankResult:
    return linear_map_rank(request.direction, request.linear_map)


def build_finite_field_bundle() -> DomainBundle:
    provider = python_flint_finite_field_provider_runtime()
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
        provider_runtime=provider,
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
        output_ports=(
            OutputPort(name="linear_map", value_type=FiniteLinearMap),
        ),
    )
    rank_operation = inline_operation(
        OperationSpec(
            operation_id="finite_field.linear_map.rank",
            version="1",
            request_type=LinearMapRankRequest,
            result_type=RankResult,
            execute=_rank,
            title="Compute finite linear-map rank over the prime field",
            description="Return the exact rank bound to its direction and map.",
            tags=("finite-field", "linear-map", "rank", "exact"),
        ),
        provider_runtime=provider,
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
        backend_version=f"python-flint-{PYTHON_FLINT_VERSION}",
        capabilities=(restrict_operation, rank_operation),
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
