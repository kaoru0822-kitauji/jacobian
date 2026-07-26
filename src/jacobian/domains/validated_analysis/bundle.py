"""Installation bundle for bounded validated analysis and exact moments."""

from __future__ import annotations

import flint
import sympy

from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.domains.validated_analysis.operations import (
    VALIDATED_ANALYSIS_CAPABILITIES,
)
from jacobian.operations import DomainBundle, DomainDiagnostics, DomainSemantics
from jacobian.provider_runtime import jacobian_provider_runtime

VALIDATED_ANALYSIS_BUNDLE = DomainBundle(
    domain_id="validated_analysis",
    schema_namespace="jacobian.validated-analysis",
    semantics=DomainSemantics(
        name="jacobian.validated-analysis",
        version="1",
        definition={
            "description": (
                "fixed-function rigorous real-ball enclosures, exact finite "
                "rational moments, and standard-form rational LP certificates"
            ),
            "arb_scope": (
                "one EXP, LOG, SQRT, SIN, or COS evaluation at an exact "
                "rational point and declared precision"
            ),
            "moment_scope": (
                "one raw moment of a normalized finite rational distribution"
            ),
            "linear_program_scope": (
                "minimize c^T x subject to A x = b and x >= 0 over rationals"
            ),
            "budget": "wall_seconds is enforced in isolated Arb and SymPy workers",
            "failure": (
                "non-finite balls, timeouts, backend errors, and missing LP "
                "candidates are non-conclusions"
            ),
            "verification": (
                "all outputs remain COMPUTED or UNKNOWN; independent authorized "
                "replay is an open obligation for bounded operations"
            ),
        },
    ),
    provider_runtime=jacobian_provider_runtime(
        "jacobian.validated-analysis",
        features=(
            "arb-point-enclosure",
            "finite-rational-moment",
            "rational-lp-certificate",
            "bounded-worker",
        ),
        configuration={
            "python_flint_version": flint.__version__,
            "sympy_version": sympy.__version__,
        },
    ),
    backend_version=(f"python-flint-{flint.__version__};sympy-{sympy.__version__}"),
    capabilities=VALIDATED_ANALYSIS_CAPABILITIES,
    diagnostics=DomainDiagnostics(
        invalid_request=CapabilityDiagnostic(
            code="INVALID_VALIDATED_ANALYSIS_REQUEST",
            stage="validated_analysis_input_validation",
            message="Input does not satisfy the bounded validated-analysis contract.",
            hint=(
                "Use canonical bounded rationals, fixed supported functions, "
                "normalized finite distributions, or the declared rational LP form."
            ),
        )
    ),
    scope_description="one complete typed validated-analysis request",
    completeness_basis=(
        "the maintained backend produced the complete declared mathematical "
        "object within the request bounds"
    ),
    assurance_basis=(
        "pinned maintained-backend computation; no producer can grant VERIFIED "
        "assurance and bounded results retain an independent replay obligation"
    ),
)

__all__ = ["VALIDATED_ANALYSIS_BUNDLE"]
