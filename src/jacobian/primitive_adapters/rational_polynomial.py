"""Six exact deterministic rational-polynomial primitives backed by pinned SymPy.

Capabilities:
  - polynomial.rational.gcd.compute
  - polynomial.rational.quotient_remainder.compute
  - polynomial.rational.evaluate
  - polynomial.rational.derivative.compute
  - polynomial.rational.integrate.polynomial
  - polynomial.rational.partial_fraction.decompose
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jacobian.primitive_adapters._base import (
    PrimitiveAdapter,
    _check,
    _frac_to_json,
    _parse_rational,
    _rational_array_field,
    _rational_field,
    _schema,
)

if TYPE_CHECKING:
    from jacobian.capabilities import CapabilityAdapter
    from jacobian.kernel import JacobianKernel

_PROVIDER = "jacobian.sympy"
_MAX_COEFFS = 512


def factory(kernel: JacobianKernel) -> tuple[CapabilityAdapter, ...]:
    return (
        _gcd(),
        _quotient_remainder(),
        _evaluate(),
        _derivative(),
        _integrate(),
        _partial_fraction(),
    )


def _coeffs_field() -> dict[str, Any]:
    return _rational_array_field(max_items=_MAX_COEFFS)


def _build_poly(coeffs: list[Any], domain: str = "QQ") -> Any:
    from sympy import Poly, Symbol

    _check(len(coeffs) >= 1, "polynomial requires at least one coefficient")
    x = Symbol("x")
    terms = sum(c * x**i for i, c in enumerate(coeffs))
    return Poly(terms, x, domain=domain)


def _gcd() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from fractions import Fraction

        from sympy import Poly, Symbol
        from sympy import gcd as poly_gcd

        a_coeffs = [_parse_rational(c) for c in inp["a_coefficients"]]
        b_coeffs = [_parse_rational(c) for c in inp["b_coefficients"]]
        x = Symbol("x")
        pa = _build_poly(a_coeffs)
        pb = _build_poly(b_coeffs)
        g = poly_gcd(pa.as_expr(), pb.as_expr())
        gp = Poly(g, x, domain="QQ")
        raw = gp.all_coeffs()
        return {"gcd_coefficients": [_frac_to_json(Fraction(c)) for c in raw]}

    return PrimitiveAdapter(
        capability_id="polynomial.rational.gcd.compute",
        title="GCD of two rational polynomials",
        description=(
            "Compute the monic GCD of two polynomials in Q[x] using SymPy's "
            "exact polynomial gcd over the rationals."
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
        tags=("polynomial", "rational", "gcd", "exact"),
        scope_description="two bounded rational coefficient lists",
    )


def _quotient_remainder() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from fractions import Fraction

        from sympy import Poly, Symbol, div

        a_coeffs = [_parse_rational(c) for c in inp["a_coefficients"]]
        b_coeffs = [_parse_rational(c) for c in inp["b_coefficients"]]
        _check(any(c != 0 for c in b_coeffs), "divisor polynomial must be nonzero")
        x = Symbol("x")
        pa = _build_poly(a_coeffs)
        pb = _build_poly(b_coeffs)
        q, r = div(pa.as_expr(), pb.as_expr(), x, domain="QQ")
        qp = Poly(q, x, domain="QQ")
        rp = Poly(r, x, domain="QQ")
        return {
            "quotient_coefficients": [
                _frac_to_json(Fraction(c)) for c in qp.all_coeffs()
            ],
            "remainder_coefficients": [
                _frac_to_json(Fraction(c)) for c in rp.all_coeffs()
            ],
        }

    return PrimitiveAdapter(
        capability_id="polynomial.rational.quotient_remainder.compute",
        title="Exact quotient and remainder in Q[x]",
        description=(
            "Compute (quotient, remainder) of a / b in Q[x] using SymPy's exact "
            "polynomial div."
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
        tags=("polynomial", "rational", "div", "exact"),
        scope_description="two bounded rational coefficient lists",
    )


def _evaluate() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from fractions import Fraction

        coeffs = [_parse_rational(c) for c in inp["coefficients"]]
        point = _parse_rational(inp["point"])
        result = Fraction(0)
        for i, c in enumerate(coeffs):
            result += c * point**i
        return {"point": _frac_to_json(point), "value": _frac_to_json(result)}

    return PrimitiveAdapter(
        capability_id="polynomial.rational.evaluate",
        title="Evaluate a rational polynomial at a rational point",
        description=(
            "Evaluate p(x) = sum c_i x^i at a bounded rational point using "
            "exact rational arithmetic."
        ),
        input_schema=_schema(
            {
                "coefficients": _coeffs_field(),
                "point": _rational_field(),
            },
            required=("coefficients", "point"),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("polynomial", "rational", "evaluate", "exact"),
        scope_description="bounded rational coefficients and rational point",
    )


def _derivative() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from fractions import Fraction

        from sympy import Poly, Symbol, diff

        coeffs = [_parse_rational(c) for c in inp["coefficients"]]
        x = Symbol("x")
        p = _build_poly(coeffs)
        d = diff(p.as_expr(), x)
        dp = Poly(d, x, domain="QQ")
        return {
            "derivative_coefficients": [
                _frac_to_json(Fraction(c)) for c in dp.all_coeffs()
            ],
        }

    return PrimitiveAdapter(
        capability_id="polynomial.rational.derivative.compute",
        title="Formal derivative in Q[x]",
        description=(
            "Compute the formal derivative dp/dx of a polynomial in Q[x] using "
            "SymPy's exact diff."
        ),
        input_schema=_schema(
            {"coefficients": _coeffs_field()},
            required=("coefficients",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("polynomial", "rational", "derivative", "exact"),
        scope_description="one bounded rational coefficient list",
    )


def _integrate() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from fractions import Fraction

        from sympy import Poly, Symbol, integrate

        coeffs = [_parse_rational(c) for c in inp["coefficients"]]
        x = Symbol("x")
        p = _build_poly(coeffs)
        antideriv = integrate(p.as_expr(), x)
        ap = Poly(antideriv, x, domain="QQ")
        return {
            "antiderivative_coefficients": [
                _frac_to_json(Fraction(c)) for c in ap.all_coeffs()
            ],
        }

    return PrimitiveAdapter(
        capability_id="polynomial.rational.integrate.polynomial",
        title="Formal antiderivative in Q[x]",
        description=(
            "Compute the polynomial antiderivative integral p(x) dx of a "
            "polynomial in Q[x] using SymPy's exact integrate."
        ),
        input_schema=_schema(
            {"coefficients": _coeffs_field()},
            required=("coefficients",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("polynomial", "rational", "integrate", "exact"),
        scope_description="one bounded rational coefficient list",
    )


def _partial_fraction() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import Symbol, apart

        numerator = [_parse_rational(c) for c in inp["numerator_coefficients"]]
        denominator = [_parse_rational(c) for c in inp["denominator_coefficients"]]
        _check(any(c != 0 for c in denominator), "denominator must be nonzero")
        x = Symbol("x")
        pn = _build_poly(numerator)
        pd = _build_poly(denominator)
        expr = pn.as_expr() / pd.as_expr()
        decomposed = apart(expr, x)
        return {"decomposition": str(decomposed)}

    return PrimitiveAdapter(
        capability_id="polynomial.rational.partial_fraction.decompose",
        title="Partial fraction decomposition over Q",
        description=(
            "Compute the partial fraction decomposition of a rational function "
            "P(x)/Q(x) over Q using SymPy's exact apart."
        ),
        input_schema=_schema(
            {
                "numerator_coefficients": _coeffs_field(),
                "denominator_coefficients": _coeffs_field(),
            },
            required=("numerator_coefficients", "denominator_coefficients"),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("polynomial", "rational", "partial_fraction", "exact"),
        scope_description="two bounded rational coefficient lists",
    )
