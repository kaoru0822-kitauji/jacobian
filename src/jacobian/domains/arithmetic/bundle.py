"""Installation bundle for exact arithmetic.

The arithmetic domain owns integer absolute value, sign, decimal digit
sum/count, base expansion, integer nth root, and rational arithmetic/order.
Number-theory capabilities (gcd, lcm, divisors, primes, modular arithmetic,
integer predicates) are owned by the number-theory domain (p3) and are
intentionally excluded from this bundle.
"""

from __future__ import annotations

import platform

from jacobian.contracts.arithmetic import (
    MAX_REAL_QUADRATIC_DIGITS,
    MAX_REAL_QUADRATIC_RADICAND,
)
from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.domains.arithmetic.checkers import ARITHMETIC_EXACT_REPLAY_CHECKERS
from jacobian.domains.arithmetic.integers import INTEGER_CAPABILITIES
from jacobian.domains.arithmetic.quadratic import REAL_QUADRATIC_CAPABILITIES
from jacobian.domains.arithmetic.rationals import RATIONAL_CAPABILITIES
from jacobian.operations import (
    DomainBundle,
    DomainDiagnostics,
    DomainSemantics,
)
from jacobian.provider_runtime import SYMPY_VERSION, known_provider_runtime


def build_arithmetic_bundle() -> DomainBundle:
    """Build this domain-owned installation unit explicitly."""
    return DomainBundle(
        domain_id="arithmetic",
        schema_namespace="jacobian.arithmetic",
        semantics=DomainSemantics(
            name="jacobian.exact-arithmetic",
            version="2",
            definition={
                "description": (
                    "exact integer absolute value, sign, decimal digit sum/count, "
                    "base expansion, integer nth root, rational arithmetic/order, "
                    "and bounded same-radicand real-quadratic order"
                ),
                "integer_encoding": "canonical decimal string",
                "rational_encoding": "canonical reduced num/den with positive denominator",
                "real_quadratic_encoding": (
                    "a+b*sqrt(d), with shared positive square-free d"
                ),
                "arithmetic": "exact via stdlib and maintained SymPy APIs",
                "assurance": (
                    "computed; real-quadratic order supports operator-authorized "
                    "independent standard-library replay"
                ),
            },
        ),
        provider_runtime=known_provider_runtime(
            "jacobian.sympy",
            features=(
                "exact-integer-arithmetic",
                "exact-rational-arithmetic",
                "exact-real-quadratic-order",
            ),
            configuration={
                "sympy_version": SYMPY_VERSION,
                "real_quadratic_max_digits": MAX_REAL_QUADRATIC_DIGITS,
                "real_quadratic_max_radicand": MAX_REAL_QUADRATIC_RADICAND,
            },
        ),
        backend_version=f"python-{platform.python_version()};sympy-{SYMPY_VERSION}",
        capabilities=(
            *INTEGER_CAPABILITIES,
            *RATIONAL_CAPABILITIES,
            *REAL_QUADRATIC_CAPABILITIES,
        ),
        diagnostics=DomainDiagnostics(
            invalid_request=CapabilityDiagnostic(
                code="INVALID_ARITHMETIC_REQUEST",
                stage="arithmetic_input_validation",
                message="Input does not satisfy the exact arithmetic contract.",
                hint=(
                    "Use canonical integer/rational strings and bounded values; "
                    "inspect the operation's request schema."
                ),
            )
        ),
        scope_description="the complete supplied bounded exact arithmetic input",
        completeness_basis=(
            "deterministic exact computation covered the supplied input; "
            "not independently verified"
        ),
        assurance_basis=(
            "deterministic exact arithmetic from the pinned stdlib/SymPy runtime; "
            "independent verification requires an explicit domain-owned verifier "
            "invocation where declared"
        ),
        checker_declarations=ARITHMETIC_EXACT_REPLAY_CHECKERS,
    )
