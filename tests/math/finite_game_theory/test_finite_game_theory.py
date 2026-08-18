"""Tests for finite game theory operations."""

from fractions import Fraction

from jacobian.math.finite_game_theory._models import (
    PayoffMatrix,
    ZeroSumGameRequest,
)
from jacobian.math.finite_game_theory._operations import (
    compute_best_response,
    compute_nash_equilibrium,
)


class TestBestResponse:
    def test_simple(self):
        req = ZeroSumGameRequest(
            payoff_matrix=PayoffMatrix(
                n_rows=2,
                n_cols=2,
                entries=(
                    {"num": "3", "den": "1"},
                    {"num": "0", "den": "1"},
                    {"num": "0", "den": "1"},
                    {"num": "2", "den": "1"},
                ),
            ),
        )
        result = compute_best_response(req)
        assert result.best_row == 0  # Row 0 has minimum 0, Row 1 has minimum 0


class TestNashEquilibrium:
    def test_pure_strategy(self):
        req = ZeroSumGameRequest(
            payoff_matrix=PayoffMatrix(
                n_rows=2,
                n_cols=2,
                entries=(
                    {"num": "1", "den": "1"},
                    {"num": "1", "den": "1"},
                    {"num": "0", "den": "1"},
                    {"num": "0", "den": "1"},
                ),
            ),
        )
        result = compute_nash_equilibrium(req)
        assert result.value == "1"  # (0,0) is the pure Nash equilibrium

    def test_mixed_equilibrium(self):
        req = ZeroSumGameRequest(
            payoff_matrix=PayoffMatrix(
                n_rows=2,
                n_cols=2,
                entries=(
                    {"num": "2", "den": "1"},
                    {"num": "0", "den": "1"},
                    {"num": "-1", "den": "1"},
                    {"num": "3", "den": "1"},
                ),
            ),
        )
        result = compute_nash_equilibrium(req)
        assert result.row_strategy == ("2/3", "1/3")
        assert result.col_strategy == ("1/2", "1/2")
        assert result.value == "1"

    def test_degenerate_game_uses_exact_linear_programming(self):
        req = ZeroSumGameRequest(
            payoff_matrix=PayoffMatrix(
                n_rows=3,
                n_cols=3,
                entries=tuple(
                    {"num": str(value), "den": "1"}
                    for value in (1, -1, 0, -1, 1, 0, 0, 0, 0)
                ),
            ),
        )

        result = compute_nash_equilibrium(req)

        assert result.value == "0"
        assert sum(Fraction(value) for value in result.row_strategy) == 1
        assert sum(Fraction(value) for value in result.col_strategy) == 1

    def test_negative_game_value_is_not_clamped_by_simplex_nonnegativity(self):
        req = ZeroSumGameRequest(
            payoff_matrix=PayoffMatrix(
                n_rows=2,
                n_cols=2,
                entries=tuple(
                    {"num": str(value), "den": "1"} for value in (-2, -3, -4, -5)
                ),
            ),
        )

        result = compute_nash_equilibrium(req)

        assert result.row_strategy == ("1", "0")
        assert result.col_strategy == ("0", "1")
        assert result.value == "-3"

    def test_fractional_payoffs_are_scaled_before_exact_linear_programming(self):
        values = (Fraction(1, 3), Fraction(-2, 5), Fraction(7, 4), Fraction(1, 2))
        req = ZeroSumGameRequest(
            payoff_matrix=PayoffMatrix(
                n_rows=2,
                n_cols=2,
                entries=tuple(
                    {"num": str(value.numerator), "den": str(value.denominator)}
                    for value in values
                ),
            ),
        )

        result = compute_nash_equilibrium(req)

        assert result.row_strategy == ("0", "1")
        assert result.col_strategy == ("0", "1")
        assert result.value == "1/2"

    def test_maximin_uses_actual_payoff(self):
        req = ZeroSumGameRequest(
            payoff_matrix=PayoffMatrix(
                n_rows=1,
                n_cols=1,
                entries=({"num": "-100000000000000000000", "den": "1"},),
            ),
        )
        result = compute_best_response(req)
        assert result.value == "-100000000000000000000"
