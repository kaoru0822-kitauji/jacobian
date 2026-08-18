"""Domain-owned finite game theory operations."""

from __future__ import annotations

from fractions import Fraction

from jacobian.canonical import format_canonical_integer
from jacobian.math.finite_game_theory._models import (
    BestResponseResult,
    NashEquilibriumResult,
    ZeroSumGameRequest,
)


def _format_rational(value: Fraction) -> str:
    if value.denominator == 1:
        return format_canonical_integer(value.numerator)
    return (
        f"{format_canonical_integer(value.numerator)}/"
        f"{format_canonical_integer(value.denominator)}"
    )


def _payoff_matrix(request: ZeroSumGameRequest) -> list[list[Fraction]]:
    matrix = request.payoff_matrix
    entries = [entry.as_fraction() for entry in matrix.entries]
    return [
        [entries[row * matrix.n_cols + col] for col in range(matrix.n_cols)]
        for row in range(matrix.n_rows)
    ]


def compute_best_response(request: ZeroSumGameRequest) -> BestResponseResult:
    """Compute the maximin value and a maximizing row for the row player."""
    matrix = _payoff_matrix(request)
    best_row = 0
    best_value = min(matrix[0])
    for row_index, row in enumerate(matrix[1:], start=1):
        row_min = min(row)
        if row_min > best_value:
            best_value = row_min
            best_row = row_index
    return BestResponseResult(value=_format_rational(best_value), best_row=best_row)


def compute_nash_equilibrium(request: ZeroSumGameRequest) -> NashEquilibriumResult:
    """Compute one exact saddle point of a finite 2-player zero-sum game."""

    import sympy
    from sympy.solvers.simplex import lpmax, lpmin

    matrix = _payoff_matrix(request)
    n_rows = len(matrix)
    n_cols = len(matrix[0])
    minimum_payoff = min(min(row) for row in matrix)
    shift = max(Fraction(0), Fraction(1) - minimum_payoff)
    shifted_matrix = [[value + shift for value in row] for row in matrix]
    row_symbols = sympy.symbols(f"_row0:{n_rows}")
    column_symbols = sympy.symbols(f"_column0:{n_cols}")
    row_value_symbol = sympy.Symbol("_row_value")
    column_value_symbol = sympy.Symbol("_column_value")

    row_constraints = [symbol >= 0 for symbol in row_symbols]
    row_constraints.append(sympy.Eq(sum(row_symbols), 1))
    row_constraints.extend(
        sum(
            row_symbols[row] * sympy.Rational(shifted_matrix[row][column])
            for row in range(n_rows)
        )
        >= row_value_symbol
        for column in range(n_cols)
    )
    row_value, row_solution = lpmax(row_value_symbol, row_constraints)

    column_constraints = [symbol >= 0 for symbol in column_symbols]
    column_constraints.append(sympy.Eq(sum(column_symbols), 1))
    column_constraints.extend(
        sum(
            sympy.Rational(shifted_matrix[row][column]) * column_symbols[column]
            for column in range(n_cols)
        )
        <= column_value_symbol
        for row in range(n_rows)
    )
    column_value, column_solution = lpmin(
        column_value_symbol,
        column_constraints,
    )
    if row_value != column_value:
        raise RuntimeError("exact primal and dual game values disagree")

    row_strategy = [Fraction(row_solution.get(symbol, 0)) for symbol in row_symbols]
    column_strategy = [
        Fraction(column_solution.get(symbol, 0)) for symbol in column_symbols
    ]
    value = Fraction(row_value) - shift
    if sum(row_strategy) != 1 or any(weight < 0 for weight in row_strategy):
        raise RuntimeError("SymPy returned an invalid row strategy")
    if sum(column_strategy) != 1 or any(weight < 0 for weight in column_strategy):
        raise RuntimeError("SymPy returned an invalid column strategy")
    if any(
        sum(row_strategy[row] * matrix[row][column] for row in range(n_rows)) < value
        for column in range(n_cols)
    ):
        raise RuntimeError("row strategy does not attain the reported game value")
    if any(
        sum(matrix[row][column] * column_strategy[column] for column in range(n_cols))
        > value
        for row in range(n_rows)
    ):
        raise RuntimeError("column strategy does not attain the reported game value")
    return NashEquilibriumResult(
        row_strategy=tuple(_format_rational(weight) for weight in row_strategy),
        col_strategy=tuple(_format_rational(weight) for weight in column_strategy),
        value=_format_rational(value),
    )


__all__ = ["compute_best_response", "compute_nash_equilibrium"]
