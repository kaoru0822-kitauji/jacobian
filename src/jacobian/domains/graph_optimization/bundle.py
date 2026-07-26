"""Installation bundle for bounded graph optimization."""

from __future__ import annotations

import z3  # type: ignore[import-untyped]

from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.domains.graph_optimization.chromatic_number import (
    CHROMATIC_NUMBER_CAPABILITY,
)
from jacobian.operations import (
    DomainBundle,
    DomainDiagnostics,
    DomainSemantics,
)
from jacobian.provider_runtime import known_provider_runtime

GRAPH_OPTIMIZATION_BUNDLE = DomainBundle(
    domain_id="graph_optimization",
    schema_namespace="jacobian.graph-optimization",
    semantics=DomainSemantics(
        name="jacobian.bounded-graph-optimization",
        version="1",
        definition={
            "description": (
                "Bounded exact graph-optimization search over finite simple "
                "undirected graphs with explicit wall-clock budgets"
            ),
            "graph_class": "finite simple undirected",
            "max_order": 32,
            "max_edges": 496,
            "budget": "explicit wall_seconds per request",
            "timeout_or_cancellation": (
                "UNKNOWN partial result with preserved bounds and tested obligations"
            ),
            "assurance": "computed; incomplete search is never a conclusion",
        },
    ),
    provider_runtime=known_provider_runtime(
        "jacobian.z3",
        features=("bounded-k-colorability", "timeout-aware"),
    ),
    backend_version=z3.get_version_string(),
    capabilities=(CHROMATIC_NUMBER_CAPABILITY,),
    diagnostics=DomainDiagnostics(
        invalid_request=CapabilityDiagnostic(
            code="INVALID_CHROMATIC_NUMBER_REQUEST",
            stage="request_validation",
            message=(
                "The complete chromatic-number request is invalid: validation failed"
            ),
            hint=(
                "Supply a simple graph with unique vertices and undirected "
                "edges, plus an optional wall_seconds budget from 1 to 120."
            ),
        )
    ),
    scope_description="one bounded simple undirected graph",
    completeness_basis=(
        "Z3 settled every k-colorability decision through the first satisfying k"
    ),
    assurance_basis=(
        "bounded Z3 computation; an independent graph-coloring checker "
        "would still be required for VERIFIED assurance"
    ),
)
