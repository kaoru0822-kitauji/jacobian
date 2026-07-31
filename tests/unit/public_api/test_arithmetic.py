from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from jacobian.math import arithmetic


@given(st.integers())
def test_absolute_value_and_sign_preserve_integer_invariants(value: int) -> None:
    assert arithmetic.absolute_value(value) >= 0
    assert arithmetic.absolute_value(value) * arithmetic.sign(value) == value


def test_exact_rational_operations() -> None:
    assert arithmetic.sum_rationals(Fraction(1, 3), Fraction(1, 6)) == Fraction(1, 2)
    assert arithmetic.quotient(Fraction(2, 3), 4) == Fraction(1, 6)
    assert arithmetic.reciprocal(Fraction(-2, 3)) == Fraction(-3, 2)


@pytest.mark.parametrize(
    "operation", [arithmetic.reciprocal, lambda x: arithmetic.quotient(1, x)]
)
def test_zero_division_is_explicit(operation: object) -> None:
    with pytest.raises(ZeroDivisionError, match=r"zero|division by zero"):
        operation(0)  # type: ignore[operator]
