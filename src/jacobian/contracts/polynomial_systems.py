"""Exact rational polynomial-system verification contracts."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from jacobian.contracts.common import ArtifactUri, CheckerUri
from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.polynomials import PolynomialVariable, SparseRationalPolynomial
from jacobian.contracts.results import ContractModel


class RationalPolynomialSystem(ContractModel):
    system_schema_version: Literal["1"] = "1"
    domain: Literal["QQ"] = "QQ"
    variables: tuple[PolynomialVariable, ...] = Field(min_length=1, max_length=4)
    equations: tuple[SparseRationalPolynomial, ...] = Field(
        min_length=1,
        max_length=64,
    )
    inequations: tuple[SparseRationalPolynomial, ...] = Field(
        default=(),
        max_length=64,
    )

    @model_validator(mode="after")
    def require_one_declared_ring(self) -> Self:
        if len(set(self.variables)) != len(self.variables):
            raise ValueError("polynomial-system variables must be unique")
        dimension = len(self.variables)
        if any(
            len(term.exponents) != dimension
            for polynomial in (*self.equations, *self.inequations)
            for term in polynomial.terms
        ):
            raise ValueError("every system monomial must match the variable order")
        return self


class RationalPolynomialAssignment(ContractModel):
    assignment_schema_version: Literal["1"] = "1"
    values: tuple[CanonicalRational, ...] = Field(min_length=1, max_length=4)


class PolynomialSystemSolutionRequest(ContractModel):
    system: RationalPolynomialSystem
    assignment: tuple[CanonicalRational, ...] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def require_assignment_dimension(self) -> Self:
        if len(self.assignment) != len(self.system.variables):
            raise ValueError("assignment dimension must match the variable order")
        return self


class PolynomialSystemSolutionClaim(ContractModel):
    claim_schema_version: Literal["1"] = "1"
    predicate: Literal["ASSIGNMENT_SATISFIES_POLYNOMIAL_SYSTEM"] = (
        "ASSIGNMENT_SATISFIES_POLYNOMIAL_SYSTEM"
    )
    domain: Literal["QQ"] = "QQ"
    system_uri: ArtifactUri
    assignment_uri: ArtifactUri


class PolynomialSystemSolutionReplay(ContractModel):
    method: Literal["DIRECT_EXACT_EVALUATION"] = "DIRECT_EXACT_EVALUATION"
    system_uri: ArtifactUri
    assignment_uri: ArtifactUri


class PolynomialSystemSolutionOutput(ContractModel):
    satisfies: bool
    conclusion: Literal["TRUE", "FALSE", "UNKNOWN"]
    equation_residuals: tuple[CanonicalRational, ...]
    inequation_values: tuple[CanonicalRational, ...]
    system_uri: ArtifactUri
    assignment_uri: ArtifactUri
    claim_uri: ArtifactUri
    certificate_uri: ArtifactUri
    verification_record_uri: ArtifactUri | None = None
    checker_id: CheckerUri | None = None
    exactness: Literal["EXACT_RATIONAL"] = "EXACT_RATIONAL"
    determinism: Literal["DETERMINISTIC"] = "DETERMINISTIC"
