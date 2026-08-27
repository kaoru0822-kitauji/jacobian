"""Domain-owned real algebra operations."""

from __future__ import annotations

from fractions import Fraction

from pydantic_core import PydanticCustomError

from jacobian._exact import CanonicalRational, require_bounded_rational
from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.polynomials.real_algebra import root_count, sturm_chain
from jacobian.math.polynomials.real_algebra._models import (
    PolynomialTerm,
    RootCountRequest,
    RootCountResult,
    SturmChainRequest,
    SturmChainResult,
    UnivariatePolynomial,
)
from jacobian.math.polynomials.real_algebra._strict_sublevel import (
    compute_strict_sublevel_payload,
)
from jacobian.math.polynomials.real_algebra._strict_sublevel_models import (
    MAX_STRICT_SUBLEVEL_BOUNDARY_HEIGHT_DIGITS,
    MAX_STRICT_SUBLEVEL_DEGREE,
    MAX_STRICT_SUBLEVEL_INPUT_DIGITS,
    MAX_STRICT_SUBLEVEL_ISOLATION_WORK,
    MAX_STRICT_SUBLEVEL_TERMS,
    StrictSublevelMeasureRequest,
    StrictSublevelMeasureResult,
    _level_polynomial_height_digits,
    _polynomial_degree,
    _validation_error,
)
from jacobian.math.polynomials.values import require_polynomial_budget


def _admit_strict_sublevel(request: StrictSublevelMeasureRequest) -> None:
    if len(request.polynomial.variables) != 1:
        raise _validation_error("variable_count", "strict sublevel measure requires one polynomial variable")
    require_polynomial_budget(
        request.polynomial,
        maximum_terms=MAX_STRICT_SUBLEVEL_TERMS,
        maximum_exponent=MAX_STRICT_SUBLEVEL_DEGREE,
        maximum_coefficient_digits=MAX_STRICT_SUBLEVEL_INPUT_DIGITS,
        label="strict sublevel polynomial",
    )
    for value, label in (
        (request.threshold, "strict sublevel threshold"),
        (request.lower, "strict sublevel lower scope endpoint"),
        (request.upper, "strict sublevel upper scope endpoint"),
    ):
        require_bounded_rational(value, max_digits=MAX_STRICT_SUBLEVEL_INPUT_DIGITS, label=label)
    if request.threshold.as_fraction() < 0:
        raise _validation_error("negative_threshold", "strict sublevel threshold must be nonnegative")
    if request.lower.as_fraction() > request.upper.as_fraction():
        raise _validation_error("scope_order", "strict sublevel lower endpoint must not exceed upper")
    if request.threshold.as_fraction() == 0 or _polynomial_degree(request.polynomial) == 0 or request.lower == request.upper:
        return
    boundary_heights = []
    for subtract_threshold, label in ((True, "f-threshold"), (False, "f+threshold")):
        height_digits = _level_polynomial_height_digits(
            request.polynomial,
            request.threshold,
            subtract_threshold=subtract_threshold,
        )
        if height_digits > MAX_STRICT_SUBLEVEL_BOUNDARY_HEIGHT_DIGITS:
            raise _validation_error(
                "boundary_height",
                f"primitive {label} height exceeds the {MAX_STRICT_SUBLEVEL_BOUNDARY_HEIGHT_DIGITS}-digit root-isolation bound",
            )
        boundary_heights.append(height_digits)
    degree = _polynomial_degree(request.polynomial)
    isolation_work = degree**5 * sum(boundary_heights)
    if isolation_work > MAX_STRICT_SUBLEVEL_ISOLATION_WORK:
        raise _validation_error(
            "isolation_work",
            "strict sublevel exact-root isolation exceeds the work bound "
            f"(degree^5*level-height-sum={isolation_work} > {MAX_STRICT_SUBLEVEL_ISOLATION_WORK}); reduce degree or coefficient/threshold height",
        )


def _run_admission(request: StrictSublevelMeasureRequest) -> None:
    try:
        _admit_strict_sublevel(request)
    except OperationDomainValidationError:
        raise
    except PydanticCustomError as exc:
        raise OperationDomainValidationError(location=(), code=exc.type, message=exc.message()) from exc
    except ValueError as exc:
        raise OperationDomainValidationError(location=(), code="polynomial.strict_sublevel_admission", message=str(exc)) from exc


def _poly_to_terms(poly: UnivariatePolynomial) -> list[tuple[Fraction, int]]:
    return [(t.coefficient.as_fraction(), t.exponent) for t in poly.terms]


def _terms_to_poly(terms: list[tuple[Fraction, int]]) -> UnivariatePolynomial:
    return UnivariatePolynomial(
        terms=tuple(
            PolynomialTerm(
                coefficient=CanonicalRational.from_fraction(coeff),
                exponent=exp,
            )
            for coeff, exp in terms
            if coeff != 0
        )
    )


def compute_sturm_chain(request: SturmChainRequest) -> SturmChainResult:
    poly = request.polynomial
    terms = _poly_to_terms(poly)
    chain = sturm_chain(terms)
    degree = max(t.exponent for t in poly.terms)
    return SturmChainResult(
        chain=tuple(_terms_to_poly(c) for c in chain),
        degree=degree,
    )


def compute_root_count(request: RootCountRequest) -> RootCountResult:
    terms = _poly_to_terms(request.polynomial)
    lower = request.lower.as_fraction()
    upper = request.upper.as_fraction()
    count = root_count(terms, lower, upper)
    return RootCountResult(
        source_polynomial=request.polynomial,
        root_count=count,
        lower=request.lower,
        upper=request.upper,
    )


def compute_strict_sublevel_measure(
    request: StrictSublevelMeasureRequest,
) -> StrictSublevelMeasureResult:
    _run_admission(request)
    payload = compute_strict_sublevel_payload(request)
    return StrictSublevelMeasureResult._from_kernel(
        request,
        components=payload.components,
        measure=payload.measure,
    )
