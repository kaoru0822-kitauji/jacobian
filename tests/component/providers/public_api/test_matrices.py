import pytest
import sympy

from jacobian.math import matrices


def test_exact_matrix_operations() -> None:
    source = sympy.Matrix([[1, 2], [3, 4]])
    assert matrices.inverse(source) == sympy.Matrix(
        [[-2, 1], [sympy.Rational(3, 2), sympy.Rational(-1, 2)]]
    )
    assert matrices.trace(source) == 5
    reduced, pivots = matrices.rref(sympy.Matrix([[1, 2], [2, 4]]))
    assert reduced == sympy.Matrix([[1, 2], [0, 0]])
    assert pivots == (0,)


def test_matrix_input_errors_are_stable() -> None:
    with pytest.raises(TypeError, match="SymPy MatrixBase"):
        matrices.trace([[1]])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="square"):
        matrices.inverse(sympy.Matrix([[1, 2]]))
    with pytest.raises(ValueError, match="singular"):
        matrices.inverse(sympy.zeros(2))
    with pytest.raises(ValueError, match="exact"):
        matrices.trace(sympy.Matrix([[1.5]]))
    nested_float = sympy.Add(sympy.Float("0.1"), sympy.Rational(1, 3), evaluate=False)
    with pytest.raises(ValueError, match="exact"):
        matrices.trace(sympy.Matrix([[nested_float]]))
