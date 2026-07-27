"""Installation bundle for exact combinatorics capabilities."""

from __future__ import annotations

import platform

import sympy

from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.domains.combinatorics.counting import COUNTING_CAPABILITIES
from jacobian.domains.combinatorics.partitions import PARTITION_CAPABILITIES
from jacobian.domains.combinatorics.recurrence import RECURRENCE_CAPABILITIES
from jacobian.operations import (
    DomainBundle,
    DomainDiagnostics,
    DomainSemantics,
)
from jacobian.provider_runtime import known_provider_runtime

COMBINATORICS_BUNDLE = DomainBundle(
    domain_id="combinatorics",
    schema_namespace="jacobian.combinatorics",
    semantics=DomainSemantics(
        name="jacobian.exact-combinatorics",
        version="1",
        definition={
            "description": "Exact finite combinatorics over bounded non-negative integers",
            "arithmetic": "exact integer via maintained SymPy and stdlib APIs",
            "assurance": "computed; no independent checker",
        },
    ),
    provider_runtime=known_provider_runtime(
        "jacobian.sympy",
        features=("exact-combinatorics",),
    ),
    backend_version=f"python-{platform.python_version()};sympy-{sympy.__version__}",
    capabilities=(
        *COUNTING_CAPABILITIES,
        *PARTITION_CAPABILITIES,
        *RECURRENCE_CAPABILITIES,
    ),
    diagnostics=DomainDiagnostics(
        invalid_request=CapabilityDiagnostic(
            code="INVALID_COMBINATORICS_REQUEST",
            stage="combinatorics_input_validation",
            message="Input does not satisfy the exact combinatorics contract.",
            hint="Provide bounded non-negative integers within each operation's limits.",
        )
    ),
    scope_description="the complete supplied bounded combinatorics input",
    completeness_basis=(
        "exact SymPy and stdlib computation covered the supplied bounded input; "
        "not independently verified"
    ),
    assurance_basis="exact SymPy and stdlib combinatorics; no independent checker invoked",
)
