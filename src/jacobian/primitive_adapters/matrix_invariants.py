"""Eight exact deterministic integer-matrix invariant primitives backed by pinned SymPy.

Capabilities:
  - matrix.integer.rank.compute
  - matrix.integer.determinant.compute
  - matrix.integer.inverse.compute
  - matrix.integer.kernel_basis.compute
  - matrix.integer.row_hermite_normal_form
  - matrix.integer.smith_normal_form
  - matrix.integer.trace.compute
  - matrix.integer.characteristic_polynomial.compute
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jacobian.primitive_adapters._base import (
    PrimitiveAdapter,
    _check,
    _frac_matrix_to_json,
    _frac_to_json,
    _matrix_field,
    _parse_int_matrix,
    _schema,
)

if TYPE_CHECKING:
    from jacobian.capabilities import CapabilityAdapter
    from jacobian.kernel import JacobianKernel

_PROVIDER = "jacobian.sympy"
_MAX_DIM = 64


def factory(kernel: JacobianKernel) -> tuple[CapabilityAdapter, ...]:
    return (
        _rank(),
        _determinant(),
        _inverse(),
        _kernel_basis(),
        _hermite_normal_form(),
        _smith_normal_form(),
        _trace(),
        _characteristic_polynomial(),
    )


def _matrix_schema() -> dict[str, Any]:
    return _matrix_field(max_rows=_MAX_DIM, max_cols=_MAX_DIM)


def _build_matrix(rows: int, cols: int, entries: list[int]) -> Any:
    from sympy import Matrix

    return Matrix(rows, cols, entries)


def _rank() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        rows, cols, entries = _parse_int_matrix(inp["matrix"])
        m = _build_matrix(rows, cols, entries)
        return {"rank": int(m.rank())}

    return PrimitiveAdapter(
        capability_id="matrix.integer.rank.compute",
        title="Rank of an integer matrix",
        description=(
            "Compute the exact rank of a bounded integer matrix using SymPy's "
            "Matrix.rank()."
        ),
        input_schema=_schema(
            {"matrix": _matrix_schema()},
            required=("matrix",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("matrix", "integer", "rank", "exact"),
        scope_description="one bounded integer matrix",
    )


def _determinant() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        rows, cols, entries = _parse_int_matrix(inp["matrix"])
        _check(rows == cols, "determinant requires a square matrix")
        m = _build_matrix(rows, cols, entries)
        return {"determinant": int(m.det())}

    return PrimitiveAdapter(
        capability_id="matrix.integer.determinant.compute",
        title="Determinant of an integer matrix",
        description=(
            "Compute the exact determinant of a bounded square integer matrix "
            "using SymPy's Matrix.det()."
        ),
        input_schema=_schema(
            {"matrix": _matrix_schema()},
            required=("matrix",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("matrix", "integer", "determinant", "exact"),
        scope_description="one bounded square integer matrix",
    )


def _inverse() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from fractions import Fraction

        rows, cols, entries = _parse_int_matrix(inp["matrix"])
        _check(rows == cols, "inverse requires a square matrix")
        m = _build_matrix(rows, cols, entries)
        det = int(m.det())
        _check(det != 0, "matrix is singular; inverse does not exist")
        inv = m.inv()
        flat = [Fraction(inv[r, c]) for r in range(rows) for c in range(cols)]
        return {"inverse": _frac_matrix_to_json(rows, cols, flat)}

    return PrimitiveAdapter(
        capability_id="matrix.integer.inverse.compute",
        title="Inverse of a nonsingular integer matrix",
        description=(
            "Compute the exact rational inverse of a bounded nonsingular square "
            "integer matrix using SymPy's Matrix.inv()."
        ),
        input_schema=_schema(
            {"matrix": _matrix_schema()},
            required=("matrix",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("matrix", "integer", "inverse", "exact"),
        scope_description="one bounded nonsingular square integer matrix",
    )


def _kernel_basis() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from fractions import Fraction

        rows, cols, entries = _parse_int_matrix(inp["matrix"])
        m = _build_matrix(rows, cols, entries)
        nullspace = m.nullspace()
        basis: list[list[dict[str, int]]] = []
        for vec in nullspace:
            flat = [Fraction(vec[r, 0]) for r in range(cols)]
            basis.append([_frac_to_json(v) for v in flat])
        return {"kernel_dimension": len(basis), "basis_vectors": basis}

    return PrimitiveAdapter(
        capability_id="matrix.integer.kernel_basis.compute",
        title="Integer nullspace basis",
        description=(
            "Compute a rational basis for the nullspace (kernel) of a bounded "
            "integer matrix using SymPy's Matrix.nullspace()."
        ),
        input_schema=_schema(
            {"matrix": _matrix_schema()},
            required=("matrix",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("matrix", "integer", "kernel", "exact"),
        scope_description="one bounded integer matrix",
    )


def _hermite_normal_form() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy.matrices.normalforms import hermite_normal_form

        rows, cols, entries = _parse_int_matrix(inp["matrix"])
        m = _build_matrix(rows, cols, entries)
        hnf = hermite_normal_form(m)
        flat = [int(hnf[r, c]) for r in range(rows) for c in range(cols)]
        return {
            "hermite_normal_form": {
                "rows": rows,
                "cols": cols,
                "entries": flat,
            },
        }

    return PrimitiveAdapter(
        capability_id="matrix.integer.row_hermite_normal_form",
        title="Hermite normal form",
        description=(
            "Compute the row Hermite normal form of a bounded integer matrix "
            "using SymPy's Matrix.hermite_normal_form()."
        ),
        input_schema=_schema(
            {"matrix": _matrix_schema()},
            required=("matrix",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("matrix", "integer", "hermite_normal_form", "exact"),
        scope_description="one bounded integer matrix",
    )


def _smith_normal_form() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy.matrices.normalforms import smith_normal_form

        rows, cols, entries = _parse_int_matrix(inp["matrix"])
        m = _build_matrix(rows, cols, entries)
        snf = smith_normal_form(m)
        flat = [int(snf[r, c]) for r in range(rows) for c in range(cols)]
        return {
            "smith_normal_form": {
                "rows": rows,
                "cols": cols,
                "entries": flat,
            },
        }

    return PrimitiveAdapter(
        capability_id="matrix.integer.smith_normal_form",
        title="Smith normal form",
        description=(
            "Compute the Smith normal form of a bounded integer matrix using "
            "SymPy's Matrix.smith_normal_form()."
        ),
        input_schema=_schema(
            {"matrix": _matrix_schema()},
            required=("matrix",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("matrix", "integer", "smith_normal_form", "exact"),
        scope_description="one bounded integer matrix",
    )


def _trace() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        rows, cols, entries = _parse_int_matrix(inp["matrix"])
        _check(rows == cols, "trace requires a square matrix")
        m = _build_matrix(rows, cols, entries)
        return {"trace": int(m.trace())}

    return PrimitiveAdapter(
        capability_id="matrix.integer.trace.compute",
        title="Trace of an integer matrix",
        description=(
            "Compute the exact trace (sum of diagonal entries) of a bounded "
            "square integer matrix."
        ),
        input_schema=_schema(
            {"matrix": _matrix_schema()},
            required=("matrix",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("matrix", "integer", "trace", "exact"),
        scope_description="one bounded square integer matrix",
    )


def _characteristic_polynomial() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        rows, cols, entries = _parse_int_matrix(inp["matrix"])
        _check(rows == cols, "characteristic polynomial requires a square matrix")
        m = _build_matrix(rows, cols, entries)
        char_poly = m.charpoly()
        coeffs = [int(c) for c in char_poly.all_coeffs()]
        return {"characteristic_polynomial_coefficients": coeffs}

    return PrimitiveAdapter(
        capability_id="matrix.integer.characteristic_polynomial.compute",
        title="Characteristic polynomial of an integer matrix",
        description=(
            "Compute the exact characteristic polynomial coefficients of a "
            "bounded square integer matrix using SymPy's Matrix.charpoly()."
        ),
        input_schema=_schema(
            {"matrix": _matrix_schema()},
            required=("matrix",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("matrix", "integer", "characteristic_polynomial", "exact"),
        scope_description="one bounded square integer matrix",
    )
