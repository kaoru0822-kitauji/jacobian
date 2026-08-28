"""Budgeted declarations for complete factorization-derived operations."""

from __future__ import annotations

from collections.abc import Callable

from jacobian._models import StrictModel
from jacobian.catalog._examples import example
from jacobian.catalog.models import MathTool, OperationExample
from jacobian.math.number_theory._certification_models import (
    CertifiedFactorizationRequest,
    CertifiedFactorizationResult,
    PrimalityCertificateRequest,
    PrimalityCertificateResult,
)
from jacobian.math.number_theory._direct_factorization_models import (
    DivisorListResult,
    FactorizationRequest,
    PrimeFactorizationResult,
)
from jacobian.math.number_theory._factorization_kernels import (
    compute_pratt_certificate,
    enumerate_divisors,
    factorize_certified,
    factorize_primes,
)


def _operation[RequestT: StrictModel, ResultT: StrictModel](
    *,
    operation_id: str,
    title: str,
    description: str,
    request_model: type[RequestT],
    result_model: type[ResultT],
    implementation: Callable[[RequestT], ResultT],
    tags: tuple[str, ...],
    discovery_terms: tuple[str, ...] = (),
    examples: tuple[OperationExample, ...] = (),
) -> MathTool[RequestT, ResultT]:
    return MathTool(
        operation_id=operation_id,
        title=title,
        description=description,
        request_type=request_model,
        result_type=result_model,
        run=implementation,
        tags=tags,
        discovery_terms=discovery_terms,
        examples=examples,
    )


FACTORIZATION_OPERATIONS = (
    _operation(
        operation_id="integer.factor.certified_compute",
        title="Compute a certified integer factorization",
        description=(
            "Factor one bounded 30-digit integer (~100 bits) in an isolated "
            "subexponential worker (Pollard rho, Pollard p-1, ECM via "
            "sympy.ntheory.factorint), returning a complete prime-power "
            "factorization with per-factor Pratt certificates, or UNKNOWN if "
            "the worker cannot establish a complete result within its envelope."
        ),
        request_model=CertifiedFactorizationRequest,
        result_model=CertifiedFactorizationResult,
        implementation=factorize_certified,
        tags=("number-theory", "factorization", "bounded", "prime", "certificate"),
        examples=(
            example(
                "semiprime_10403",
                "Factor 10403 with subexponential methods and per-factor Pratt "
                "certificates. The input must be a canonical integer of at "
                "least 2 and at most 30 digits.",
                {"value": "10403"},
            ),
        ),
    ),
    _operation(
        operation_id="integer.primality.certificate.compute",
        title="Compute a Pratt primality certificate",
        description="Produce a Pratt primality certificate for one declared prime, or report COMPOSITE when the candidate is not prime.",
        request_model=PrimalityCertificateRequest,
        result_model=PrimalityCertificateResult,
        implementation=compute_pratt_certificate,
        tags=("number-theory", "primality", "certificate"),
        examples=(
            example(
                "pratt_101",
                "Produce a Pratt certificate for the prime 101. The input must "
                "be a canonical integer of at least 2 and at most 30 digits.",
                {"value": "101"},
            ),
        ),
    ),
    _operation(
        operation_id="integer.compute.divisors",
        title="Enumerate positive divisors",
        description=(
            "Enumerate every positive divisor exactly, including the input's "
            "absolute value, or return UNKNOWN when the bounded factorization "
            "worker cannot establish the enumeration."
        ),
        request_model=FactorizationRequest,
        result_model=DivisorListResult,
        implementation=enumerate_divisors,
        tags=("number-theory", "enumeration"),
        discovery_terms=("positive divisors",),
        examples=(
            example(
                "divisors_12", "Enumerate the positive divisors of 12.", {"value": "12"}
            ),
        ),
    ),
    _operation(
        operation_id="integer.compute.prime_factorization",
        title="Factor an integer",
        description=(
            "Factor an integer into prime powers and return the complete "
            "prime-power factorization, or UNKNOWN when the bounded worker "
            "cannot establish it."
        ),
        request_model=FactorizationRequest,
        result_model=PrimeFactorizationResult,
        implementation=factorize_primes,
        tags=("number-theory", "factorization"),
        examples=(
            example(
                "prime_factorization_360",
                "Factor 360 into prime powers.",
                {"value": "360"},
            ),
        ),
    ),
)
