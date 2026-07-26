"""Ten exact deterministic number-theory primitives backed by pinned SymPy 1.14.

Capabilities:
  - number_theory.gcd.compute
  - number_theory.lcm.compute
  - number_theory.primality.test
  - number_theory.prime_factorize.compute
  - number_theory.totient.compute
  - number_theory.mobius.compute
  - number_theory.divisor_sigma.compute
  - number_theory.crt.solve
  - number_theory.jacobi_symbol.compute
  - number_theory.discrete_log.bounded
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
_MAX_INT = 2**53 - 1
_MAX_LIST = 1024


def factory(kernel: JacobianKernel) -> tuple[CapabilityAdapter, ...]:
    return (
        _gcd(),
        _lcm(),
        _primality(),
        _prime_factorize(),
        _totient(),
        _mobius(),
        _divisor_sigma(),
        _crt(),
        _jacobi_symbol(),
        _discrete_log(),
    )


def _gcd() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from math import gcd

        values = [int(x) for x in inp["values"]]
        result = 0
        for v in values:
            result = gcd(result, v)
        return {"gcd": abs(result) if result else 0}

    return PrimitiveAdapter(
        capability_id="number_theory.gcd.compute",
        title="GCD of a bounded integer list",
        description=(
            "Compute the non-negative greatest common divisor of a bounded list "
            "of integers using Python's exact math.gcd."
        ),
        input_schema=_schema(
            {"values": _int_array_field(max_items=_MAX_LIST)},
            required=("values",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("number_theory", "gcd", "exact"),
        scope_description="the bounded input integer list",
    )


def _lcm() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from math import gcd

        values = [int(x) for x in inp["values"]]
        result = 1
        for v in values:
            if v == 0:
                return {"lcm": 0}
            result = abs(result * v) // gcd(result, v)
        return {"lcm": result}

    return PrimitiveAdapter(
        capability_id="number_theory.lcm.compute",
        title="LCM of a bounded integer list",
        description=(
            "Compute the non-negative least common multiple of a bounded list "
            "of integers; returns 0 if any value is 0."
        ),
        input_schema=_schema(
            {"values": _int_array_field(max_items=_MAX_LIST)},
            required=("values",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("number_theory", "lcm", "exact"),
        scope_description="the bounded input integer list",
    )


def _primality() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import isprime

        n = int(inp["n"])
        _check(n >= 0, "primality test requires n >= 0")
        return {"n": n, "is_prime": bool(isprime(n))}

    return PrimitiveAdapter(
        capability_id="number_theory.primality.test",
        title="Deterministic primality test",
        description=(
            "Test whether a bounded non-negative integer is prime using SymPy's "
            "deterministic isprime for n < 3.317e24."
        ),
        input_schema=_schema(
            {"n": _int_field(minimum=0, maximum=_MAX_INT)},
            required=("n",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("number_theory", "primality", "exact"),
        scope_description="one bounded non-negative integer",
    )


def _prime_factorize() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import factorint

        n = int(inp["n"])
        _check(n >= 2, "factorization requires n >= 2")
        factors = factorint(n)
        return {
            "n": n,
            "factors": [
                {"prime": int(p), "exponent": int(e)}
                for p, e in sorted(factors.items())
            ],
        }

    return PrimitiveAdapter(
        capability_id="number_theory.prime_factorize.compute",
        title="Exact prime factorization",
        description=(
            "Compute the exact prime factorization of a bounded integer n >= 2 "
            "using SymPy's factorint."
        ),
        input_schema=_schema(
            {"n": _int_field(minimum=2, maximum=_MAX_INT)},
            required=("n",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("number_theory", "factorization", "exact"),
        scope_description="one bounded integer n >= 2",
    )


def _totient() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import totient

        n = int(inp["n"])
        _check(n >= 1, "Euler totient requires n >= 1")
        return {"n": n, "totient": int(totient(n))}

    return PrimitiveAdapter(
        capability_id="number_theory.totient.compute",
        title="Euler's totient",
        description=(
            "Compute Euler's totient phi(n) for a bounded positive integer using "
            "SymPy's totient."
        ),
        input_schema=_schema(
            {"n": _int_field(minimum=1, maximum=_MAX_INT)},
            required=("n",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("number_theory", "totient", "exact"),
        scope_description="one bounded positive integer",
    )


def _mobius() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import mobius

        n = int(inp["n"])
        _check(n >= 1, "Mobius function requires n >= 1")
        return {"n": n, "mobius": int(mobius(n))}

    return PrimitiveAdapter(
        capability_id="number_theory.mobius.compute",
        title="Mobius function",
        description=(
            "Compute the Mobius function mu(n) for a bounded positive integer "
            "using SymPy's mobius."
        ),
        input_schema=_schema(
            {"n": _int_field(minimum=1, maximum=_MAX_INT)},
            required=("n",),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("number_theory", "mobius", "exact"),
        scope_description="one bounded positive integer",
    )


def _divisor_sigma() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import divisor_sigma

        n = int(inp["n"])
        k = int(inp["k"])
        _check(n >= 1, "divisor sigma requires n >= 1")
        return {"n": n, "k": k, "sigma": int(divisor_sigma(n, k))}

    return PrimitiveAdapter(
        capability_id="number_theory.divisor_sigma.compute",
        title="Sum of k-th powers of divisors",
        description=(
            "Compute sigma_k(n) = sum of d^k over all positive divisors d of n, "
            "using SymPy's divisor_sigma."
        ),
        input_schema=_schema(
            {
                "n": _int_field(minimum=1, maximum=_MAX_INT),
                "k": _int_field(minimum=0, maximum=64),
            },
            required=("n", "k"),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("number_theory", "divisor_sigma", "exact"),
        scope_description="one bounded positive integer and bounded exponent",
    )


def _crt() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy.ntheory.modular import crt

        remainders = [int(x) for x in inp["remainders"]]
        moduli = [int(x) for x in inp["moduli"]]
        _check(
            len(remainders) == len(moduli),
            "remainders and moduli must have equal length",
        )
        _check(all(m >= 2 for m in moduli), "each modulus must be >= 2")
        result = crt(moduli, remainders)
        if result is None:
            return {"solvable": False, "solution": None, "modulus": None}
        solution, modulus = result
        return {
            "solvable": True,
            "solution": int(solution),
            "modulus": int(modulus),
        }

    return PrimitiveAdapter(
        capability_id="number_theory.crt.solve",
        title="Chinese Remainder Theorem",
        description=(
            "Solve a bounded system of simultaneous congruences x = r_i (mod m_i) "
            "using SymPy's crt; returns unsolvable when moduli are not coprime."
        ),
        input_schema=_schema(
            {
                "remainders": _int_array_field(max_items=64),
                "moduli": _int_array_field(
                    max_items=64, item_minimum=2, item_maximum=_MAX_INT
                ),
            },
            required=("remainders", "moduli"),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("number_theory", "crt", "exact"),
        scope_description="two bounded equal-length integer lists",
    )


def _jacobi_symbol() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy import jacobi_symbol

        a = int(inp["a"])
        n = int(inp["n"])
        _check(n >= 3 and n % 2 == 1, "Jacobi symbol requires odd n >= 3")
        return {"a": a, "n": n, "jacobi": int(jacobi_symbol(a, n))}

    return PrimitiveAdapter(
        capability_id="number_theory.jacobi_symbol.compute",
        title="Jacobi symbol (a/n)",
        description=(
            "Compute the Jacobi symbol (a/n) for a bounded integer a and odd "
            "positive integer n >= 3 using SymPy's jacobi_symbol."
        ),
        input_schema=_schema(
            {
                "a": _int_field(minimum=-_MAX_INT, maximum=_MAX_INT),
                "n": _int_field(minimum=3, maximum=_MAX_INT),
            },
            required=("a", "n"),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("number_theory", "jacobi_symbol", "exact"),
        scope_description="one bounded integer and one bounded odd integer >= 3",
    )


def _discrete_log() -> PrimitiveAdapter:
    def invoke(inp: dict[str, Any]) -> dict[str, Any]:
        from sympy.ntheory import discrete_log

        n = int(inp["modulus"])
        base = int(inp["base"])
        target = int(inp["target"])
        _check(n >= 2, "discrete log requires modulus >= 2")
        _check(0 <= base < n, "base must satisfy 0 <= base < modulus")
        _check(0 <= target < n, "target must satisfy 0 <= target < modulus")
        result = discrete_log(n, target, base)
        if result is None:
            return {"solvable": False, "discrete_log": None}
        return {"solvable": True, "discrete_log": int(result)}

    return PrimitiveAdapter(
        capability_id="number_theory.discrete_log.bounded",
        title="Bounded discrete logarithm",
        description=(
            "Compute the discrete logarithm log_base(target) mod n for bounded "
            "integers using SymPy's baby-step giant-step discrete_log."
        ),
        input_schema=_schema(
            {
                "base": _int_field(minimum=0, maximum=_MAX_INT),
                "target": _int_field(minimum=0, maximum=_MAX_INT),
                "modulus": _int_field(minimum=2, maximum=_MAX_INT),
            },
            required=("base", "target", "modulus"),
        ),
        invoke=invoke,
        provider=_PROVIDER,
        tags=("number_theory", "discrete_log", "exact"),
        scope_description="bounded base, target, and modulus",
    )
