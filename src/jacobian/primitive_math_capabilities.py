"""Evidence-mined exact arithmetic and combinatorics capability adapters."""

from __future__ import annotations

import math
import platform
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from functools import reduce
from itertools import pairwise
from operator import mul
from typing import Any, Literal, cast

import sympy
from pydantic import ValidationError

from jacobian.artifacts import ArtifactService
from jacobian.capabilities import CapabilityInvocationError
from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityCompleteness,
    CapabilityCompletenessStatus,
    CapabilityDescriptor,
    CapabilityDiagnostic,
    CapabilityMode,
    CapabilityRelationship,
    CapabilityRequest,
    CapabilityResult,
    CapabilityScope,
)
from jacobian.contracts.primitive_math import (
    ChineseRemainderRequest,
    IntegerBaseDigitsResult,
    IntegerListRequest,
    IntegerModulusRequest,
    IntegerPairRequest,
    IntegerSetPairRequest,
    IntegerValueRequest,
    NonnegativeIntegerRequest,
    NonnegativePairRequest,
    PrimitiveMathArtifact,
    PrimitiveMathOutput,
    RationalPairRequest,
    RationalValueRequest,
)
from jacobian.contracts.results import ContractModel, Execution, ExecutionStatus
from jacobian.provider_runtime import known_provider_runtime
from jacobian.schema_registry import SchemaRegistry, model_schema
from jacobian.store import ArtifactStore

_BACKEND_VERSION = f"python-{platform.python_version()};sympy-{sympy.__version__}"

Compute = Callable[[ContractModel], Any]


@dataclass(frozen=True, slots=True)
class PrimitiveSpec:
    capability_id: str
    title: str
    description: str
    request_model: type[ContractModel]
    compute: Compute
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PrimitiveResources:
    artifacts: ArtifactService
    semantics_uri: str
    input_schema_uris: dict[type[ContractModel], str]
    output_schema_uri: str


def _i(value: Any) -> int:
    return int(value)


def _s(value: Any) -> str:
    return str(int(value))


def _unary(fn: Callable[[int], Any]) -> Compute:
    return lambda request: fn(_i(cast(IntegerValueRequest, request).value))


def _nonnegative(fn: Callable[[int], Any]) -> Compute:
    return lambda request: fn(cast(NonnegativeIntegerRequest, request).n)


def _pair(fn: Callable[[int, int], Any]) -> Compute:
    def compute(request: ContractModel) -> Any:
        pair = cast(IntegerPairRequest, request)
        return fn(_i(pair.left), _i(pair.right))

    return compute


def _nk(fn: Callable[[int, int], Any]) -> Compute:
    return lambda request: fn(
        cast(NonnegativePairRequest, request).n,
        cast(NonnegativePairRequest, request).k,
    )


def _values(request: ContractModel) -> list[int]:
    return [_i(value) for value in cast(IntegerListRequest, request).values]


def _fraction(value: Any) -> Fraction:
    return Fraction(int(value.num), int(value.den))


def _rational(value: Fraction | sympy.Rational) -> dict[str, str]:
    return {"num": str(value.numerator), "den": str(value.denominator)}


def _rational_unary(fn: Callable[[Fraction], Any]) -> Compute:
    return lambda request: fn(_fraction(cast(RationalValueRequest, request).value))


def _rational_pair(fn: Callable[[Fraction, Fraction], Any]) -> Compute:
    def compute(request: ContractModel) -> Any:
        pair = cast(RationalPairRequest, request)
        return fn(_fraction(pair.left), _fraction(pair.right))

    return compute


def _factorization(value: int) -> dict[str, str]:
    if value == 0:
        raise ValueError("zero has no finite prime factorization")
    return {
        str(prime): str(power) for prime, power in sympy.factorint(abs(value)).items()
    }


def _extended_gcd(left: int, right: int) -> dict[str, str]:
    x, y, divisor = sympy.gcdex(left, right)
    return {"gcd": _s(divisor), "left_coefficient": _s(x), "right_coefficient": _s(y)}


def _previous_prime(n: int) -> str:
    if n <= 2:
        raise ValueError("previous prime requires n greater than 2")
    return _s(sympy.prevprime(n))


def _valuation(left: int, right: int) -> str:
    if left == 0 or abs(right) < 2 or not sympy.isprime(abs(right)):
        raise ValueError("valuation requires nonzero left and prime absolute right")
    return _s(sympy.multiplicity(abs(right), abs(left)))


def _modular_inverse(request: ContractModel) -> str:
    modular = cast(IntegerModulusRequest, request)
    return _s(sympy.mod_inverse(_i(modular.value), modular.modulus))


def _multiplicative_order(request: ContractModel) -> str:
    modular = cast(IntegerModulusRequest, request)
    value, modulus = _i(modular.value), modular.modulus
    if math.gcd(value, modulus) != 1:
        raise ValueError("multiplicative order requires coprime value and modulus")
    return _s(sympy.n_order(value, modulus))


def _quadratic_residues(request: ContractModel) -> list[str]:
    modulus = cast(IntegerModulusRequest, request).modulus
    return [
        str(value)
        for value in sympy.ntheory.residue_ntheory.quadratic_residues(modulus)
    ]


def _crt(request: ContractModel) -> dict[str, str]:
    system = cast(ChineseRemainderRequest, request)
    value, modulus = sympy.ntheory.modular.solve_congruence(
        *zip(
            system.residues,
            system.moduli,
            strict=True,
        ),
        check=True,
    ) or (None, None)
    if value is None:
        raise ValueError("congruence system is inconsistent")
    return {"residue": _s(value), "modulus": _s(modulus)}


def _divisors(value: int, *, proper: bool = False) -> list[str]:
    if value == 0:
        raise ValueError("zero has infinitely many divisors")
    result = list(sympy.divisors(abs(value), proper=proper))
    return [_s(item) for item in result]


def _factorial(n: int) -> str:
    return _s(math.factorial(n))


def _double_factorial(n: int) -> str:
    return _s(sympy.factorial2(n))


def _stirling(n: int, k: int, *, kind: int) -> str:
    return _s(sympy.functions.combinatorial.numbers.stirling(n, k, kind=kind))


def _multinomial(request: ContractModel) -> str:
    values = _values(request)
    if any(value < 0 for value in values):
        raise ValueError("multinomial parts must be nonnegative")
    numerator = math.factorial(sum(values))
    denominator = reduce(mul, (math.factorial(value) for value in values), 1)
    return str(numerator // denominator)


def _frequency(request: ContractModel) -> dict[str, str]:
    return {
        str(key): str(value) for key, value in sorted(Counter(_values(request)).items())
    }


def _prefix_sums(request: ContractModel) -> list[str]:
    total = 0
    result = []
    for value in _values(request):
        total += value
        result.append(str(total))
    return result


def _differences(request: ContractModel) -> list[str]:
    values = _values(request)
    return [str(right - left) for left, right in pairwise(values)]


def _prefix_products(request: ContractModel) -> list[str]:
    total = 1
    result = []
    for value in _values(request):
        total *= value
        result.append(str(total))
    return result


def _is_arithmetic(request: ContractModel) -> bool:
    differences = [b - a for a, b in pairwise(_values(request))]
    return len(set(differences)) <= 1


def _is_geometric(request: ContractModel) -> bool:
    values = _values(request)
    if len(values) < 2:
        return True
    if values[0] == 0:
        return all(value == 0 for value in values)
    ratio = Fraction(values[1], values[0])
    return all(
        right * ratio.denominator == left * ratio.numerator
        for left, right in pairwise(values)
    )


def _integer_root(n: int, k: int) -> dict[str, Any]:
    if k < 1:
        raise ValueError("root degree must be positive")
    if n < 0 and k % 2 == 0:
        raise ValueError("even root of a negative integer is not integral-real")
    root, exact = sympy.integer_nthroot(abs(n), k)
    return {"root": str(-root if n < 0 else root), "exact": exact}


def _base_digits(request: ContractModel) -> IntegerBaseDigitsResult:
    modular = cast(IntegerModulusRequest, request)
    value, base = _i(modular.value), modular.modulus
    digits = sympy.ntheory.digits(abs(value), base)[1:]
    sign: Literal[-1, 0, 1] = -1 if value < 0 else (1 if value > 0 else 0)
    return IntegerBaseDigitsResult(
        sign=sign,
        base=base,
        digits=tuple(str(digit) for digit in digits),
    )


def _set_pair(request: ContractModel) -> tuple[set[int], set[int]]:
    pair = cast(IntegerSetPairRequest, request)
    return (
        {_i(value) for value in pair.left},
        {_i(value) for value in pair.right},
    )


def _set_values(
    fn: Callable[[set[int], set[int]], set[int]],
) -> Compute:
    return lambda request: [str(value) for value in sorted(fn(*_set_pair(request)))]


def _set_predicate(fn: Callable[[set[int], set[int]], bool]) -> Compute:
    return lambda request: fn(*_set_pair(request))


def _mean(request: ContractModel) -> dict[str, str]:
    values = _values(request)
    return _rational(Fraction(sum(values), len(values)))


def _median(request: ContractModel) -> dict[str, str]:
    values = sorted(_values(request))
    middle = len(values) // 2
    if len(values) % 2:
        return _rational(Fraction(values[middle]))
    return _rational(Fraction(values[middle - 1] + values[middle], 2))


def _running(request: ContractModel, fn: Callable[[int, int], int]) -> list[str]:
    values = _values(request)
    result = [values[0]]
    for value in values[1:]:
        result.append(fn(result[-1], value))
    return [str(value) for value in result]


def _continued_fraction(value: Fraction) -> list[str]:
    rational = sympy.Rational(value.numerator, value.denominator)
    return [str(term) for term in sympy.continued_fraction(rational)]


def _spec(
    capability_id: str,
    title: str,
    description: str,
    request_model: type[ContractModel],
    compute: Compute,
    *tags: str,
) -> PrimitiveSpec:
    return PrimitiveSpec(
        capability_id, title, description, request_model, compute, tags
    )


SPECS: tuple[PrimitiveSpec, ...] = (
    _spec(
        "integer.compute.absolute_value",
        "Compute integer absolute value",
        "Compute the exact absolute value of one integer.",
        IntegerValueRequest,
        _unary(lambda n: str(abs(n))),
        "integer",
        "exact",
    ),
    _spec(
        "integer.compute.sign",
        "Compute integer sign",
        "Compute -1, 0, or 1 according to one integer's sign.",
        IntegerValueRequest,
        _unary(lambda n: str((n > 0) - (n < 0))),
        "integer",
        "exact",
    ),
    _spec(
        "integer.compute.gcd",
        "Compute integer gcd",
        "Compute the nonnegative greatest common divisor of two integers.",
        IntegerPairRequest,
        _pair(lambda a, b: str(math.gcd(a, b))),
        "number-theory",
        "divisibility",
    ),
    _spec(
        "integer.compute.lcm",
        "Compute integer lcm",
        "Compute the nonnegative least common multiple of two integers.",
        IntegerPairRequest,
        _pair(lambda a, b: str(math.lcm(a, b))),
        "number-theory",
        "divisibility",
    ),
    _spec(
        "integer.compute.extended_gcd",
        "Compute Bézout coefficients",
        "Compute a gcd and exact Bézout coefficients for two integers.",
        IntegerPairRequest,
        _pair(_extended_gcd),
        "number-theory",
        "certificate",
    ),
    _spec(
        "integer.compute.divisors",
        "Enumerate positive divisors",
        "Enumerate every positive divisor of one nonzero integer.",
        IntegerValueRequest,
        _unary(_divisors),
        "number-theory",
        "enumeration",
    ),
    _spec(
        "integer.compute.proper_divisors",
        "Enumerate proper divisors",
        "Enumerate every positive proper divisor of one nonzero integer.",
        IntegerValueRequest,
        _unary(lambda n: _divisors(n, proper=True)),
        "number-theory",
        "enumeration",
    ),
    _spec(
        "integer.compute.prime_factorization",
        "Factor an integer",
        "Compute the complete prime-power factorization of one nonzero integer.",
        IntegerValueRequest,
        _unary(_factorization),
        "number-theory",
        "factorization",
    ),
    _spec(
        "integer.decide.prime",
        "Decide integer primality",
        "Decide whether one integer is prime.",
        IntegerValueRequest,
        _unary(sympy.isprime),
        "number-theory",
        "predicate",
    ),
    _spec(
        "integer.compute.next_prime",
        "Compute next prime",
        "Compute the least prime strictly greater than n.",
        NonnegativeIntegerRequest,
        _nonnegative(lambda n: _s(sympy.nextprime(n))),
        "number-theory",
        "prime",
    ),
    _spec(
        "integer.compute.previous_prime",
        "Compute previous prime",
        "Compute the greatest prime strictly below n.",
        NonnegativeIntegerRequest,
        _nonnegative(_previous_prime),
        "number-theory",
        "prime",
    ),
    _spec(
        "integer.compute.euler_totient",
        "Compute Euler totient",
        "Count residues coprime to one positive integer.",
        NonnegativeIntegerRequest,
        _nonnegative(
            lambda n: (
                _s(sympy.totient(n))
                if n
                else (_ for _ in ()).throw(ValueError("totient requires positive n"))
            )
        ),
        "number-theory",
        "arithmetic-function",
    ),
    _spec(
        "integer.compute.mobius",
        "Compute Möbius value",
        "Compute the Möbius arithmetic function of one positive integer.",
        NonnegativeIntegerRequest,
        _nonnegative(
            lambda n: (
                _s(sympy.mobius(n))
                if n
                else (_ for _ in ()).throw(ValueError("Möbius requires positive n"))
            )
        ),
        "number-theory",
        "arithmetic-function",
    ),
    _spec(
        "integer.compute.radical",
        "Compute integer radical",
        "Compute the product of distinct prime divisors of one positive integer.",
        NonnegativeIntegerRequest,
        _nonnegative(
            lambda n: (
                _s(math.prod(sympy.factorint(n)))
                if n
                else (_ for _ in ()).throw(ValueError("radical requires positive n"))
            )
        ),
        "number-theory",
        "arithmetic-function",
    ),
    _spec(
        "integer.compute.divisor_count",
        "Count positive divisors",
        "Compute the number of positive divisors of one positive integer.",
        NonnegativeIntegerRequest,
        _nonnegative(
            lambda n: (
                _s(sympy.divisor_count(n))
                if n
                else (_ for _ in ()).throw(
                    ValueError("divisor count requires positive n")
                )
            )
        ),
        "number-theory",
        "divisibility",
    ),
    _spec(
        "integer.compute.divisor_sum",
        "Sum positive divisors",
        "Compute the sum of every positive divisor of one positive integer.",
        NonnegativeIntegerRequest,
        _nonnegative(
            lambda n: (
                _s(sympy.divisor_sigma(n))
                if n
                else (_ for _ in ()).throw(
                    ValueError("divisor sum requires positive n")
                )
            )
        ),
        "number-theory",
        "divisibility",
    ),
    _spec(
        "integer.compute.aliquot_sum",
        "Compute aliquot sum",
        "Compute the sum of positive proper divisors of one positive integer.",
        NonnegativeIntegerRequest,
        _nonnegative(
            lambda n: (
                _s(sympy.divisor_sigma(n) - n)
                if n
                else (_ for _ in ()).throw(
                    ValueError("aliquot sum requires positive n")
                )
            )
        ),
        "number-theory",
        "divisibility",
    ),
    _spec(
        "integer.compute.valuation",
        "Compute prime-adic valuation",
        "Compute the exponent of a prime in one nonzero integer.",
        IntegerPairRequest,
        _pair(_valuation),
        "number-theory",
        "valuation",
    ),
    _spec(
        "modular.compute.inverse",
        "Compute modular inverse",
        "Compute the least nonnegative inverse of a value modulo m.",
        IntegerModulusRequest,
        _modular_inverse,
        "number-theory",
        "modular",
    ),
    _spec(
        "modular.compute.multiplicative_order",
        "Compute multiplicative order",
        "Compute the multiplicative order of a unit modulo m.",
        IntegerModulusRequest,
        _multiplicative_order,
        "number-theory",
        "modular",
    ),
    _spec(
        "modular.enumerate.quadratic_residues",
        "Enumerate quadratic residues",
        "Enumerate all quadratic residues modulo m.",
        IntegerModulusRequest,
        _quadratic_residues,
        "number-theory",
        "modular",
        "enumeration",
    ),
    _spec(
        "modular.solve.chinese_remainder",
        "Solve congruence system",
        "Solve a finite compatible system of integer congruences.",
        ChineseRemainderRequest,
        _crt,
        "number-theory",
        "modular",
    ),
    _spec(
        "combinatorics.compute.factorial",
        "Compute factorial",
        "Compute n factorial exactly.",
        NonnegativeIntegerRequest,
        _nonnegative(_factorial),
        "combinatorics",
        "counting",
    ),
    _spec(
        "combinatorics.compute.double_factorial",
        "Compute double factorial",
        "Compute n double factorial exactly.",
        NonnegativeIntegerRequest,
        _nonnegative(_double_factorial),
        "combinatorics",
        "counting",
    ),
    _spec(
        "combinatorics.compute.derangements",
        "Count derangements",
        "Count fixed-point-free permutations of n labeled objects.",
        NonnegativeIntegerRequest,
        _nonnegative(lambda n: _s(sympy.subfactorial(n))),
        "combinatorics",
        "counting",
    ),
    _spec(
        "combinatorics.compute.binomial",
        "Compute binomial coefficient",
        "Count k-element subsets of an n-element set.",
        NonnegativePairRequest,
        _nk(lambda n, k: _s(math.comb(n, k)) if k <= n else "0"),
        "combinatorics",
        "counting",
    ),
    _spec(
        "combinatorics.compute.multinomial",
        "Compute multinomial coefficient",
        "Count arrangements with the supplied nonnegative part sizes.",
        IntegerListRequest,
        _multinomial,
        "combinatorics",
        "counting",
    ),
    _spec(
        "combinatorics.compute.permutations",
        "Count partial permutations",
        "Count ordered selections of k objects from n.",
        NonnegativePairRequest,
        _nk(lambda n, k: _s(math.perm(n, k)) if k <= n else "0"),
        "combinatorics",
        "counting",
    ),
    _spec(
        "combinatorics.compute.stirling_first",
        "Compute Stirling number of first kind",
        "Count permutations of n elements with k cycles, unsigned.",
        NonnegativePairRequest,
        _nk(lambda n, k: _stirling(n, k, kind=1)),
        "combinatorics",
        "partition",
    ),
    _spec(
        "combinatorics.compute.stirling_second",
        "Compute Stirling number of second kind",
        "Count partitions of n labeled elements into k nonempty blocks.",
        NonnegativePairRequest,
        _nk(lambda n, k: _stirling(n, k, kind=2)),
        "combinatorics",
        "partition",
    ),
    _spec(
        "combinatorics.compute.bell",
        "Compute Bell number",
        "Count set partitions of n labeled elements.",
        NonnegativeIntegerRequest,
        _nonnegative(lambda n: _s(sympy.bell(n))),
        "combinatorics",
        "partition",
    ),
    _spec(
        "combinatorics.compute.catalan",
        "Compute Catalan number",
        "Compute the nth Catalan number.",
        NonnegativeIntegerRequest,
        _nonnegative(lambda n: _s(sympy.catalan(n))),
        "combinatorics",
        "counting",
    ),
    _spec(
        "combinatorics.compute.partition_number",
        "Compute partition number",
        "Count unordered additive partitions of n.",
        NonnegativeIntegerRequest,
        _nonnegative(lambda n: _s(sympy.partition(n))),
        "combinatorics",
        "partition",
    ),
    _spec(
        "combinatorics.compute.fibonacci",
        "Compute Fibonacci number",
        "Compute the nth Fibonacci number exactly.",
        NonnegativeIntegerRequest,
        _nonnegative(lambda n: _s(sympy.fibonacci(n))),
        "combinatorics",
        "sequence",
    ),
    _spec(
        "combinatorics.compute.lucas",
        "Compute Lucas number",
        "Compute the nth Lucas number exactly.",
        NonnegativeIntegerRequest,
        _nonnegative(lambda n: _s(sympy.lucas(n))),
        "combinatorics",
        "sequence",
    ),
    _spec(
        "combinatorics.compute.motzkin",
        "Compute Motzkin number",
        "Compute the nth Motzkin path count.",
        NonnegativeIntegerRequest,
        _nonnegative(lambda n: _s(sympy.motzkin(n))),
        "combinatorics",
        "counting",
    ),
    _spec(
        "combinatorics.compute.bernoulli",
        "Compute Bernoulli number",
        "Compute the nth Bernoulli number as a reduced rational.",
        NonnegativeIntegerRequest,
        _nonnegative(
            lambda n: {
                "num": str(sympy.bernoulli(n).p),
                "den": str(sympy.bernoulli(n).q),
            }
        ),
        "combinatorics",
        "sequence",
    ),
    _spec(
        "combinatorics.compute.central_binomial",
        "Compute central binomial coefficient",
        "Compute binomial(2n,n) exactly.",
        NonnegativeIntegerRequest,
        _nonnegative(lambda n: _s(math.comb(2 * n, n))),
        "combinatorics",
        "counting",
    ),
    _spec(
        "combinatorics.compute.compositions",
        "Count positive compositions",
        "Count ordered positive-part compositions of n into k parts.",
        NonnegativePairRequest,
        _nk(
            lambda n, k: (
                "1"
                if n == k == 0
                else (_s(math.comb(n - 1, k - 1)) if 0 < k <= n else "0")
            )
        ),
        "combinatorics",
        "counting",
    ),
    _spec(
        "sequence.compute.sum",
        "Sum integer sequence",
        "Compute the exact sum of a finite integer sequence.",
        IntegerListRequest,
        lambda r: str(sum(_values(r))),
        "sequence",
        "exact",
    ),
    _spec(
        "sequence.compute.product",
        "Multiply integer sequence",
        "Compute the exact product of a finite integer sequence.",
        IntegerListRequest,
        lambda r: str(math.prod(_values(r))),
        "sequence",
        "exact",
    ),
    _spec(
        "sequence.compute.gcd",
        "Compute sequence gcd",
        "Compute the gcd of every value in a finite integer sequence.",
        IntegerListRequest,
        lambda r: str(reduce(math.gcd, _values(r))),
        "sequence",
        "divisibility",
    ),
    _spec(
        "sequence.compute.lcm",
        "Compute sequence lcm",
        "Compute the lcm of every value in a finite integer sequence.",
        IntegerListRequest,
        lambda r: str(reduce(math.lcm, _values(r), 1)),
        "sequence",
        "divisibility",
    ),
    _spec(
        "sequence.compute.minimum",
        "Compute sequence minimum",
        "Compute the least value in a finite integer sequence.",
        IntegerListRequest,
        lambda r: str(min(_values(r))),
        "sequence",
        "order",
    ),
    _spec(
        "sequence.compute.maximum",
        "Compute sequence maximum",
        "Compute the greatest value in a finite integer sequence.",
        IntegerListRequest,
        lambda r: str(max(_values(r))),
        "sequence",
        "order",
    ),
    _spec(
        "sequence.compute.prefix_sums",
        "Compute prefix sums",
        "Compute every nonempty prefix sum of a finite integer sequence.",
        IntegerListRequest,
        _prefix_sums,
        "sequence",
        "transform",
    ),
    _spec(
        "sequence.compute.first_differences",
        "Compute first differences",
        "Compute adjacent first differences of a finite integer sequence.",
        IntegerListRequest,
        _differences,
        "sequence",
        "transform",
    ),
    _spec(
        "sequence.compute.prefix_products",
        "Compute prefix products",
        "Compute every nonempty prefix product of a finite integer sequence.",
        IntegerListRequest,
        _prefix_products,
        "sequence",
        "transform",
    ),
    _spec(
        "sequence.compute.frequencies",
        "Compute value frequencies",
        "Count each distinct value in a finite integer sequence.",
        IntegerListRequest,
        _frequency,
        "sequence",
        "counting",
    ),
    _spec(
        "sequence.transform.sorted_unique",
        "Sort and deduplicate sequence",
        "Return the strictly increasing values occurring in a finite integer sequence.",
        IntegerListRequest,
        lambda r: [str(v) for v in sorted(set(_values(r)))],
        "sequence",
        "transform",
    ),
    _spec(
        "sequence.decide.arithmetic",
        "Decide arithmetic progression",
        "Decide whether consecutive terms have one common difference.",
        IntegerListRequest,
        _is_arithmetic,
        "sequence",
        "predicate",
    ),
    _spec(
        "sequence.decide.geometric",
        "Decide geometric progression",
        "Decide whether a finite integer sequence has a consistent rational ratio.",
        IntegerListRequest,
        _is_geometric,
        "sequence",
        "predicate",
    ),
)

SPECS += (
    _spec(
        "integer.decide.square",
        "Decide perfect square",
        "Decide whether a nonnegative integer is a square.",
        NonnegativeIntegerRequest,
        _nonnegative(lambda n: math.isqrt(n) ** 2 == n),
        "number-theory",
        "predicate",
    ),
    _spec(
        "integer.decide.squarefree",
        "Decide squarefreeness",
        "Decide whether a positive integer has no squared prime divisor.",
        NonnegativeIntegerRequest,
        _nonnegative(
            lambda n: all(power == 1 for power in sympy.factorint(n)) if n else False
        ),
        "number-theory",
        "predicate",
    ),
    _spec(
        "integer.decide.perfect",
        "Decide perfect number",
        "Decide whether a positive integer equals its aliquot sum.",
        NonnegativeIntegerRequest,
        _nonnegative(lambda n: bool(n and sympy.divisor_sigma(n) - n == n)),
        "number-theory",
        "predicate",
    ),
    _spec(
        "integer.decide.abundant",
        "Decide abundant number",
        "Decide whether a positive integer has aliquot sum greater than itself.",
        NonnegativeIntegerRequest,
        _nonnegative(lambda n: bool(n and sympy.divisor_sigma(n) - n > n)),
        "number-theory",
        "predicate",
    ),
    _spec(
        "integer.decide.deficient",
        "Decide deficient number",
        "Decide whether a positive integer has aliquot sum below itself.",
        NonnegativeIntegerRequest,
        _nonnegative(lambda n: bool(n and sympy.divisor_sigma(n) - n < n)),
        "number-theory",
        "predicate",
    ),
    _spec(
        "integer.decide.even",
        "Decide evenness",
        "Decide whether one integer is divisible by two.",
        IntegerValueRequest,
        _unary(lambda n: n % 2 == 0),
        "integer",
        "predicate",
    ),
    _spec(
        "integer.decide.odd",
        "Decide oddness",
        "Decide whether one integer is not divisible by two.",
        IntegerValueRequest,
        _unary(lambda n: n % 2 != 0),
        "integer",
        "predicate",
    ),
    _spec(
        "integer.decide.coprime",
        "Decide coprimality",
        "Decide whether two integers have gcd one.",
        IntegerPairRequest,
        _pair(lambda a, b: math.gcd(a, b) == 1),
        "number-theory",
        "predicate",
    ),
    _spec(
        "integer.decide.divides",
        "Decide divisibility",
        "Decide whether the first nonzero integer divides the second.",
        IntegerPairRequest,
        _pair(
            lambda a, b: (
                b % a == 0
                if a
                else (_ for _ in ()).throw(ValueError("divisor must be nonzero"))
            )
        ),
        "number-theory",
        "predicate",
    ),
    _spec(
        "integer.compute.nth_root",
        "Compute integer nth root",
        "Compute floor nth root and whether it is exact.",
        NonnegativePairRequest,
        _nk(_integer_root),
        "number-theory",
        "root",
    ),
    _spec(
        "integer.compute.prime_count",
        "Count primes through n",
        "Count primes not exceeding one nonnegative integer.",
        NonnegativeIntegerRequest,
        _nonnegative(lambda n: _s(sympy.primepi(n))),
        "number-theory",
        "prime",
    ),
    _spec(
        "integer.compute.nth_prime",
        "Compute nth prime",
        "Compute the nth prime using one-based indexing.",
        NonnegativeIntegerRequest,
        _nonnegative(
            lambda n: (
                _s(sympy.prime(n))
                if n
                else (_ for _ in ()).throw(ValueError("prime index must be positive"))
            )
        ),
        "number-theory",
        "prime",
    ),
    _spec(
        "integer.compute.primorial",
        "Compute primorial",
        "Compute the product of the first n primes.",
        NonnegativeIntegerRequest,
        _nonnegative(lambda n: _s(sympy.primorial(n))),
        "number-theory",
        "prime",
    ),
    _spec(
        "integer.compute.decimal_digit_sum",
        "Compute decimal digit sum",
        "Sum decimal digits of one integer's absolute value.",
        IntegerValueRequest,
        _unary(lambda n: str(sum(int(digit) for digit in str(abs(n))))),
        "integer",
        "representation",
    ),
    _spec(
        "integer.compute.decimal_digit_count",
        "Count decimal digits",
        "Count decimal digits in one integer's absolute value.",
        IntegerValueRequest,
        _unary(lambda n: str(len(str(abs(n))))),
        "integer",
        "representation",
    ),
    _spec(
        "integer.transform.base_digits",
        "Expand integer in a base",
        "Return positional digits of one integer in a base from 2 through 1,000,000.",
        IntegerModulusRequest,
        _base_digits,
        "integer",
        "representation",
    ),
    _spec(
        "rational.compute.reciprocal",
        "Compute rational reciprocal",
        "Compute the reduced reciprocal of one nonzero rational.",
        RationalValueRequest,
        _rational_unary(
            lambda value: (
                _rational(1 / value)
                if value
                else (_ for _ in ()).throw(ValueError("zero has no reciprocal"))
            )
        ),
        "rational",
        "exact",
    ),
    _spec(
        "rational.compute.negation",
        "Negate rational",
        "Compute the exact additive inverse of one rational.",
        RationalValueRequest,
        _rational_unary(lambda value: _rational(-value)),
        "rational",
        "exact",
    ),
    _spec(
        "rational.compute.absolute_value",
        "Compute rational absolute value",
        "Compute the exact absolute value of one rational.",
        RationalValueRequest,
        _rational_unary(lambda value: _rational(abs(value))),
        "rational",
        "exact",
    ),
    _spec(
        "rational.compute.sum",
        "Add rationals",
        "Compute the reduced sum of two rationals.",
        RationalPairRequest,
        _rational_pair(lambda left, right: _rational(left + right)),
        "rational",
        "exact",
    ),
    _spec(
        "rational.compute.difference",
        "Subtract rationals",
        "Compute the reduced difference of two rationals.",
        RationalPairRequest,
        _rational_pair(lambda left, right: _rational(left - right)),
        "rational",
        "exact",
    ),
    _spec(
        "rational.compute.product",
        "Multiply rationals",
        "Compute the reduced product of two rationals.",
        RationalPairRequest,
        _rational_pair(lambda left, right: _rational(left * right)),
        "rational",
        "exact",
    ),
    _spec(
        "rational.compute.quotient",
        "Divide rationals",
        "Compute the reduced quotient of two rationals.",
        RationalPairRequest,
        _rational_pair(
            lambda left, right: (
                _rational(left / right)
                if right
                else (_ for _ in ()).throw(ValueError("division by zero"))
            )
        ),
        "rational",
        "exact",
    ),
    _spec(
        "rational.compute.minimum",
        "Compute rational minimum",
        "Return the lesser of two exact rationals.",
        RationalPairRequest,
        _rational_pair(lambda left, right: _rational(min(left, right))),
        "rational",
        "order",
    ),
    _spec(
        "rational.compute.maximum",
        "Compute rational maximum",
        "Return the greater of two exact rationals.",
        RationalPairRequest,
        _rational_pair(lambda left, right: _rational(max(left, right))),
        "rational",
        "order",
    ),
    _spec(
        "rational.compute.floor",
        "Floor rational",
        "Compute the greatest integer not exceeding one rational.",
        RationalValueRequest,
        _rational_unary(lambda value: str(math.floor(value))),
        "rational",
        "rounding",
    ),
    _spec(
        "rational.compute.ceiling",
        "Ceil rational",
        "Compute the least integer not below one rational.",
        RationalValueRequest,
        _rational_unary(lambda value: str(math.ceil(value))),
        "rational",
        "rounding",
    ),
    _spec(
        "rational.compute.continued_fraction",
        "Expand rational continued fraction",
        "Compute the finite simple continued fraction of one rational.",
        RationalValueRequest,
        _rational_unary(_continued_fraction),
        "rational",
        "representation",
    ),
    _spec(
        "rational.decide.equal",
        "Decide rational equality",
        "Decide exact equality of two reduced rationals.",
        RationalPairRequest,
        _rational_pair(lambda left, right: left == right),
        "rational",
        "predicate",
    ),
    _spec(
        "rational.decide.less_than",
        "Compare rationals",
        "Decide whether the first rational is strictly less than the second.",
        RationalPairRequest,
        _rational_pair(lambda left, right: left < right),
        "rational",
        "predicate",
    ),
    _spec(
        "finite_set.compute.union",
        "Compute finite-set union",
        "Return the sorted union of two finite integer sets.",
        IntegerSetPairRequest,
        _set_values(set.union),
        "finite-set",
        "exact",
    ),
    _spec(
        "finite_set.compute.intersection",
        "Compute finite-set intersection",
        "Return the sorted intersection of two finite integer sets.",
        IntegerSetPairRequest,
        _set_values(set.intersection),
        "finite-set",
        "exact",
    ),
    _spec(
        "finite_set.compute.difference",
        "Compute finite-set difference",
        "Return elements in the first finite set but not the second.",
        IntegerSetPairRequest,
        _set_values(set.difference),
        "finite-set",
        "exact",
    ),
    _spec(
        "finite_set.compute.symmetric_difference",
        "Compute symmetric difference",
        "Return elements occurring in exactly one of two finite integer sets.",
        IntegerSetPairRequest,
        _set_values(set.symmetric_difference),
        "finite-set",
        "exact",
    ),
    _spec(
        "finite_set.decide.subset",
        "Decide subset relation",
        "Decide whether every left-set element occurs in the right set.",
        IntegerSetPairRequest,
        _set_predicate(set.issubset),
        "finite-set",
        "predicate",
    ),
    _spec(
        "finite_set.decide.proper_subset",
        "Decide proper subset",
        "Decide whether the left set is a strict subset of the right set.",
        IntegerSetPairRequest,
        _set_predicate(lambda left, right: left < right),
        "finite-set",
        "predicate",
    ),
    _spec(
        "finite_set.decide.disjoint",
        "Decide disjointness",
        "Decide whether two finite integer sets have empty intersection.",
        IntegerSetPairRequest,
        _set_predicate(set.isdisjoint),
        "finite-set",
        "predicate",
    ),
    _spec(
        "finite_set.compute.left_cardinality",
        "Count left finite set",
        "Count distinct elements in the left finite integer set.",
        IntegerSetPairRequest,
        lambda request: str(len(_set_pair(request)[0])),
        "finite-set",
        "counting",
    ),
    _spec(
        "finite_set.compute.intersection_cardinality",
        "Count set intersection",
        "Count common elements of two finite integer sets.",
        IntegerSetPairRequest,
        lambda request: str(len(set.intersection(*_set_pair(request)))),
        "finite-set",
        "counting",
    ),
    _spec(
        "finite_set.compute.union_cardinality",
        "Count set union",
        "Count distinct elements occurring in either finite integer set.",
        IntegerSetPairRequest,
        lambda request: str(len(set.union(*_set_pair(request)))),
        "finite-set",
        "counting",
    ),
    _spec(
        "sequence.compute.mean",
        "Compute sequence mean",
        "Compute the reduced arithmetic mean of a finite integer sequence.",
        IntegerListRequest,
        _mean,
        "sequence",
        "statistic",
    ),
    _spec(
        "sequence.compute.median",
        "Compute sequence median",
        "Compute the reduced median of a finite integer sequence.",
        IntegerListRequest,
        _median,
        "sequence",
        "statistic",
    ),
    _spec(
        "sequence.compute.range",
        "Compute sequence range",
        "Compute maximum minus minimum for a finite integer sequence.",
        IntegerListRequest,
        lambda request: str(max(_values(request)) - min(_values(request))),
        "sequence",
        "statistic",
    ),
    _spec(
        "sequence.compute.distinct_count",
        "Count distinct sequence values",
        "Count distinct values in a finite integer sequence.",
        IntegerListRequest,
        lambda request: str(len(set(_values(request)))),
        "sequence",
        "counting",
    ),
    _spec(
        "sequence.transform.sort",
        "Sort integer sequence",
        "Return a nondecreasing ordering retaining multiplicities.",
        IntegerListRequest,
        lambda request: [str(value) for value in sorted(_values(request))],
        "sequence",
        "transform",
    ),
    _spec(
        "sequence.transform.reverse",
        "Reverse integer sequence",
        "Return the finite integer sequence in reverse order.",
        IntegerListRequest,
        lambda request: [str(value) for value in reversed(_values(request))],
        "sequence",
        "transform",
    ),
    _spec(
        "sequence.compute.prefix_minima",
        "Compute prefix minima",
        "Compute the minimum of every nonempty prefix.",
        IntegerListRequest,
        lambda request: _running(request, min),
        "sequence",
        "transform",
    ),
    _spec(
        "sequence.compute.prefix_maxima",
        "Compute prefix maxima",
        "Compute the maximum of every nonempty prefix.",
        IntegerListRequest,
        lambda request: _running(request, max),
        "sequence",
        "transform",
    ),
    _spec(
        "sequence.compute.prefix_gcds",
        "Compute prefix gcds",
        "Compute the gcd of every nonempty prefix.",
        IntegerListRequest,
        lambda request: _running(request, math.gcd),
        "sequence",
        "divisibility",
    ),
    _spec(
        "sequence.compute.prefix_lcms",
        "Compute prefix lcms",
        "Compute the lcm of every nonempty prefix.",
        IntegerListRequest,
        lambda request: _running(request, math.lcm),
        "sequence",
        "divisibility",
    ),
    _spec(
        "sequence.compute.second_differences",
        "Compute second differences",
        "Compute adjacent differences of the first-difference sequence.",
        IntegerListRequest,
        lambda request: [
            str(right - left)
            for left, right in pairwise([b - a for a, b in pairwise(_values(request))])
        ],
        "sequence",
        "transform",
    ),
    _spec(
        "sequence.transform.parities",
        "Compute parity sequence",
        "Return 0 for even and 1 for odd at each position.",
        IntegerListRequest,
        lambda request: [str(value % 2) for value in _values(request)],
        "sequence",
        "transform",
    ),
    _spec(
        "sequence.transform.signs",
        "Compute sign sequence",
        "Return -1, 0, or 1 for each sequence value.",
        IntegerListRequest,
        lambda request: [str((value > 0) - (value < 0)) for value in _values(request)],
        "sequence",
        "transform",
    ),
    _spec(
        "sequence.compute.zero_indices",
        "Locate zero terms",
        "Return zero-based indices whose sequence value is zero.",
        IntegerListRequest,
        lambda request: [
            str(index) for index, value in enumerate(_values(request)) if value == 0
        ],
        "sequence",
        "search",
    ),
    _spec(
        "sequence.decide.nondecreasing",
        "Decide nondecreasing order",
        "Decide whether every term is at least its predecessor.",
        IntegerListRequest,
        lambda request: all(
            left <= right for left, right in pairwise(_values(request))
        ),
        "sequence",
        "predicate",
    ),
    _spec(
        "sequence.decide.strictly_increasing",
        "Decide strict increase",
        "Decide whether every term is greater than its predecessor.",
        IntegerListRequest,
        lambda request: all(left < right for left, right in pairwise(_values(request))),
        "sequence",
        "predicate",
    ),
)


def install_primitive_math_capabilities(
    store: ArtifactStore,
    schemas: SchemaRegistry,
    artifacts: ArtifactService,
) -> tuple[PrimitiveMathAdapter, ...]:
    semantics_uri = store.register_descriptor(
        kind="semantics",
        name="jacobian.exact-primitive-math",
        version="1",
        definition={
            "description": "bounded exact integer and finite combinatorial operations",
            "integer_encoding": "canonical decimal string unless a count parameter is bounded",
            "assurance": "computed; no independent checker",
        },
    )
    models = {spec.request_model for spec in SPECS}
    input_schema_uris = {
        model: schemas.register_model(
            name=f"jacobian.primitive-input.{model.__name__}",
            version="1",
            model=model,
        )
        for model in models
    }
    output_schema_uri = schemas.register_model(
        name="jacobian.primitive-math-artifact",
        version="1",
        model=PrimitiveMathArtifact,
    )
    resources = PrimitiveResources(
        artifacts=artifacts,
        semantics_uri=semantics_uri,
        input_schema_uris=input_schema_uris,
        output_schema_uri=output_schema_uri,
    )
    return tuple(PrimitiveMathAdapter(spec, resources) for spec in SPECS)


class PrimitiveMathAdapter:
    def __init__(self, spec: PrimitiveSpec, resources: PrimitiveResources) -> None:
        self.spec = spec
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id=spec.capability_id,
            version="1",
            title=spec.title,
            description=spec.description,
            provider="jacobian.primitive-math",
            provider_runtime=known_provider_runtime(
                "jacobian.primitive-math",
                features=("exact-integer", "combinatorics"),
                configuration={"sympy_version": sympy.__version__},
            ),
            modes=(CapabilityMode.EXPLORE,),
            input_schema=model_schema(spec.request_model),
            output_schema=model_schema(PrimitiveMathOutput),
            tags=spec.tags,
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        try:
            validated = self.spec.request_model.model_validate(request.input)
        except ValidationError as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_PRIMITIVE_MATH_REQUEST",
                    stage="primitive_input_validation",
                    message="Input does not satisfy this capability's exact contract.",
                    hint="Inspect capability.describe and supply canonical bounded values.",
                )
            ) from exc
        started = time.monotonic()
        try:
            result = self.spec.compute(validated)
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="PRIMITIVE_MATH_NOT_APPLICABLE",
                    stage="primitive_computation",
                    message=str(exc)
                    or "The operation is not applicable to this input.",
                    hint="Adjust the input to satisfy the operation's mathematical preconditions.",
                )
            ) from exc
        input_uri = self.resources.artifacts.put(
            schema_uri=self.resources.input_schema_uris[self.spec.request_model],
            semantics_uri=self.resources.semantics_uri,
            payload=validated.model_dump(mode="json"),
            summary=f"{self.spec.capability_id} exact input",
        ).artifact_uri
        artifact = PrimitiveMathArtifact(
            capability_id=self.spec.capability_id,
            input_uri=input_uri,
            result=result,
            backend_version=_BACKEND_VERSION,
        )
        result_uri = self.resources.artifacts.put(
            schema_uri=self.resources.output_schema_uri,
            semantics_uri=self.resources.semantics_uri,
            payload=artifact.model_dump(mode="json"),
            parents=(input_uri,),
            summary=f"{self.spec.capability_id} exact result",
        ).artifact_uri
        output = PrimitiveMathOutput(
            input_uri=input_uri,
            result_uri=result_uri,
            result=result,
            backend_version=_BACKEND_VERSION,
        )
        return CapabilityResult(
            capability_id=self.spec.capability_id,
            capability_version="1",
            mode=request.mode,
            execution=Execution(
                status=ExecutionStatus.COMPLETED,
                runtime_ms=max(0, round((time.monotonic() - started) * 1000)),
            ),
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description="the complete supplied bounded exact input",
                parameters={"input_uri": input_uri},
                artifact_uri=input_uri,
            ),
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.COMPLETE,
                basis="deterministic exact computation covered the declared input; not independently verified",
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            relationships=(
                CapabilityRelationship(
                    relation_id=self.spec.capability_id.replace(
                        ".compute.", ".relation."
                    )
                    .replace(".decide.", ".relation.")
                    .replace(".enumerate.", ".relation.")
                    .replace(".solve.", ".relation.")
                    .replace(".transform.", ".relation."),
                    source_artifact_uris=(input_uri,),
                    target_artifact_uris=(result_uri,),
                ),
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis="deterministic exact arithmetic from the pinned SymPy runtime; no independent checker invoked",
            ),
            artifact_uris=(input_uri, result_uri),
        )
