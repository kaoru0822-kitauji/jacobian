"""Contracts for exact polynomial invariants over ``QQ``."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, StrictInt, model_validator

from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.polynomials import (
    PolynomialVariable,
    RationalPolynomial,
)
from jacobian.contracts.results import ContractModel

_MAX_COEFFICIENT_DIGITS = 256
_MAX_GCD_TERMS = 512
_MAX_INVARIANT_TERMS = 256
_MAX_GCD_DEGREE = 127
_MAX_ELIMINATION_DEGREE_SUM = 64
_MAX_DISCRIMINANT_DEGREE = 32
_MAX_SQUARE_FREE_EXPONENT = 64


def _coefficient_digits(polynomial: RationalPolynomial) -> int:
    return max(
        (
            max(
                len(term.coefficient.num.lstrip("-")),
                len(term.coefficient.den),
            )
            for term in polynomial.polynomial.terms
        ),
        default=1,
    )


def _degree(polynomial: RationalPolynomial, variable_index: int) -> int:
    return max(
        (term.exponents[variable_index] for term in polynomial.polynomial.terms),
        default=0,
    )


def _require_polynomial_budget(
    polynomial: RationalPolynomial,
    *,
    maximum_terms: int,
    maximum_exponent: int,
) -> None:
    if len(polynomial.polynomial.terms) > maximum_terms:
        raise ValueError("polynomial exceeds the operation term budget")
    if _coefficient_digits(polynomial) > _MAX_COEFFICIENT_DIGITS:
        raise ValueError("polynomial coefficient exceeds the decimal-digit budget")
    if any(
        exponent > maximum_exponent
        for term in polynomial.polynomial.terms
        for exponent in term.exponents
    ):
        raise ValueError("polynomial exponent exceeds the operation degree budget")


class PolynomialPairRequest(ContractModel):
    """Two polynomials in one identical declared rational polynomial ring."""

    left: RationalPolynomial
    right: RationalPolynomial

    @model_validator(mode="after")
    def require_matching_rings(self) -> Self:
        if self.left.variables != self.right.variables:
            raise ValueError("polynomials must use the same ordered variables")
        return self


class PolynomialGcdRequest(PolynomialPairRequest):
    @model_validator(mode="after")
    def require_univariate_budget(self) -> Self:
        if len(self.left.variables) != 1:
            raise ValueError("Bézout GCD currently supports one variable over QQ")
        for polynomial in (self.left, self.right):
            _require_polynomial_budget(
                polynomial,
                maximum_terms=_MAX_GCD_TERMS,
                maximum_exponent=_MAX_GCD_DEGREE,
            )
        return self


class PolynomialBezoutIdentity(ContractModel):
    left_multiplier: RationalPolynomial
    right_multiplier: RationalPolynomial


class PolynomialGcdResult(ContractModel):
    gcd: RationalPolynomial
    bezout: PolynomialBezoutIdentity
    normalization: Literal["MONIC"] = "MONIC"


class PolynomialResultantRequest(PolynomialPairRequest):
    elimination_variable: PolynomialVariable

    @model_validator(mode="after")
    def require_elimination_budget(self) -> Self:
        if self.elimination_variable not in self.left.variables:
            raise ValueError("elimination variable must belong to the declared ring")
        for polynomial in (self.left, self.right):
            _require_polynomial_budget(
                polynomial,
                maximum_terms=_MAX_INVARIANT_TERMS,
                maximum_exponent=_MAX_ELIMINATION_DEGREE_SUM,
            )
        variable_index = self.left.variables.index(self.elimination_variable)
        degree_sum = _degree(self.left, variable_index) + _degree(
            self.right, variable_index
        )
        if degree_sum > _MAX_ELIMINATION_DEGREE_SUM:
            raise ValueError("Sylvester degree exceeds the resultant budget")
        return self


class PolynomialDiscriminantRequest(ContractModel):
    polynomial: RationalPolynomial
    variable: PolynomialVariable

    @model_validator(mode="after")
    def require_discriminant_budget(self) -> Self:
        if self.variable not in self.polynomial.variables:
            raise ValueError("discriminant variable must belong to the declared ring")
        _require_polynomial_budget(
            self.polynomial,
            maximum_terms=_MAX_INVARIANT_TERMS,
            maximum_exponent=_MAX_SQUARE_FREE_EXPONENT,
        )
        variable_index = self.polynomial.variables.index(self.variable)
        if _degree(self.polynomial, variable_index) > _MAX_DISCRIMINANT_DEGREE:
            raise ValueError("main-variable degree exceeds the discriminant budget")
        return self


class PolynomialScalarValue(ContractModel):
    kind: Literal["SCALAR"] = "SCALAR"
    value: CanonicalRational


class PolynomialValue(ContractModel):
    kind: Literal["POLYNOMIAL"] = "POLYNOMIAL"
    value: RationalPolynomial


PolynomialInvariantValue = Annotated[
    PolynomialScalarValue | PolynomialValue,
    Field(discriminator="kind"),
]


class PolynomialResultantResult(ContractModel):
    elimination_variable: PolynomialVariable
    resultant: PolynomialInvariantValue
    convention: Literal["SYLVESTER_DETERMINANT"] = "SYLVESTER_DETERMINANT"


class PolynomialDiscriminantResult(ContractModel):
    variable: PolynomialVariable
    discriminant: PolynomialInvariantValue
    convention: Literal["STANDARD_UNIVARIATE"] = "STANDARD_UNIVARIATE"


class PolynomialSquareFreeRequest(ContractModel):
    polynomial: RationalPolynomial

    @model_validator(mode="after")
    def require_square_free_budget(self) -> Self:
        _require_polynomial_budget(
            self.polynomial,
            maximum_terms=_MAX_GCD_TERMS,
            maximum_exponent=_MAX_SQUARE_FREE_EXPONENT,
        )
        return self


class PolynomialSquareFreeFactor(ContractModel):
    factor: RationalPolynomial
    multiplicity: int = Field(ge=1, le=_MAX_SQUARE_FREE_EXPONENT)


class PolynomialSquareFreeDecompositionResult(ContractModel):
    coefficient: CanonicalRational
    factors: tuple[PolynomialSquareFreeFactor, ...] = Field(max_length=64)
    reconstructed: RationalPolynomial
    normalization: Literal["MONIC_FACTORS"] = "MONIC_FACTORS"

    @model_validator(mode="after")
    def require_canonical_factor_records(self) -> Self:
        multiplicities = tuple(factor.multiplicity for factor in self.factors)
        if multiplicities != tuple(sorted(multiplicities)):
            raise ValueError("square-free factors must be ordered by multiplicity")
        if len(set(multiplicities)) != len(multiplicities):
            raise ValueError("each multiplicity must have one square-free factor")
        if any(
            factor.factor.variables != self.reconstructed.variables
            for factor in self.factors
        ):
            raise ValueError("square-free factors must use the source ring")
        return self


class PolynomialGroebnerBudget(ContractModel):
    """Enforced wall and result limits for one isolated Gröbner computation."""

    wall_seconds: StrictInt = Field(default=10, ge=1, le=60)
    maximum_basis_polynomials: StrictInt = Field(default=64, ge=1, le=64)
    maximum_output_terms: StrictInt = Field(default=1024, ge=1, le=1024)


class PolynomialGroebnerBasisRequest(ContractModel):
    generators: tuple[RationalPolynomial, ...] = Field(min_length=1, max_length=16)
    monomial_order: Literal["lex", "grlex", "grevlex"] = "grevlex"
    resource_budget: PolynomialGroebnerBudget = Field(
        default_factory=PolynomialGroebnerBudget
    )

    @model_validator(mode="after")
    def require_groebner_budget(self) -> Self:
        variables = self.generators[0].variables
        if any(generator.variables != variables for generator in self.generators):
            raise ValueError("all ideal generators must use the same ordered ring")
        if sum(len(generator.polynomial.terms) for generator in self.generators) > 256:
            raise ValueError("ideal generators exceed the aggregate term budget")
        for generator in self.generators:
            if _coefficient_digits(generator) > 128:
                raise ValueError(
                    "ideal generator coefficient exceeds the decimal-digit budget"
                )
            if any(sum(term.exponents) > 12 for term in generator.polynomial.terms):
                raise ValueError("ideal generator exceeds total degree 12")
        return self


class PolynomialGroebnerBasisResult(ContractModel):
    variables: tuple[PolynomialVariable, ...] = Field(min_length=1, max_length=4)
    monomial_order: Literal["lex", "grlex", "grevlex"]
    basis: tuple[RationalPolynomial, ...] = Field(max_length=64)
    completion: Literal["COMPLETE"] = "COMPLETE"
    normalization: Literal["REDUCED_MONIC"] = "REDUCED_MONIC"

    @model_validator(mode="after")
    def require_canonical_basis_ring(self) -> Self:
        if any(polynomial.variables != self.variables for polynomial in self.basis):
            raise ValueError("every basis polynomial must use the declared ring")
        if sum(len(polynomial.polynomial.terms) for polynomial in self.basis) > 1024:
            raise ValueError("Gröbner basis exceeds the aggregate output term limit")
        return self


class PolynomialGroebnerBasisObligation(ContractModel):
    """Independent obligations needed to verify the computed ideal basis."""

    obligation_schema_version: Literal["1"] = "1"
    candidate_basis_available: Literal[True] = True
    required_checks: tuple[
        Literal[
            "ORIGINAL_GENERATORS_REDUCE_TO_ZERO",
            "BASIS_ELEMENTS_BELONG_TO_SOURCE_IDEAL",
            "S_POLYNOMIALS_REDUCE_TO_ZERO",
            "BASIS_IS_REDUCED_AND_MONIC",
        ],
        ...,
    ] = (
        "ORIGINAL_GENERATORS_REDUCE_TO_ZERO",
        "BASIS_ELEMENTS_BELONG_TO_SOURCE_IDEAL",
        "S_POLYNOMIALS_REDUCE_TO_ZERO",
        "BASIS_IS_REDUCED_AND_MONIC",
    )
    verification_status: Literal["UNVERIFIED"] = "UNVERIFIED"


__all__ = [
    "PolynomialBezoutIdentity",
    "PolynomialDiscriminantRequest",
    "PolynomialDiscriminantResult",
    "PolynomialGcdRequest",
    "PolynomialGcdResult",
    "PolynomialGroebnerBasisObligation",
    "PolynomialGroebnerBasisRequest",
    "PolynomialGroebnerBasisResult",
    "PolynomialGroebnerBudget",
    "PolynomialInvariantValue",
    "PolynomialPairRequest",
    "PolynomialResultantRequest",
    "PolynomialResultantResult",
    "PolynomialScalarValue",
    "PolynomialSquareFreeDecompositionResult",
    "PolynomialSquareFreeFactor",
    "PolynomialSquareFreeRequest",
    "PolynomialValue",
]
