"""Exact number-theory capabilities with structured, argument-bound results."""

from jacobian.contracts.number_theory import (
    FactorialValuationRequest,
    FactorialValuationResult,
    FloorSquareRootRequest,
    FloorSquareRootResult,
    LegendreSymbolRequest,
    LegendreSymbolResult,
)
from jacobian.domains.number_theory._support import number_theory_operation
from jacobian.domains.number_theory.operations import (
    compute_factorial_valuation,
    compute_floor_square_root,
    compute_legendre_symbol,
)

DERIVED_NUMBER_THEORY_CAPABILITIES = (
    number_theory_operation(
        "integer.compute.floor_square_root",
        "Compute an integer floor square root",
        "Return floor(sqrt(n)) exactly for a bounded nonnegative integer.",
        FloorSquareRootRequest,
        FloorSquareRootResult,
        compute_floor_square_root,
        "number-theory",
        "square",
    ),
    number_theory_operation(
        "number_theory.compute.legendre_symbol",
        "Compute a Legendre symbol",
        "Compute (a/p) exactly for a bounded odd prime p.",
        LegendreSymbolRequest,
        LegendreSymbolResult,
        compute_legendre_symbol,
        "number-theory",
        "quadratic-residue",
    ),
    number_theory_operation(
        "number_theory.compute.factorial_valuation",
        "Compute a factorial valuation",
        "Compute the largest e such that base**e divides n!.",
        FactorialValuationRequest,
        FactorialValuationResult,
        compute_factorial_valuation,
        "number-theory",
        "valuation",
    ),
)
