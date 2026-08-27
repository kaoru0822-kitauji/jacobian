"""Contracts owned by basic modular-arithmetic kernels.

Polynomial residue-image contracts remain in ``_modular_models``; this module
owns the distinct unit, CRT, Jacobi, and quadratic-residue envelopes.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, StrictInt, model_validator

from jacobian._models import StrictModel
from jacobian.math.number_theory._models import BoundedInteger, _validation_error

MAX_MODULUS = 1_000_000
MAX_CRT_SIZE = 64
# The CRT result carries its combined modulus as a canonical integer whose
# width is bounded by the neutral integer grammar.
MAX_CRT_COMBINED_MODULUS = 10**256


class ModularValueRequest(StrictModel):
    """One canonical integer and a bounded modulus."""

    value: BoundedInteger
    modulus: StrictInt = Field(ge=2, le=MAX_MODULUS)


class ModularUnitRequest(ModularValueRequest):
    """One canonical integer that is a unit modulo the supplied modulus."""


class ModulusRequest(StrictModel):
    """A single bounded modulus."""

    modulus: StrictInt = Field(ge=2, le=MAX_MODULUS)


class ChineseRemainderRequest(StrictModel):
    """A finite, compatible system of canonical integer congruences."""

    residues: tuple[int, ...] = Field(min_length=1, max_length=MAX_CRT_SIZE)
    moduli: tuple[int, ...] = Field(min_length=1, max_length=MAX_CRT_SIZE)


class JacobiSymbolRequest(StrictModel):
    """Arguments for the Jacobi symbol ``(a / n)`` with odd positive ``n``."""

    a: BoundedInteger
    n: StrictInt = Field(ge=3, le=MAX_MODULUS)


class QuadraticResiduesResult(StrictModel):
    """All quadratic residues modulo one admitted modulus."""

    residues: tuple[BoundedInteger, ...]


class ChineseRemainderResult(StrictModel):
    """The least non-negative solution and modulus of a CRT system."""

    residue: BoundedInteger
    modulus: BoundedInteger


class JacobiSymbolResult(StrictModel):
    """The exact Jacobi symbol, bound to its normalized arguments."""

    a: BoundedInteger
    n: StrictInt = Field(ge=3, le=MAX_MODULUS)
    jacobi: Literal[-1, 0, 1]

    @model_validator(mode="after")
    def require_odd_denominator(self) -> Self:
        if self.n % 2 == 0:
            raise _validation_error(
                "jacobi_symbol_denominator_must_be_odd",
                "Jacobi symbol denominator must be odd",
            )
        return self


__all__ = [
    "MAX_CRT_COMBINED_MODULUS",
    "MAX_CRT_SIZE",
    "MAX_MODULUS",
    "ChineseRemainderRequest",
    "ChineseRemainderResult",
    "JacobiSymbolRequest",
    "JacobiSymbolResult",
    "ModularUnitRequest",
    "ModularValueRequest",
    "ModulusRequest",
    "QuadraticResiduesResult",
]
