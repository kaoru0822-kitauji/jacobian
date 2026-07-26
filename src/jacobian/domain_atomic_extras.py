"""Additional resource-led, one-outcome domain primitives.

These small operations are deliberately separate from search and verification:
each returns one exact computed object, with bounded JSON input and COMPUTED
assurance only.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, cast

from jacobian.primitive_adapters._base import (
    PrimitiveAdapter,
    _build_graph,
    _check,
    _edge_array_field,
    _int_array_field,
    _int_field,
    _matrix_field,
    _parse_rational_matrix,
    _rational_field,
    _rational_matrix_field,
    _schema,
    _string_array_field,
)

if TYPE_CHECKING:
    from jacobian.capabilities import CapabilityAdapter
    from jacobian.kernel import JacobianKernel

_PROVIDER_SYMPY = "jacobian.sympy"
_PROVIDER_NETWORKX = "jacobian.networkx"
_MAX = 2**53 - 1
_GRAPH_INPUT = {
    "vertices": _string_array_field(min_items=0, max_items=64),
    "edges": _edge_array_field(max_items=512),
}


def install_domain_atomic_extras(
    kernel: JacobianKernel,
) -> tuple[CapabilityAdapter, ...]:
    """Install twelve exact primitives not covered by the core portfolio."""
    return (
        _prime_counting(),
        _is_square(),
        _legendre_symbol(),
        _factorial_valuation(),
        _multinomial(),
        _fibonacci_pair(),
        _integer_shift(),
        _rational_solve(),
        _adjugate(),
        _triangle_count(),
        _k_core(),
        _graph_radius(),
    )


def _prime_counting() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import primepi

        return {"n": int(inp["n"]), "prime_count": int(primepi(inp["n"]))}

    return PrimitiveAdapter(
        capability_id="number_theory.prime_counting.compute",
        title="Count primes up to one integer",
        description="Compute the exact prime-counting function pi(n).",
        input_schema=_schema({"n": _int_field(maximum=10**8)}, required=("n",)),
        invoke=invoke,
        provider=_PROVIDER_SYMPY,
        tags=("number-theory", "prime-counting", "exact"),
    )


def _is_square() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import integer_nthroot

        root, exact = integer_nthroot(inp["n"], 2)
        return {"n": int(inp["n"]), "root": int(root), "is_square": bool(exact)}

    return PrimitiveAdapter(
        capability_id="number_theory.square.test",
        title="Test whether one integer is a square",
        description="Compute the exact integer square-root test.",
        input_schema=_schema({"n": _int_field(maximum=10**12)}, required=("n",)),
        invoke=invoke,
        provider=_PROVIDER_SYMPY,
        tags=("number-theory", "square", "exact"),
    )


def _legendre_symbol() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import legendre_symbol

        return {
            "a": int(inp["a"]),
            "prime": int(inp["prime"]),
            "symbol": int(legendre_symbol(inp["a"], inp["prime"])),
        }

    return PrimitiveAdapter(
        capability_id="number_theory.legendre_symbol.compute",
        title="Compute one Legendre symbol",
        description="Compute (a/p) for a bounded odd prime p.",
        input_schema=_schema(
            {
                "a": _int_field(minimum=-_MAX, maximum=_MAX),
                "prime": _int_field(minimum=3, maximum=10**7),
            },
            required=("a", "prime"),
        ),
        invoke=invoke,
        provider=_PROVIDER_SYMPY,
        tags=("number-theory", "quadratic-residue", "exact"),
    )


def _factorial_valuation() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import factorint

        n, base = int(inp["n"]), int(inp["base"])
        _check(base >= 2, "base must be at least 2")
        valuation = math.inf
        for prime, exponent in factorint(base).items():
            power = int(prime)
            total = 0
            while power <= n:
                total += n // power
                if power > n // int(prime):
                    break
                power *= int(prime)
            valuation = min(valuation, total // int(exponent))
        return {"n": n, "base": base, "valuation": int(valuation)}

    return PrimitiveAdapter(
        capability_id="number_theory.factorial_valuation.compute",
        title="Compute the base valuation of a factorial",
        description="Compute the largest e with base^e dividing n!, exactly.",
        input_schema=_schema(
            {
                "n": _int_field(maximum=100000),
                "base": _int_field(minimum=2, maximum=10**6),
            },
            required=("n", "base"),
        ),
        invoke=invoke,
        provider=_PROVIDER_SYMPY,
        tags=("number-theory", "valuation", "exact"),
    )


def _multinomial() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        parts = [int(v) for v in inp["parts"]]
        total = math.factorial(sum(parts))
        for part in parts:
            total //= math.factorial(part)
        return {"parts": parts, "value": total}

    return PrimitiveAdapter(
        capability_id="combinatorics.multinomial.compute",
        title="Compute one multinomial coefficient",
        description="Compute (sum parts)! divided by the factorials of the parts.",
        input_schema=_schema(
            {"parts": _int_array_field(max_items=16, item_maximum=1000)},
            required=("parts",),
        ),
        invoke=invoke,
        provider=_PROVIDER_SYMPY,
        tags=("combinatorics", "multinomial", "exact"),
    )


def _fibonacci_pair() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import fibonacci

        n = int(inp["n"])
        return {"n": n, "f_n": int(fibonacci(n)), "f_n_plus_one": int(fibonacci(n + 1))}

    return PrimitiveAdapter(
        capability_id="combinatorics.fibonacci_pair.compute",
        title="Compute consecutive Fibonacci numbers",
        description="Return F_n and F_(n+1) as one exact recurrence boundary.",
        input_schema=_schema({"n": _int_field(maximum=10000)}, required=("n",)),
        invoke=invoke,
        provider=_PROVIDER_SYMPY,
        tags=("combinatorics", "fibonacci", "exact"),
    )


def _integer_shift() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import Poly, Symbol, expand

        x = Symbol("x")
        coeffs = [int(v) for v in inp["coefficients"]]
        expression = sum(value * x**index for index, value in enumerate(coeffs))
        shifted = Poly(expand(expression.subs(x, x + inp["shift"])), x)
        return {
            "shift": int(inp["shift"]),
            "coefficients": [int(v) for v in shifted.all_coeffs()],
        }

    return PrimitiveAdapter(
        capability_id="polynomial.integer.shift.compute",
        title="Shift one integer polynomial",
        description="Compute p(x + a) exactly for one bounded integer polynomial.",
        input_schema=_schema(
            {
                "coefficients": _int_array_field(
                    max_items=64, item_minimum=-(10**6), item_maximum=10**6
                ),
                "shift": _int_field(minimum=-10000, maximum=10000),
            },
            required=("coefficients", "shift"),
        ),
        invoke=invoke,
        provider=_PROVIDER_SYMPY,
        tags=("polynomial", "integer", "shift", "exact"),
    )


def _rational_solve() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import Matrix, Rational

        rows, cols, entries = _parse_rational_matrix(inp["matrix"])
        rhs = [Rational(v["numerator"], v["denominator"]) for v in inp["rhs"]]
        _check(
            rows == cols and len(rhs) == rows, "square matrix and matching rhs required"
        )
        matrix = Matrix(
            rows,
            cols,
            [Rational(v.numerator, v.denominator) for v in entries],
        )
        solution, parameters = matrix.gauss_jordan_solve(Matrix(rhs))
        _check(not parameters, "linear system has free parameters")
        return {"solution": [str(value) for value in solution]}

    return PrimitiveAdapter(
        capability_id="matrix.rational.solve",
        title="Solve one exact rational linear system",
        description="Solve Ax=b for one bounded nonsingular rational matrix.",
        input_schema=_schema(
            {
                "matrix": _rational_matrix_field(max_rows=12, max_cols=12),
                "rhs": {
                    "type": "array",
                    "items": _rational_field(),
                    "minItems": 1,
                    "maxItems": 12,
                },
            },
            required=("matrix", "rhs"),
        ),
        invoke=invoke,
        provider=_PROVIDER_SYMPY,
        tags=("linear-algebra", "rational", "exact"),
    )


def _adjugate() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import Matrix

        rows, cols, entries = _parse_int_matrix(inp["matrix"])
        _check(rows == cols, "adjugate requires a square matrix")
        return {
            "adjugate": [
                [str(v) for v in row]
                for row in Matrix(rows, cols, entries).adjugate().tolist()
            ]
        }

    from jacobian.primitive_adapters._base import _parse_int_matrix

    return PrimitiveAdapter(
        capability_id="matrix.invariant.adjugate",
        title="Compute one exact matrix adjugate",
        description="Compute adj(A) for one bounded integer square matrix.",
        input_schema=_schema(
            {"matrix": _matrix_field(max_rows=12, max_cols=12)}, required=("matrix",)
        ),
        invoke=invoke,
        provider=_PROVIDER_SYMPY,
        tags=("linear-algebra", "adjugate", "exact"),
    )


def _triangle_count() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        import networkx as nx

        graph = _build_graph(inp)
        triangle_counts = cast(dict[Any, int], nx.triangles(graph))
        return {"triangle_count": sum(triangle_counts.values()) // 3}

    return PrimitiveAdapter(
        capability_id="graph.invariant.triangle_count",
        title="Count triangles in one simple graph",
        description="Compute the exact number of 3-cycles in a finite simple graph.",
        input_schema=_schema(_GRAPH_INPUT, required=("vertices", "edges")),
        invoke=invoke,
        provider=_PROVIDER_NETWORKX,
        tags=("graph", "triangle", "exact"),
    )


def _k_core() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        import networkx as nx

        core = nx.k_core(_build_graph(inp), k=int(inp["k"]))
        return {"k": int(inp["k"]), "vertices": sorted(str(v) for v in core.nodes())}

    return PrimitiveAdapter(
        capability_id="graph.invariant.k_core",
        title="Extract one graph k-core",
        description="Return the vertices of the exact k-core of a simple graph.",
        input_schema=_schema(
            {**_GRAPH_INPUT, "k": _int_field(maximum=64)},
            required=("vertices", "edges", "k"),
        ),
        invoke=invoke,
        provider=_PROVIDER_NETWORKX,
        tags=("graph", "k-core", "exact"),
    )


def _graph_radius() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        import networkx as nx

        graph = _build_graph(inp)
        _check(
            len(graph) == 0 or nx.is_connected(graph),
            "radius requires a connected graph",
        )
        return {"radius": 0 if len(graph) == 0 else int(nx.radius(graph))}

    return PrimitiveAdapter(
        capability_id="graph.invariant.radius",
        title="Compute the radius of one connected graph",
        description="Compute the exact eccentricity radius for a connected graph.",
        input_schema=_schema(_GRAPH_INPUT, required=("vertices", "edges")),
        invoke=invoke,
        provider=_PROVIDER_NETWORKX,
        tags=("graph", "distance", "exact"),
    )
