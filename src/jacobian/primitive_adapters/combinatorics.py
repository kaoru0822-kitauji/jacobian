"""Eight exact deterministic combinatorics primitives backed by pinned SymPy.

Capabilities:
  - combinatorics.binomial.compute
  - combinatorics.factorial.compute
  - combinatorics.permutation_count.compute
  - combinatorics.stirling_second.compute
  - combinatorics.bell_number.compute
  - combinatorics.catalan_number.compute
  - combinatorics.integer_partition.count
  - combinatorics.integer_partition.enumerate
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jacobian.primitive_adapters._base import (
    PrimitiveAdapter,
    _check,
    _int_field,
    _schema,
)

if TYPE_CHECKING:
    from jacobian.capabilities import CapabilityAdapter
    from jacobian.kernel import JacobianKernel

_PROVIDER = "jacobian.sympy"
_MAX_N = 10000


def factory(kernel: JacobianKernel) -> tuple[CapabilityAdapter, ...]:
    return (
        _binomial(),
        _factorial(),
        _permutation_count(),
        _stirling_second(),
        _bell_number(),
        _catalan_number(),
        _partition_count(),
        _partition_enumerate(),
    )


def _binomial() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import binomial

        n = int(inp["n"])
        k = int(inp["k"])
        _check(0 <= k <= n, "binomial requires 0 <= k <= n")
        return {"n": n, "k": k, "binomial": int(binomial(n, k))}

    return PrimitiveAdapter(
        capability_id="combinatorics.binomial.compute",
        title="Exact binomial coefficient",
        description=(
            "Compute C(n, k) = n!/(k!(n-k)!) for bounded 0 <= k <= n using "
            "SymPy's exact binomial."
        ),
        input_schema=_schema(
            {
                "n": _int_field(minimum=0, maximum=_MAX_N),
                "k": _int_field(minimum=0, maximum=_MAX_N),
            },
            required=("n", "k"),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("combinatorics", "binomial", "exact"),
        scope_description="bounded 0 <= k <= n",
    )


def _factorial() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import factorial

        n = int(inp["n"])
        _check(n >= 0, "factorial requires n >= 0")
        return {"n": n, "factorial": int(factorial(n))}

    return PrimitiveAdapter(
        capability_id="combinatorics.factorial.compute",
        title="Exact factorial",
        description=(
            "Compute n! for a bounded non-negative integer using SymPy's exact "
            "factorial."
        ),
        input_schema=_schema(
            {"n": _int_field(minimum=0, maximum=5000)},
            required=("n",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("combinatorics", "factorial", "exact"),
        scope_description="one bounded non-negative integer",
    )


def _permutation_count() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import factorial

        n = int(inp["n"])
        k = int(inp["k"])
        _check(0 <= k <= n, "permutation count requires 0 <= k <= n")
        return {"n": n, "k": k, "permutations": int(factorial(n) // factorial(n - k))}

    return PrimitiveAdapter(
        capability_id="combinatorics.permutation_count.compute",
        title="Exact permutation count P(n, k)",
        description=(
            "Compute P(n, k) = n!/(n-k)! for bounded 0 <= k <= n using exact "
            "integer arithmetic."
        ),
        input_schema=_schema(
            {
                "n": _int_field(minimum=0, maximum=5000),
                "k": _int_field(minimum=0, maximum=5000),
            },
            required=("n", "k"),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("combinatorics", "permutation", "exact"),
        scope_description="bounded 0 <= k <= n",
    )


def _stirling_second() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy.functions.combinatorial.numbers import stirling

        n = int(inp["n"])
        k = int(inp["k"])
        _check(n >= 0 and k >= 0, "Stirling number requires n >= 0 and k >= 0")
        return {"n": n, "k": k, "stirling_second": int(stirling(n, k, kind=2))}

    return PrimitiveAdapter(
        capability_id="combinatorics.stirling_second.compute",
        title="Stirling number of the second kind",
        description=(
            "Compute S(n, k) — the number of ways to partition n objects into k "
            "non-empty subsets — using SymPy's stirling."
        ),
        input_schema=_schema(
            {
                "n": _int_field(minimum=0, maximum=2000),
                "k": _int_field(minimum=0, maximum=2000),
            },
            required=("n", "k"),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("combinatorics", "stirling", "exact"),
        scope_description="bounded non-negative n and k",
    )


def _bell_number() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy.functions.combinatorial.numbers import bell

        n = int(inp["n"])
        _check(n >= 0, "Bell number requires n >= 0")
        return {"n": n, "bell": int(bell(n))}

    return PrimitiveAdapter(
        capability_id="combinatorics.bell_number.compute",
        title="Bell number",
        description=(
            "Compute B(n) — the number of partitions of a set of n elements — "
            "using SymPy's bell."
        ),
        input_schema=_schema(
            {"n": _int_field(minimum=0, maximum=1000)},
            required=("n",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("combinatorics", "bell", "exact"),
        scope_description="one bounded non-negative integer",
    )


def _catalan_number() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy.functions.combinatorial.numbers import catalan

        n = int(inp["n"])
        _check(n >= 0, "Catalan number requires n >= 0")
        return {"n": n, "catalan": int(catalan(n))}

    return PrimitiveAdapter(
        capability_id="combinatorics.catalan_number.compute",
        title="Catalan number",
        description=(
            "Compute C_n = (2n)!/((n+1)!n!) using SymPy's catalan for bounded "
            "non-negative n."
        ),
        input_schema=_schema(
            {"n": _int_field(minimum=0, maximum=5000)},
            required=("n",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("combinatorics", "catalan", "exact"),
        scope_description="one bounded non-negative integer",
    )


def _partition_count() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy.functions.combinatorial.numbers import partition

        n = int(inp["n"])
        _check(n >= 0, "partition count requires n >= 0")
        return {"n": n, "partition_count": int(partition(n))}

    return PrimitiveAdapter(
        capability_id="combinatorics.integer_partition.count",
        title="Integer partition count p(n)",
        description=(
            "Compute p(n) — the number of unrestricted partitions of n — using "
            "SymPy's partition for bounded non-negative n."
        ),
        input_schema=_schema(
            {"n": _int_field(minimum=0, maximum=10000)},
            required=("n",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("combinatorics", "partition", "exact"),
        scope_description="one bounded non-negative integer",
    )


def _partition_enumerate() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy.utilities.iterables import partitions

        n = int(inp["n"])
        max_parts = int(inp["max_parts"])
        _check(n >= 0, "partition enumeration requires n >= 0")
        _check(max_parts >= 1, "max_parts must be >= 1")
        result: list[list[int]] = []
        for p in partitions(n, m=max_parts):
            expanded: list[int] = []
            for part_size in sorted(p.keys(), reverse=True):
                expanded.extend([part_size] * int(p[part_size]))
            result.append(expanded)
        return {"n": n, "max_parts": max_parts, "partitions": result}

    return PrimitiveAdapter(
        capability_id="combinatorics.integer_partition.enumerate",
        title="Enumerate integer partitions",
        description=(
            "List all partitions of a bounded non-negative integer n into at "
            "most max_parts parts using SymPy's partitions generator."
        ),
        input_schema=_schema(
            {
                "n": _int_field(minimum=0, maximum=200),
                "max_parts": _int_field(minimum=1, maximum=200),
            },
            required=("n", "max_parts"),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("combinatorics", "partition", "enumerate", "exact"),
        scope_description="bounded n and max_parts",
    )
