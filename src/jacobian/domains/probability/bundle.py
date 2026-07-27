"""Finite-probability domain bundle."""

from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.domains.probability.operations import FINITE_MOMENT_CAPABILITIES
from jacobian.operations import DomainBundle, DomainDiagnostics, DomainSemantics
from jacobian.provider_runtime import (
    PYTHON_FLINT_VERSION,
    python_flint_probability_provider_runtime,
)

FINITE_PROBABILITY_BUNDLE = DomainBundle(
    domain_id="probability",
    schema_namespace="jacobian.validated-analysis",
    semantics=DomainSemantics(
        name="jacobian.probability",
        version="1",
        definition={
            "description": "exact finite probability calculations",
            "scope": "one raw moment of a normalized finite rational distribution",
            "failure": "invalid distributions fail before computation",
        },
    ),
    provider_runtime=python_flint_probability_provider_runtime(),
    backend_version=f"python-flint-{PYTHON_FLINT_VERSION}",
    capabilities=FINITE_MOMENT_CAPABILITIES,
    diagnostics=DomainDiagnostics(
        invalid_request=CapabilityDiagnostic(
            code="INVALID_FINITE_PROBABILITY_REQUEST",
            stage="finite_probability_input_validation",
            message="Input does not satisfy the finite-probability contract.",
            hint="Use bounded rational atoms whose probabilities sum exactly to one.",
        )
    ),
    scope_description="one exact finite-probability request",
    completeness_basis="Python-FLINT produced every exact atom contribution",
    assurance_basis="pinned maintained-backend exact rational computation",
)

__all__ = ["FINITE_PROBABILITY_BUNDLE"]
