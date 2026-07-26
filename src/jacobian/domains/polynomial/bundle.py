"""Installation bundle for exact rational polynomial operations."""

import sympy

from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.domains.polynomial.groebner import POLYNOMIAL_GROEBNER_CAPABILITY
from jacobian.domains.polynomial.invariants import (
    POLYNOMIAL_INVARIANT_CAPABILITIES,
)
from jacobian.operations import DomainBundle, DomainDiagnostics, DomainSemantics
from jacobian.provider_runtime import known_provider_runtime

POLYNOMIAL_BUNDLE = DomainBundle(
    domain_id="polynomial",
    schema_namespace="jacobian.polynomial",
    semantics=DomainSemantics(
        name="jacobian.sparse-rational-polynomial-operations",
        version="1",
        definition={
            "coefficient_field": "QQ",
            "wire_term_order": "descending lexicographic",
            "zero_terms": "omitted",
            "gcd_normalization": "monic with an exact Bezout identity",
            "resultant": "Sylvester determinant in the named variable",
            "discriminant": (
                "standard univariate convention: linear is 1; constant and zero are 0"
            ),
            "square_free_normalization": "separate coefficient and monic factors",
            "assurance": "computed; no independent checker",
        },
    ),
    provider_runtime=known_provider_runtime(
        "jacobian.sympy",
        features=("exact-rational-polynomial-operations",),
    ),
    backend_version=sympy.__version__,
    capabilities=(
        *POLYNOMIAL_INVARIANT_CAPABILITIES,
        POLYNOMIAL_GROEBNER_CAPABILITY,
    ),
    diagnostics=DomainDiagnostics(
        invalid_request=CapabilityDiagnostic(
            code="INVALID_POLYNOMIAL_REQUEST",
            stage="polynomial_input_validation",
            message="Input does not satisfy the bounded rational-polynomial contract.",
            hint="Use canonical sparse QQ polynomials and inspect the operation limits.",
        )
    ),
    scope_description="the complete supplied bounded rational-polynomial input",
    completeness_basis=(
        "exact symbolic computation covered the supplied finite input; "
        "not independently verified"
    ),
    assurance_basis="exact SymPy polynomial computation; no checker invoked",
)

__all__ = ["POLYNOMIAL_BUNDLE"]
