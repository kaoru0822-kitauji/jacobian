"""Exact combinatorics operations backed by maintained SymPy and stdlib APIs."""

from __future__ import annotations

from functools import reduce
from operator import mul
from typing import cast

from jacobian.contracts.combinatorics import (
    IntegerListRequest,
    IntegerPartitionEnumerationRequest,
    IntegerPartitionEnumerationResult,
    IntegerResult,
    NonnegativeIntegerRequest,
    NonnegativePairRequest,
    RationalResult,
)
from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.results import ContractModel


def _integer_result(value: int) -> IntegerResult:
    return IntegerResult(value=str(int(value)))


def factorial(request: ContractModel) -> ContractModel:
    import math

    n = cast(NonnegativeIntegerRequest, request).n
    return _integer_result(math.factorial(n))


def double_factorial(request: ContractModel) -> ContractModel:
    import sympy

    n = cast(NonnegativeIntegerRequest, request).n
    return _integer_result(sympy.factorial2(n))


def derangements(request: ContractModel) -> ContractModel:
    import sympy

    n = cast(NonnegativeIntegerRequest, request).n
    return _integer_result(sympy.subfactorial(n))


def binomial(request: ContractModel) -> ContractModel:
    import math

    pair = cast(NonnegativePairRequest, request)
    if pair.k > pair.n:
        return _integer_result(0)
    return _integer_result(math.comb(pair.n, pair.k))


def multinomial(request: ContractModel) -> ContractModel:
    import math

    values = [int(v) for v in cast(IntegerListRequest, request).values]
    numerator = math.factorial(sum(values))
    denominator = reduce(mul, (math.factorial(v) for v in values), 1)
    return _integer_result(numerator // denominator)


def permutations(request: ContractModel) -> ContractModel:
    import math

    pair = cast(NonnegativePairRequest, request)
    if pair.k > pair.n:
        return _integer_result(0)
    return _integer_result(math.perm(pair.n, pair.k))


def stirling_first(request: ContractModel) -> ContractModel:
    from sympy.functions.combinatorial.numbers import stirling

    pair = cast(NonnegativePairRequest, request)
    return _integer_result(stirling(pair.n, pair.k, kind=1))


def stirling_second(request: ContractModel) -> ContractModel:
    from sympy.functions.combinatorial.numbers import stirling

    pair = cast(NonnegativePairRequest, request)
    return _integer_result(stirling(pair.n, pair.k, kind=2))


def bell(request: ContractModel) -> ContractModel:
    import sympy

    n = cast(NonnegativeIntegerRequest, request).n
    return _integer_result(sympy.bell(n))


def catalan(request: ContractModel) -> ContractModel:
    import sympy

    n = cast(NonnegativeIntegerRequest, request).n
    return _integer_result(sympy.catalan(n))


def partition_number(request: ContractModel) -> ContractModel:
    import sympy

    n = cast(NonnegativeIntegerRequest, request).n
    return _integer_result(sympy.partition(n))


def enumerate_integer_partitions(request: ContractModel) -> ContractModel:
    """Enumerate all bounded partitions using ``sympy.utilities.partitions``."""
    from sympy.utilities.iterables import partitions

    value = cast(IntegerPartitionEnumerationRequest, request)
    expanded_partitions: list[tuple[int, ...]] = []
    for multiplicities in partitions(value.n, m=value.max_parts):
        expanded_partitions.append(
            tuple(
                part
                for part in sorted(multiplicities, reverse=True)
                for _ in range(int(multiplicities[part]))
            )
        )
    return IntegerPartitionEnumerationResult(
        n=value.n,
        max_parts=value.max_parts,
        partitions=tuple(expanded_partitions),
    )


def fibonacci(request: ContractModel) -> ContractModel:
    import sympy

    n = cast(NonnegativeIntegerRequest, request).n
    return _integer_result(sympy.fibonacci(n))


def lucas(request: ContractModel) -> ContractModel:
    import sympy

    n = cast(NonnegativeIntegerRequest, request).n
    return _integer_result(sympy.lucas(n))


def motzkin(request: ContractModel) -> ContractModel:
    import sympy

    n = cast(NonnegativeIntegerRequest, request).n
    return _integer_result(sympy.motzkin(n))


def bernoulli(request: ContractModel) -> ContractModel:
    import sympy

    n = cast(NonnegativeIntegerRequest, request).n
    value = sympy.bernoulli(n)
    return RationalResult(
        value=CanonicalRational(num=str(value.p), den=str(value.q)),
    )


def central_binomial(request: ContractModel) -> ContractModel:
    import math

    n = cast(NonnegativeIntegerRequest, request).n
    return _integer_result(math.comb(2 * n, n))


def compositions(request: ContractModel) -> ContractModel:
    import math

    pair = cast(NonnegativePairRequest, request)
    if pair.n == pair.k == 0:
        return _integer_result(1)
    if 0 < pair.k <= pair.n:
        return _integer_result(math.comb(pair.n - 1, pair.k - 1))
    return _integer_result(0)
