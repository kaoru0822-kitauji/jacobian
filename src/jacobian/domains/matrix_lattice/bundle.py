"""Installation bundle for exact matrix operations."""

from __future__ import annotations

import sympy

from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.domains.matrix_lattice.capabilities import MATRIX_CAPABILITIES
from jacobian.operations import DomainBundle, DomainDiagnostics, DomainSemantics
from jacobian.provider_runtime import known_provider_runtime

MATRIX_BUNDLE = DomainBundle(
    domain_id="matrix",
    schema_namespace="jacobian.matrix",
    semantics=DomainSemantics(
        name="jacobian.exact-matrix-operations",
        version="1",
        definition={
            "domains": ["QQ", "ZZ"],
            "maximum_rows": 32,
            "maximum_columns": 32,
            "maximum_decimal_digits_per_scalar_component": 256,
            "rref": "unique reduced row echelon form over QQ",
            "nullspace": "RREF fundamental basis ordered by ascending free column",
            "characteristic_polynomial": "dense det(lambda I - A) coefficients",
            "smith_normal_form": (
                "positive divisibility diagonal; transformations unavailable"
            ),
            "assurance": "computed; no producer result is independently verified",
        },
    ),
    provider_runtime=known_provider_runtime(
        "jacobian.sympy",
        features=(
            "exact-rational-matrix",
            "rref",
            "nullspace",
            "characteristic-polynomial",
            "smith-normal-form",
        ),
    ),
    backend_version=sympy.__version__,
    capabilities=MATRIX_CAPABILITIES,
    diagnostics=DomainDiagnostics(
        invalid_request=CapabilityDiagnostic(
            code="INVALID_EXACT_MATRIX_REQUEST",
            stage="matrix_input_validation",
            message="Input does not satisfy the bounded exact matrix contract.",
            hint=(
                "Use a nonempty 1..32 by 1..32 matrix with canonical QQ or ZZ "
                "entries of at most 256 decimal digits."
            ),
        )
    ),
    scope_description="the complete supplied bounded exact matrix",
    completeness_basis=(
        "exact symbolic computation covered the full finite matrix; "
        "not independently verified"
    ),
    assurance_basis="exact SymPy arithmetic; no independent checker invoked",
)
