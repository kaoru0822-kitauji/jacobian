"""Owner-local admission decisions for k-regular subgraph operations."""

from __future__ import annotations

from jacobian.catalog.admission import (
    AdmissionDecision,
    OperationAdmission,
    OperationRegistration,
)
from jacobian.math.graphs.regular_subgraph._tools import TOOLS

ADMISSIONS: tuple[OperationAdmission, ...] = (
    OperationAdmission(
        "graph.k_regular_subgraph.find",
        AdmissionDecision.KEEP,
        "distinct exact k-regular subgraph witness search with source-bound edge enumeration",
    ),
)

REGISTRATION = OperationRegistration(TOOLS, ADMISSIONS)
