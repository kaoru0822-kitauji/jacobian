"""Domain adapter for universal-algebra operations."""

from __future__ import annotations

from jacobian.canonical import (
    CanonicalizationError,
    CanonicalLimits,
    encode_strict_json,
)
from jacobian.math.universal_algebra._models import (
    _HOMOMORPHISM_RESULT_RESERVE_BYTES,
    MAX_ENUMERATION_WORK,
    CongruenceRequest,
    CongruenceResult,
    EquationProfileRequest,
    EquationProfileResult,
    EvaluateRequest,
    EvaluateResult,
    HomomorphismProfileRequest,
    HomomorphismProfileResult,
    QuotientRequest,
    SubalgebraRequest,
    SubalgebraResult,
    _congruence_work,
    _require_homomorphism_output_headroom,
)
from jacobian.math.universal_algebra.operations import (
    _equation_profile_unchecked,
    _evaluate_term_unchecked,
    congruence_check,
    generated_subalgebra,
    homomorphism_profile,
    quotient,
)
from jacobian.math.universal_algebra.values import (
    FiniteAlgebraHomomorphism,
    UniversalAlgebraAdmissionError,
    require_term_for_algebra,
)

__all__ = [
    "compute_congruence",
    "compute_equation_profile",
    "compute_evaluate",
    "compute_generated_subalgebra",
    "compute_homomorphism_profile",
    "compute_quotient",
]


def _admit_evaluate(request: EvaluateRequest) -> None:
    try:
        require_term_for_algebra(request.term, request.algebra)
    except UniversalAlgebraAdmissionError as exc:
        raise ValueError(str(exc)) from None
    if len(request.assignment) != request.term.variable_count:
        raise ValueError("assignment must cover exactly the referenced variables")
    size = len(request.algebra.carrier)
    if any(not 0 <= value < size for value in request.assignment):
        raise ValueError("assignment value out of carrier range")


def _admit_equation_profile(request: EquationProfileRequest) -> None:
    for term in (request.left, request.right):
        try:
            require_term_for_algebra(term, request.algebra)
        except UniversalAlgebraAdmissionError as exc:
            raise ValueError(str(exc)) from None
    if (
        max(request.left.variable_count, request.right.variable_count)
        > request.variable_count
    ):
        raise ValueError("variable_count must cover every referenced variable")
    if len(request.algebra.carrier) ** request.variable_count > MAX_ENUMERATION_WORK:
        raise ValueError("equation profile exceeds the assignment work budget")


def _admit_subalgebra(request: SubalgebraRequest) -> None:
    size = len(request.algebra.carrier)
    if any(not 0 <= generator < size for generator in request.generators):
        raise ValueError("generator out of carrier range")
    work = sum(size**symbol.arity for symbol in request.algebra.operations) * size
    if work > MAX_ENUMERATION_WORK:
        raise ValueError("subalgebra closure exceeds the operation work budget")


def _admit_homomorphism(request: HomomorphismProfileRequest) -> None:
    preservation_cells = sum(len(table) for table in request.carrier_map.source.tables)
    if preservation_cells > MAX_ENUMERATION_WORK:
        raise ValueError("homomorphism operation work exceeds the enumeration budget")
    _require_homomorphism_output_headroom(request.carrier_map)


def _admit_partition(request: CongruenceRequest | QuotientRequest) -> None:
    congruence_work = _congruence_work(request.algebra)
    if congruence_work > MAX_ENUMERATION_WORK:
        raise ValueError("congruence check exceeds the operation work budget")
    if not isinstance(request, QuotientRequest):
        return
    quotient_size = len(request.partition)
    quotient_table_cells = sum(
        quotient_size**operation.arity for operation in request.algebra.operations
    )
    quotient_work = (
        congruence_work
        + sum(len(table) for table in request.algebra.tables)
        + quotient_table_cells
    )
    if quotient_work > MAX_ENUMERATION_WORK:
        raise ValueError("quotient construction exceeds the operation work budget")
    try:
        source_bytes = len(encode_strict_json(request.algebra.model_dump(mode="json")))
        operation_bytes = len(
            encode_strict_json(
                [
                    operation.model_dump(mode="json")
                    for operation in request.algebra.operations
                ]
            )
        )
        quotient_carrier_bytes = sum(
            len(encode_strict_json(f"B{index}")) + 1 for index in range(quotient_size)
        )
    except CanonicalizationError as exc:
        raise ValueError("quotient source exceeds the canonical output limit") from exc
    quotient_index_bytes = len(str(quotient_size - 1)) + 1
    predicted_bytes = (
        source_bytes
        + operation_bytes
        + quotient_carrier_bytes
        + quotient_table_cells * quotient_index_bytes
        + len(request.algebra.carrier) * quotient_index_bytes
        + _HOMOMORPHISM_RESULT_RESERVE_BYTES
    )
    if predicted_bytes > CanonicalLimits().max_output_bytes:
        raise ValueError(
            "canonical quotient homomorphism would exceed the output limit"
        )


def compute_evaluate(request: EvaluateRequest) -> EvaluateResult:
    _admit_evaluate(request)
    assignment = dict(enumerate(request.assignment))
    value = _evaluate_term_unchecked(request.algebra, request.term, assignment)
    return EvaluateResult(value=value)


def compute_equation_profile(request: EquationProfileRequest) -> EquationProfileResult:
    _admit_equation_profile(request)
    result = _equation_profile_unchecked(
        request.algebra, request.left, request.right, request.variable_count
    )
    return result


def compute_generated_subalgebra(request: SubalgebraRequest) -> SubalgebraResult:
    _admit_subalgebra(request)
    return generated_subalgebra(request.algebra, request.generators)


def compute_homomorphism_profile(
    request: HomomorphismProfileRequest,
) -> HomomorphismProfileResult:
    _admit_homomorphism(request)
    return homomorphism_profile(request.carrier_map)


def compute_congruence(request: CongruenceRequest) -> CongruenceResult:
    _admit_partition(request)
    return congruence_check(request.algebra, request.partition)


def compute_quotient(request: QuotientRequest) -> FiniteAlgebraHomomorphism:
    _admit_partition(request)
    return quotient(request.algebra, request.partition)
