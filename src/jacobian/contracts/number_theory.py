"""Named Pydantic wire contracts for exact integer number-theory capabilities.

These contracts cover gcd/lcm, Bezout coefficients, divisors, prime
factorization, p-adic valuation, multiplicative arithmetic functions,
primality, modular arithmetic, and integer predicates (coprimality,
divisibility, perfect/abundant/deficient, square, squarefree).  They are
owned by the number-theory domain and intentionally exclude arithmetic-owned
operations (absolute value, sign, decimal digit sum/count, base expansion,
integer nth root).
"""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import Field, StrictInt, StringConstraints, model_validator

from jacobian.contracts.results import ContractModel

# ---------------------------------------------------------------------------
# Shared bounds — kept consistent with the legacy primitive adapters.
# ---------------------------------------------------------------------------

_MAX_INTEGER_LENGTH = 256
_MAX_N_SMALL = 1_000
_MAX_MODULUS = 10_000
_MAX_CRT_SIZE = 64
_MAX_DIVISORS = 4_096
_MAX_FACTOR_ENTRIES = 256

BoundedInteger = Annotated[
    str,
    StringConstraints(
        pattern=r"^-?(?:0|[1-9][0-9]*)$",
        max_length=_MAX_INTEGER_LENGTH,
        strict=True,
    ),
]


# ---------------------------------------------------------------------------
# Request models — canonical integers (arbitrary precision, bounded string)
# ---------------------------------------------------------------------------


class IntegerValueRequest(ContractModel):
    """One canonical integer supplied to a unary number-theory operation."""

    value: BoundedInteger


class IntegerPairRequest(ContractModel):
    """Two canonical integers supplied to a symmetric binary operation."""

    left: BoundedInteger
    right: BoundedInteger


class DivisibilityRequest(ContractModel):
    """A divisor and dividend supplied to a divisibility predicate."""

    divisor: BoundedInteger
    dividend: BoundedInteger


class ValuationRequest(ContractModel):
    """One integer and a prime base supplied to a p-adic valuation."""

    value: BoundedInteger
    prime: BoundedInteger


# ---------------------------------------------------------------------------
# Request models — bounded non-negative / positive integers
# ---------------------------------------------------------------------------


class NonnegativeIntegerRequest(ContractModel):
    """One bounded non-negative integer (0 <= n <= 1 000)."""

    n: StrictInt = Field(ge=0, le=_MAX_N_SMALL)


class PositiveIntegerRequest(ContractModel):
    """One bounded positive integer (1 <= n <= 1 000)."""

    n: StrictInt = Field(ge=1, le=_MAX_N_SMALL)


# ---------------------------------------------------------------------------
# Request models — modular arithmetic
# ---------------------------------------------------------------------------


class ModularValueRequest(ContractModel):
    """One canonical integer and a bounded modulus (2 <= modulus <= 10 000)."""

    value: BoundedInteger
    modulus: StrictInt = Field(ge=2, le=_MAX_MODULUS)


class ModulusRequest(ContractModel):
    """A single bounded modulus (2 <= modulus <= 10 000)."""

    modulus: StrictInt = Field(ge=2, le=_MAX_MODULUS)


class ChineseRemainderRequest(ContractModel):
    """A finite system of integer congruences with parallel residues and moduli."""

    residues: tuple[int, ...] = Field(min_length=1, max_length=_MAX_CRT_SIZE)
    moduli: tuple[int, ...] = Field(min_length=1, max_length=_MAX_CRT_SIZE)

    @model_validator(mode="after")
    def require_parallel_positive_moduli(self) -> Self:
        if len(self.residues) != len(self.moduli):
            raise ValueError("residues and moduli must have equal length")
        if any(modulus < 2 or modulus > _MAX_MODULUS for modulus in self.moduli):
            raise ValueError("every modulus must be between 2 and 10,000")
        return self


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class IntegerValueResult(ContractModel):
    """One exact integer value produced by a number-theory operation."""

    value: BoundedInteger


class ExtendedGcdResult(ContractModel):
    """A gcd together with exact Bezout coefficients."""

    gcd: BoundedInteger
    left_coefficient: BoundedInteger
    right_coefficient: BoundedInteger


class DivisorListResult(ContractModel):
    """An ordered list of positive divisors of one nonzero integer.

    The list may be empty: ``proper_divisors(±1)`` has no positive proper
    divisors.  Zero remains not-applicable (handled at the operation layer).
    """

    divisors: tuple[BoundedInteger, ...] = Field(
        min_length=0,
        max_length=_MAX_DIVISORS,
    )

    @model_validator(mode="after")
    def require_positive_ascending_unique(self) -> Self:
        values = [int(divisor) for divisor in self.divisors]
        if any(value < 1 for value in values):
            raise ValueError("divisors must be positive")
        if values != sorted(values):
            raise ValueError("divisors must be ascending")
        if len(set(values)) != len(values):
            raise ValueError("divisors must be unique")
        return self


class PrimePower(ContractModel):
    """One prime base and its exponent in a prime factorization."""

    prime: BoundedInteger
    power: int = Field(ge=1, le=_MAX_N_SMALL)


class PrimeFactorizationResult(ContractModel):
    """The complete prime-power factorization of one nonzero integer.

    The factor list may be empty: ``±1`` has no prime factors.  Zero remains
    not-applicable (handled at the operation layer).
    """

    factors: tuple[PrimePower, ...] = Field(
        min_length=0,
        max_length=_MAX_FACTOR_ENTRIES,
    )

    @model_validator(mode="after")
    def require_unique_primes(self) -> Self:
        primes = [factor.prime for factor in self.factors]
        if len(set(primes)) != len(primes):
            raise ValueError("prime factors must be unique")
        return self


class BooleanResult(ContractModel):
    """Truth value of a number-theory predicate."""

    holds: bool


class QuadraticResiduesResult(ContractModel):
    """All quadratic residues modulo one modulus."""

    residues: tuple[BoundedInteger, ...]


class ChineseRemainderResult(ContractModel):
    """The least non-negative solution and modulus of a compatible CRT system."""

    residue: BoundedInteger
    modulus: BoundedInteger
