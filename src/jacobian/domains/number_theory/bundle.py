"""Installation bundle for exact SymPy-backed number-theory capabilities."""

from __future__ import annotations

import platform

from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.domains.number_theory.derived import DERIVED_NUMBER_THEORY_CAPABILITIES
from jacobian.domains.number_theory.divisibility import DIVISIBILITY_CAPABILITIES
from jacobian.domains.number_theory.modular import MODULAR_CAPABILITIES
from jacobian.domains.number_theory.primes import PRIME_CAPABILITIES
from jacobian.operations import (
    DomainBundle,
    DomainDiagnostics,
    DomainSemantics,
)
from jacobian.provider_runtime import SYMPY_VERSION, known_provider_runtime

NUMBER_THEORY_BUNDLE = DomainBundle(
    domain_id="number_theory",
    schema_namespace="jacobian.number-theory",
    semantics=DomainSemantics(
        name="jacobian.exact-integer-number-theory",
        version="1",
        definition={
            "description": (
                "Exact integer divisibility, primes, arithmetic functions, "
                "and modular arithmetic over bounded inputs"
            ),
            "integer_encoding": "canonical decimal string",
            "assurance": "computed; no independent checker",
        },
    ),
    provider_runtime=known_provider_runtime(
        "jacobian.sympy",
        features=("exact-integer-number-theory",),
    ),
    backend_version=f"python-{platform.python_version()};sympy-{SYMPY_VERSION}",
    capabilities=(
        *DIVISIBILITY_CAPABILITIES,
        *PRIME_CAPABILITIES,
        *MODULAR_CAPABILITIES,
        *DERIVED_NUMBER_THEORY_CAPABILITIES,
    ),
    diagnostics=DomainDiagnostics(
        invalid_request=CapabilityDiagnostic(
            code="INVALID_NUMBER_THEORY_REQUEST",
            stage="number_theory_input_validation",
            message="Input does not satisfy the exact number-theory contract.",
            hint=(
                "Use canonical integer strings and bounded non-negative "
                "integers within each operation's limits."
            ),
        )
    ),
    scope_description=("the complete supplied bounded exact number-theory input"),
    completeness_basis=(
        "deterministic exact computation covered the declared input; "
        "not independently verified"
    ),
    assurance_basis=(
        "deterministic exact arithmetic from the pinned SymPy runtime; "
        "no independent checker invoked"
    ),
)
