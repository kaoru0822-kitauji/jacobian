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

from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StrictInt, StringConstraints, model_validator

from jacobian.contracts.results import ContractModel

# ---------------------------------------------------------------------------
# Shared bounds — kept consistent with the legacy primitive adapters.
# ---------------------------------------------------------------------------

_MAX_INTEGER_LENGTH = 256
# These small bounds deliberately keep arithmetic functions that may factor
# their input (totient, Möbius, divisor sigma, square-free predicates, and
# multiplicative order) safe for in-process SymPy execution.
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


class FactorizationResourceBudget(ContractModel):
    """Execution budget for complete integer factorization-derived operations."""

    wall_seconds: StrictInt = Field(default=5, ge=1, le=30)


class FactorizationRequest(ContractModel):
    """One integer and an explicit budget for an isolated SymPy computation."""

    value: BoundedInteger
    resource_budget: FactorizationResourceBudget = Field(
        default_factory=FactorizationResourceBudget
    )


class PowerfulNumberRequest(FactorizationRequest):
    """One positive integer for an exact powerful-number decision."""

    @model_validator(mode="after")
    def require_positive_value(self) -> Self:
        if int(self.value) < 1:
            raise ValueError("powerful-number input must be positive")
        return self


class ArithmeticFunctionRequest(ContractModel):
    """A small nonnegative integer with an explicit factorization budget."""

    n: StrictInt = Field(ge=0, le=_MAX_N_SMALL)
    resource_budget: FactorizationResourceBudget = Field(
        default_factory=FactorizationResourceBudget
    )


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


class FloorSquareRootRequest(ContractModel):
    n: StrictInt = Field(ge=0, le=1_000_000_000_000)


class FloorSquareRootResult(ContractModel):
    """The exact floor of the nonnegative integer square root."""

    root: StrictInt = Field(ge=0, le=1_000_000)


class LegendreSymbolRequest(ContractModel):
    """Arguments for the Legendre symbol with a bounded odd prime denominator."""

    a: StrictInt = Field(ge=-(2**53 - 1), le=2**53 - 1)
    prime: StrictInt = Field(ge=3, le=10_000_000)

    @model_validator(mode="after")
    def require_odd_denominator(self) -> Self:
        if self.prime % 2 == 0:
            raise ValueError("Legendre denominator must be odd")
        return self


class LegendreSymbolResult(ContractModel):
    a: StrictInt
    prime: StrictInt = Field(ge=3, le=10_000_000)
    symbol: Literal[-1, 0, 1]


class FactorialValuationRequest(ContractModel):
    """Arguments for the largest exponent ``e`` such that ``base**e`` divides ``n!``."""

    n: StrictInt = Field(ge=0, le=100_000)
    base: StrictInt = Field(ge=2, le=1_000_000)


class FactorialValuationResult(ContractModel):
    n: StrictInt = Field(ge=0, le=100_000)
    base: StrictInt = Field(ge=2, le=1_000_000)
    valuation: StrictInt = Field(ge=0)


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
        if any(
            residue < 0 or residue >= modulus
            for residue, modulus in zip(self.residues, self.moduli, strict=True)
        ):
            raise ValueError("every residue must be canonical for its modulus")
        return self


class JacobiSymbolRequest(ContractModel):
    """Arguments for the Jacobi symbol (a / n), with odd positive n."""

    a: BoundedInteger
    n: StrictInt = Field(ge=3, le=_MAX_MODULUS)

    @model_validator(mode="after")
    def require_odd_denominator(self) -> Self:
        if self.n % 2 == 0:
            raise ValueError("Jacobi symbol denominator must be odd")
        return self


class DiscreteLogarithmBudget(ContractModel):
    """Total wall-clock budget for one isolated SymPy computation."""

    wall_seconds: StrictInt = Field(default=5, ge=1, le=30)


class DiscreteLogarithmRequest(ContractModel):
    """A bounded modular discrete-logarithm problem."""

    base: StrictInt = Field(ge=0, le=_MAX_MODULUS)
    target: StrictInt = Field(ge=0, le=_MAX_MODULUS)
    modulus: StrictInt = Field(ge=2, le=_MAX_MODULUS)
    resource_budget: DiscreteLogarithmBudget = Field(
        default_factory=DiscreteLogarithmBudget
    )

    @model_validator(mode="after")
    def require_canonical_residues(self) -> Self:
        if self.base >= self.modulus or self.target >= self.modulus:
            raise ValueError("base and target must be less than the modulus")
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


class PowerfulNumberResult(ContractModel):
    """A powerful-number decision with its complete factor witness."""

    semantics_version: Literal["powerful-number.prime-exponents-at-least-two.v1"]
    is_powerful: StrictBool
    factors: tuple[PrimePower, ...] = Field(
        min_length=0,
        max_length=_MAX_FACTOR_ENTRIES,
    )
    violating_primes: tuple[BoundedInteger, ...] = Field(
        min_length=0,
        max_length=_MAX_FACTOR_ENTRIES,
    )

    @model_validator(mode="after")
    def bind_decision_to_canonical_factor_witness(self) -> Self:
        primes = [int(factor.prime) for factor in self.factors]
        if any(prime < 2 for prime in primes):
            raise ValueError("factor bases must be greater than one")
        if primes != sorted(set(primes)):
            raise ValueError("factor bases must be strictly increasing")
        expected_violations = tuple(
            factor.prime for factor in self.factors if factor.power < 2
        )
        if self.violating_primes != expected_violations:
            raise ValueError(
                "violating primes must be exactly the factors with exponent below two"
            )
        if self.is_powerful != (not expected_violations):
            raise ValueError("powerful decision does not match the factor exponents")
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


class JacobiSymbolResult(ContractModel):
    """The exact Jacobi symbol, bound to its normalized arguments."""

    a: BoundedInteger
    n: StrictInt = Field(ge=3, le=_MAX_MODULUS)
    jacobi: Literal[-1, 0, 1]

    @model_validator(mode="after")
    def require_odd_denominator(self) -> Self:
        if self.n % 2 == 0:
            raise ValueError("Jacobi symbol denominator must be odd")
        return self


class DiscreteLogarithmResult(ContractModel):
    """A completed discrete-log result; interruption has a separate envelope."""

    status: Literal["SOLVED", "UNSOLVABLE"]
    base: StrictInt = Field(ge=0, le=_MAX_MODULUS)
    target: StrictInt = Field(ge=0, le=_MAX_MODULUS)
    modulus: StrictInt = Field(ge=2, le=_MAX_MODULUS)
    discrete_log: StrictInt | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def bind_conclusion(self) -> Self:
        if self.base >= self.modulus or self.target >= self.modulus:
            raise ValueError("base and target must be less than the modulus")
        if self.status == "SOLVED":
            if self.discrete_log is None:
                raise ValueError("solved discrete logarithm requires an exponent")
            if pow(self.base, self.discrete_log, self.modulus) != self.target:
                raise ValueError("discrete logarithm does not reproduce the target")
        elif self.discrete_log is not None:
            raise ValueError("unsolvable discrete logarithm cannot carry an exponent")
        return self


class DiscreteLogarithmObligation(ContractModel):
    """Independent checks still open for a completed producer result."""

    obligation_schema_version: Literal["1"] = "1"
    predicate: Literal["MODULAR_DISCRETE_LOGARITHM"] = "MODULAR_DISCRETE_LOGARITHM"
    base: StrictInt = Field(ge=0, le=_MAX_MODULUS)
    target: StrictInt = Field(ge=0, le=_MAX_MODULUS)
    modulus: StrictInt = Field(ge=2, le=_MAX_MODULUS)
    status: Literal["SOLVED", "UNSOLVABLE"]
    discrete_log: StrictInt | None = Field(default=None, ge=0)
    required_checks: tuple[
        Literal[
            "DISCRETE_LOG_WITNESS_REPLAY",
            "DISCRETE_LOG_NONSOLVABILITY",
        ],
        ...,
    ]

    @model_validator(mode="after")
    def require_status_specific_check(self) -> Self:
        if self.base >= self.modulus or self.target >= self.modulus:
            raise ValueError("base and target must be less than the modulus")
        expected = (
            ("DISCRETE_LOG_WITNESS_REPLAY",)
            if self.status == "SOLVED"
            else ("DISCRETE_LOG_NONSOLVABILITY",)
        )
        if self.required_checks != expected:
            raise ValueError("required checks must match the discrete-log status")
        if (self.discrete_log is None) != (self.status == "UNSOLVABLE"):
            raise ValueError("candidate exponent must match the discrete-log status")
        return self
