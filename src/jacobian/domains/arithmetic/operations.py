"""Exact integer and rational operations owned by the arithmetic domain.

The arithmetic domain owns integer absolute value, sign, decimal digit
sum/count, base expansion, integer nth root, and rational arithmetic, order,
rounding, representation, and predicates.  Number-theory operations (gcd,
lcm, divisors, primes, modular arithmetic, integer predicates) are owned by
the number-theory domain.

No handrolled algorithms are used where the Python standard library or
SymPy provides a maintained implementation.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Literal, cast

from jacobian.contracts.arithmetic import (
    IntegerBaseDigitsRequest,
    IntegerBaseDigitsResult,
    IntegerNthRootRequest,
    IntegerNthRootResult,
    IntegerSignResult,
    IntegerValueRequest,
    IntegerValueResult,
)
from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.rationals import (
    RationalComparisonResult,
    RationalContinuedFractionResult,
    RationalIntegerResult,
    RationalPairRequest,
    RationalValueRequest,
    RationalValueResult,
)
from jacobian.contracts.results import ContractModel


def _int(value: str) -> int:
    return int(value)


def _canonical(value: int) -> str:
    return str(value)


def to_fraction(num: str, den: str) -> Fraction:
    """Build a reduced ``Fraction`` from canonical integer strings."""
    return Fraction(int(num), int(den))


def absolute_value(request: ContractModel) -> ContractModel:
    req = cast(IntegerValueRequest, request)
    return IntegerValueResult(value=_canonical(abs(_int(req.value))))


def sign(request: ContractModel) -> ContractModel:
    req = cast(IntegerValueRequest, request)
    value = _int(req.value)
    if value < 0:
        sign: Literal[-1, 0, 1] = -1
    elif value > 0:
        sign = 1
    else:
        sign = 0
    return IntegerSignResult(sign=sign)


def decimal_digit_sum(request: ContractModel) -> ContractModel:
    req = cast(IntegerValueRequest, request)
    return IntegerValueResult(
        value=_canonical(sum(int(digit) for digit in str(abs(_int(req.value)))))
    )


def decimal_digit_count(request: ContractModel) -> ContractModel:
    req = cast(IntegerValueRequest, request)
    return IntegerValueResult(value=_canonical(len(str(abs(_int(req.value))))))


def base_digits(request: ContractModel) -> ContractModel:
    from sympy.ntheory import digits as sympy_digits

    req = cast(IntegerBaseDigitsRequest, request)
    value = _int(req.value)
    expanded = sympy_digits(abs(value), req.base)[1:]
    if value < 0:
        sign: Literal[-1, 0, 1] = -1
    elif value > 0:
        sign = 1
    else:
        sign = 0
    return IntegerBaseDigitsResult(
        sign=sign,
        base=req.base,
        digits=tuple(str(digit) for digit in expanded),
    )


def nth_root(request: ContractModel) -> ContractModel:
    from sympy import integer_nthroot

    req = cast(IntegerNthRootRequest, request)
    if req.value < 0 and req.degree % 2 == 0:
        raise ValueError("even root of a negative integer is not integral-real")
    root, exact = integer_nthroot(abs(req.value), req.degree)
    return IntegerNthRootResult(
        root=_canonical(-root if req.value < 0 else root),
        exact=exact,
    )


def _fraction(value: CanonicalRational) -> Fraction:
    return Fraction(int(value.num), int(value.den))


def _wire(value: Fraction) -> CanonicalRational:
    return CanonicalRational(
        num=str(value.numerator),
        den=str(value.denominator),
    )


def reciprocal(request: ContractModel) -> ContractModel:
    req = cast(RationalValueRequest, request)
    value = _fraction(req.value)
    if value == 0:
        raise ValueError("zero has no reciprocal")
    return RationalValueResult(value=_wire(Fraction(1, 1) / value))


def negation(request: ContractModel) -> ContractModel:
    req = cast(RationalValueRequest, request)
    return RationalValueResult(value=_wire(-_fraction(req.value)))


def rational_absolute_value(request: ContractModel) -> ContractModel:
    req = cast(RationalValueRequest, request)
    return RationalValueResult(value=_wire(abs(_fraction(req.value))))


def sum_rationals(request: ContractModel) -> ContractModel:
    req = cast(RationalPairRequest, request)
    return RationalValueResult(value=_wire(_fraction(req.left) + _fraction(req.right)))


def difference(request: ContractModel) -> ContractModel:
    req = cast(RationalPairRequest, request)
    return RationalValueResult(value=_wire(_fraction(req.left) - _fraction(req.right)))


def product(request: ContractModel) -> ContractModel:
    req = cast(RationalPairRequest, request)
    return RationalValueResult(value=_wire(_fraction(req.left) * _fraction(req.right)))


def quotient(request: ContractModel) -> ContractModel:
    req = cast(RationalPairRequest, request)
    right = _fraction(req.right)
    if right == 0:
        raise ValueError("division by zero")
    return RationalValueResult(value=_wire(_fraction(req.left) / right))


def minimum(request: ContractModel) -> ContractModel:
    req = cast(RationalPairRequest, request)
    return RationalValueResult(
        value=_wire(min(_fraction(req.left), _fraction(req.right)))
    )


def maximum(request: ContractModel) -> ContractModel:
    req = cast(RationalPairRequest, request)
    return RationalValueResult(
        value=_wire(max(_fraction(req.left), _fraction(req.right)))
    )


def floor(request: ContractModel) -> ContractModel:
    req = cast(RationalValueRequest, request)
    return RationalIntegerResult(value=str(math.floor(_fraction(req.value))))


def ceiling(request: ContractModel) -> ContractModel:
    req = cast(RationalValueRequest, request)
    return RationalIntegerResult(value=str(math.ceil(_fraction(req.value))))


def continued_fraction(request: ContractModel) -> ContractModel:
    from sympy import Rational as SympyRational
    from sympy import continued_fraction as sympy_continued_fraction

    req = cast(RationalValueRequest, request)
    value = _fraction(req.value)
    terms = sympy_continued_fraction(SympyRational(value.numerator, value.denominator))
    return RationalContinuedFractionResult(
        terms=tuple(str(int(term)) for term in terms)
    )


def equal(request: ContractModel) -> ContractModel:
    req = cast(RationalPairRequest, request)
    return RationalComparisonResult(holds=_fraction(req.left) == _fraction(req.right))


def less_than(request: ContractModel) -> ContractModel:
    req = cast(RationalPairRequest, request)
    return RationalComparisonResult(holds=_fraction(req.left) < _fraction(req.right))
