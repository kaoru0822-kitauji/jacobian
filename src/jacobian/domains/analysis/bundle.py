"""Validated real-analysis domain bundle."""

from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.domains.analysis.operations import POINT_ENCLOSURE_CAPABILITIES
from jacobian.operations import DomainBundle, DomainDiagnostics, DomainSemantics
from jacobian.provider_runtime import (
    PYTHON_FLINT_VERSION,
    python_flint_analysis_provider_runtime,
)

REAL_ANALYSIS_BUNDLE = DomainBundle(
    domain_id="analysis",
    schema_namespace="jacobian.validated-analysis",
    semantics=DomainSemantics(
        name="jacobian.analysis",
        version="1",
        definition={
            "description": "rigorous real-function enclosures",
            "scope": (
                "one EXP, LOG, SQRT, SIN, or COS evaluation at an exact "
                "rational point and declared precision"
            ),
            "budget": "wall_seconds is enforced in an isolated Arb worker",
            "failure": "non-finite balls and worker failures are non-conclusions",
        },
    ),
    provider_runtime=python_flint_analysis_provider_runtime(),
    backend_version=f"python-flint-{PYTHON_FLINT_VERSION}",
    capabilities=POINT_ENCLOSURE_CAPABILITIES,
    diagnostics=DomainDiagnostics(
        invalid_request=CapabilityDiagnostic(
            code="INVALID_REAL_ANALYSIS_REQUEST",
            stage="real_analysis_input_validation",
            message="Input does not satisfy the bounded real-analysis contract.",
            hint="Use a supported function, bounded rational, and declared precision.",
        )
    ),
    scope_description="one bounded real-function point-enclosure request",
    completeness_basis="Arb produced the complete declared enclosure",
    assurance_basis=(
        "pinned maintained-backend computation; independent replay remains open"
    ),
)

__all__ = ["REAL_ANALYSIS_BUNDLE"]
