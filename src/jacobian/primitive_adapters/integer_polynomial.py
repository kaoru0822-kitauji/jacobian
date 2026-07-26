"""Eight exact deterministic integer-polynomial primitives backed by pinned SymPy.

Capabilities:
  - polynomial.integer.gcd.compute
  - polynomial.integer.resultant.compute
  - polynomial.integer.discriminant.compute
  - polynomial.integer.content.compute
  - polynomial.integer.primitive_part.compute
  - polynomial.integer.evaluate
  - polynomial.integer.compose
  - polynomial.integer.square_free_factorize
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jacobian.primitive_adapters._base import (
    PrimitiveAdapter,
    _check,
    _int_array_field,
    _int_field,
    _schema,
)

if TYPE_CHECKING:
    from jacobian.capabilities import CapabilityAdapter
    from jacobian.kernel import JacobianKernel

_PROVIDER = "jacobian.sympy"
_MAX_COEFFS = 1024
_MAX_POINT = 2**53 - 1


def factory(kernel: JacobianKernel) -> tuple[CapabilityAdapter, ...]:
    return (
        _gcd(),
        _resultant(),
        _discriminant(),
        _content(),
        _primitive_part(),
        _evaluate(),
        _compose(),
        _square_free_factorize(),
    )


def _coeffs_field() -> dict[str, Any]:
    return _int_array_field(max_items=_MAX_COEFFS)


def _invoke_poly(coeffs: list[int], domain: str = "ZZ") -> Any:
    from sympy import Poly, Symbol

    _check(len(coeffs) >= 1, "polynomial requires at least one coefficient")
    x = Symbol("x")
    return Poly(sum(c * x**i for i, c in enumerate(coeffs)), x, domain=domain)


def _gcd() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import Poly, Symbol
        from sympy import gcd as poly_gcd

        a_coeffs = [int(x) for x in inp["a_coefficients"]]
        b_coeffs = [int(x) for x in inp["b_coefficients"]]
        _check(
            len(a_coeffs) >= 1 and len(b_coeffs) >= 1,
            "each polynomial needs >= 1 coefficient",
        )
        x = Symbol("x")
        pa = _invoke_poly(a_coeffs)
        pb = _invoke_poly(b_coeffs)
        g = poly_gcd(pa.as_expr(), pb.as_expr())
        gp = Poly(g, x, domain="ZZ")
        result_coeffs = [int(c) for c in gp.all_coeffs()]
        return {"gcd_coefficients": result_coeffs}

    return PrimitiveAdapter(
        capability_id="polynomial.integer.gcd.compute",
        title="GCD of two integer polynomials",
        description=(
            "Compute the monic GCD of two polynomials in Z[x] using SymPy's "
            "exact polynomial gcd."
        ),
        input_schema=_schema(
            {
                "a_coefficients": _coeffs_field(),
                "b_coefficients": _coeffs_field(),
            },
            required=("a_coefficients", "b_coefficients"),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("polynomial", "integer", "gcd", "exact"),
        scope_description="two bounded integer coefficient lists",
    )


def _resultant() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import Symbol, resultant

        a_coeffs = [int(x) for x in inp["a_coefficients"]]
        b_coeffs = [int(x) for x in inp["b_coefficients"]]
        x = Symbol("x")
        pa = _invoke_poly(a_coeffs)
        pb = _invoke_poly(b_coeffs)
        res = resultant(pa.as_expr(), pb.as_expr(), x)
        return {"resultant": int(res)}

    return PrimitiveAdapter(
        capability_id="polynomial.integer.resultant.compute",
        title="Resultant of two integer polynomials",
        description=(
            "Compute the resultant of two polynomials in Z[x] using SymPy's "
            "exact resultant."
        ),
        input_schema=_schema(
            {
                "a_coefficients": _coeffs_field(),
                "b_coefficients": _coeffs_field(),
            },
            required=("a_coefficients", "b_coefficients"),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("polynomial", "integer", "resultant", "exact"),
        scope_description="two bounded integer coefficient lists",
    )


def _discriminant() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import Symbol, discriminant

        coeffs = [int(x) for x in inp["coefficients"]]
        x = Symbol("x")
        p = _invoke_poly(coeffs)
        disc = discriminant(p.as_expr(), x)
        return {"discriminant": int(disc)}

    return PrimitiveAdapter(
        capability_id="polynomial.integer.discriminant.compute",
        title="Discriminant of an integer polynomial",
        description=(
            "Compute the discriminant of a polynomial in Z[x] using SymPy's "
            "exact discriminant."
        ),
        input_schema=_schema(
            {"coefficients": _coeffs_field()},
            required=("coefficients",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("polynomial", "integer", "discriminant", "exact"),
        scope_description="one bounded integer coefficient list",
    )


def _content() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from math import gcd

        coeffs = [int(x) for x in inp["coefficients"]]
        _check(len(coeffs) >= 1, "polynomial requires at least one coefficient")
        nonzero = [c for c in coeffs if c != 0]
        _check(bool(nonzero), "content is undefined for the zero polynomial")
        content = abs(gcd(*nonzero))
        return {"content": content}

    return PrimitiveAdapter(
        capability_id="polynomial.integer.content.compute",
        title="Content of an integer polynomial",
        description=(
            "Compute the content (GCD of absolute values of coefficients) of a "
            "polynomial in Z[x] using exact integer GCD."
        ),
        input_schema=_schema(
            {"coefficients": _coeffs_field()},
            required=("coefficients",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("polynomial", "integer", "content", "exact"),
        scope_description="one bounded integer coefficient list",
    )


def _primitive_part() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from math import gcd

        coeffs = [int(x) for x in inp["coefficients"]]
        _check(len(coeffs) >= 1, "polynomial requires at least one coefficient")
        nonzero = [c for c in coeffs if c != 0]
        _check(bool(nonzero), "primitive part is undefined for the zero polynomial")
        content = abs(gcd(*nonzero))
        primitive = [c // content for c in coeffs]
        leading = primitive[-1] if len(coeffs) > 1 else primitive[0]
        if leading < 0:
            primitive = [-c for c in primitive]
        return {"content": content, "primitive_part_coefficients": primitive}

    return PrimitiveAdapter(
        capability_id="polynomial.integer.primitive_part.compute",
        title="Primitive part of an integer polynomial",
        description=(
            "Compute the primitive part (coefficients divided by content, "
            "sign-normalised) of a polynomial in Z[x]."
        ),
        input_schema=_schema(
            {"coefficients": _coeffs_field()},
            required=("coefficients",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("polynomial", "integer", "primitive_part", "exact"),
        scope_description="one bounded integer coefficient list",
    )


def _evaluate() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        coeffs = [int(x) for x in inp["coefficients"]]
        point = int(inp["point"])
        result = 0
        for i, c in enumerate(coeffs):
            result += c * point**i
        return {"point": point, "value": int(result)}

    return PrimitiveAdapter(
        capability_id="polynomial.integer.evaluate",
        title="Evaluate an integer polynomial at an integer point",
        description=(
            "Evaluate p(x) = sum c_i x^i at a bounded integer point using exact "
            "integer arithmetic (Horner-free direct evaluation)."
        ),
        input_schema=_schema(
            {
                "coefficients": _coeffs_field(),
                "point": _int_field(minimum=-_MAX_POINT, maximum=_MAX_POINT),
            },
            required=("coefficients", "point"),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("polynomial", "integer", "evaluate", "exact"),
        scope_description="bounded coefficients and bounded integer point",
    )


def _compose() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import Poly, Symbol, compose

        outer = [int(x) for x in inp["outer_coefficients"]]
        inner = [int(x) for x in inp["inner_coefficients"]]
        x = Symbol("x")
        po = _invoke_poly(outer)
        pi = _invoke_poly(inner)
        composed = compose(po.as_expr(), pi.as_expr(), x)
        pc = Poly(composed, x, domain="ZZ")
        return {"composed_coefficients": [int(c) for c in pc.all_coeffs()]}

    return PrimitiveAdapter(
        capability_id="polynomial.integer.compose",
        title="Compose two integer polynomials",
        description=(
            "Compute (outer circ inner)(x) = outer(inner(x)) for two polynomials "
            "in Z[x] using SymPy's exact compose."
        ),
        input_schema=_schema(
            {
                "outer_coefficients": _coeffs_field(),
                "inner_coefficients": _coeffs_field(),
            },
            required=("outer_coefficients", "inner_coefficients"),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("polynomial", "integer", "compose", "exact"),
        scope_description="two bounded integer coefficient lists",
    )


def _square_free_factorize() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import Poly, Symbol, sqf_list

        coeffs = [int(x) for x in inp["coefficients"]]
        x = Symbol("x")
        p = _invoke_poly(coeffs)
        factors = sqf_list(p.as_expr(), x)
        result: list[dict[str, Any]] = []
        for factor, mult in factors[1]:
            fp = Poly(factor, x, domain="ZZ")
            result.append(
                {
                    "factor_coefficients": [int(c) for c in fp.all_coeffs()],
                    "multiplicity": int(mult),
                }
            )
        return {"square_free_factors": result}

    return PrimitiveAdapter(
        capability_id="polynomial.integer.square_free_factorize",
        title="Square-free factorization in Z[x]",
        description=(
            "Compute the square-free factorization of a polynomial in Z[x] "
            "using SymPy's exact sqf_list."
        ),
        input_schema=_schema(
            {"coefficients": _coeffs_field()},
            required=("coefficients",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("polynomial", "integer", "square_free", "exact"),
        scope_description="one bounded integer coefficient list",
    )
