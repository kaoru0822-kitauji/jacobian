"""Modular-owned exact number-theory capabilities."""

from jacobian.contracts.number_theory import (
    ChineseRemainderRequest,
    ChineseRemainderResult,
    IntegerValueResult,
    JacobiSymbolRequest,
    JacobiSymbolResult,
    ModularValueRequest,
    ModulusRequest,
    QuadraticResiduesResult,
)
from jacobian.domains._examples import example
from jacobian.domains.number_theory._support import (
    number_theory_operation,
)
from jacobian.domains.number_theory.discrete_logarithm import (
    DISCRETE_LOGARITHM_CAPABILITY,
)
from jacobian.domains.number_theory.operations import (
    compute_jacobi_symbol,
    compute_modular_inverse,
    compute_multiplicative_order,
    enumerate_quadratic_residues,
    solve_chinese_remainder,
)

MODULAR_CAPABILITIES = (
    number_theory_operation(
        "number_theory.compute.jacobi_symbol",
        "Compute Jacobi symbol",
        "Compute the Jacobi symbol (a / n) for an odd positive denominator.",
        JacobiSymbolRequest,
        JacobiSymbolResult,
        compute_jacobi_symbol,
        "number-theory",
        "modular",
        "jacobi-symbol",
        invocation_examples=(example("jacobi_10_21", "Compute the Jacobi symbol (10/21).", {"a": "10", "n": 21}),),
    ),
    number_theory_operation(
        "modular.compute.inverse",
        "Compute modular inverse",
        "Compute the least nonnegative inverse of a value modulo m.",
        ModularValueRequest,
        IntegerValueResult,
        compute_modular_inverse,
        "number-theory",
        "modular",
    ),
    number_theory_operation(
        "modular.compute.multiplicative_order",
        "Compute multiplicative order",
        "Compute the multiplicative order of a unit modulo m.",
        ModularValueRequest,
        IntegerValueResult,
        compute_multiplicative_order,
        "number-theory",
        "modular",
    ),
    number_theory_operation(
        "modular.enumerate.quadratic_residues",
        "Enumerate quadratic residues",
        "Enumerate all quadratic residues modulo m.",
        ModulusRequest,
        QuadraticResiduesResult,
        enumerate_quadratic_residues,
        "number-theory",
        "modular",
        "enumeration",
        invocation_examples=(example("quadratic_residues_mod_10", "Enumerate quadratic residues modulo 10.", {"modulus": 10}),),
    ),
    number_theory_operation(
        "modular.solve.chinese_remainder",
        "Solve congruence system",
        "Solve a finite compatible system of integer congruences.",
        ChineseRemainderRequest,
        ChineseRemainderResult,
        solve_chinese_remainder,
        "number-theory",
        "modular",
        invocation_examples=(example("crt_2_mod_3_3_mod_5", "Solve x=2 mod 3 and x=3 mod 5.", {"residues": [2, 3], "moduli": [3, 5]}),),
    ),
    DISCRETE_LOGARITHM_CAPABILITY,
)
