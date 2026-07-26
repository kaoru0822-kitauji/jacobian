"""Exact sparse rational-polynomial map contracts."""

from __future__ import annotations

from enum import StrEnum
from itertools import permutations
from math import prod
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from jacobian.contracts.common import ArtifactUri, CheckerUri
from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.results import ContractModel

PolynomialVariable = Annotated[
    str,
    StringConstraints(
        pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$",
        strict=True,
    ),
]
_MAX_SOURCE_EXPONENT = 32
_MAX_DERIVED_EXPONENT = 4 * _MAX_SOURCE_EXPONENT - 1
_MAX_JACOBIAN_PRODUCT_TERM_ESTIMATE = 1024


class RationalPolynomialTerm(ContractModel):
    coefficient: CanonicalRational
    exponents: tuple[int, ...] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def require_nonzero_coefficient_and_bounded_exponents(self) -> Self:
        if self.coefficient.as_fraction() == 0:
            raise ValueError("zero polynomial terms must be omitted")
        if any(
            exponent < 0 or exponent > _MAX_DERIVED_EXPONENT
            for exponent in self.exponents
        ):
            raise ValueError(
                "polynomial exponents exceed the bounded derived-polynomial limit"
            )
        return self


class SparseRationalPolynomial(ContractModel):
    terms: tuple[RationalPolynomialTerm, ...] = Field(
        default=(),
        max_length=1024,
    )

    @model_validator(mode="after")
    def require_unique_canonical_term_order(self) -> Self:
        exponents = tuple(term.exponents for term in self.terms)
        if len(set(exponents)) != len(exponents):
            raise ValueError("polynomial exponent tuples must be unique")
        if exponents != tuple(sorted(exponents, reverse=True)):
            raise ValueError("polynomial terms must use descending lexicographic order")
        return self


class RationalPolynomialMap(ContractModel):
    map_schema_version: Literal["1"] = "1"
    domain: Literal["QQ"] = "QQ"
    variables: tuple[PolynomialVariable, ...] = Field(min_length=1, max_length=4)
    coordinates: tuple[SparseRationalPolynomial, ...] = Field(
        min_length=1,
        max_length=4,
    )

    @model_validator(mode="after")
    def require_square_map_and_matching_monomials(self) -> Self:
        if len(set(self.variables)) != len(self.variables):
            raise ValueError("polynomial variables must be unique")
        if len(self.coordinates) != len(self.variables):
            raise ValueError("the first polynomial-map contract supports square maps")
        if any(
            len(term.exponents) != len(self.variables)
            for polynomial in self.coordinates
            for term in polynomial.terms
        ):
            raise ValueError("every monomial must match the declared variable order")
        if any(
            exponent > _MAX_SOURCE_EXPONENT
            for polynomial in self.coordinates
            for term in polynomial.terms
            for exponent in term.exponents
        ):
            raise ValueError("source polynomial exponents must be between zero and 32")
        return self


class RationalPolynomialPoint(ContractModel):
    values: tuple[CanonicalRational, ...] = Field(min_length=1, max_length=4)


class PolynomialEvaluationRequest(ContractModel):
    map: RationalPolynomialMap
    point: tuple[CanonicalRational, ...] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def require_point_dimension(self) -> Self:
        if len(self.point) != len(self.map.variables):
            raise ValueError("evaluation point dimension must match the polynomial map")
        return self


class PolynomialJacobianRequest(ContractModel):
    map: RationalPolynomialMap

    @model_validator(mode="after")
    def require_bounded_determinant_expansion(self) -> Self:
        dimension = len(self.map.variables)
        derivative_term_counts = tuple(
            tuple(
                sum(term.exponents[column] > 0 for term in polynomial.terms)
                for column in range(dimension)
            )
            for polynomial in self.map.coordinates
        )
        estimate = sum(
            prod(
                derivative_term_counts[row][permutation[row]]
                for row in range(dimension)
            )
            for permutation in permutations(range(dimension))
        )
        if estimate > _MAX_JACOBIAN_PRODUCT_TERM_ESTIMATE:
            raise ValueError(
                "Jacobian determinant expansion exceeds the exact operation budget"
            )
        return self


class PolynomialCollisionRequest(ContractModel):
    map: RationalPolynomialMap
    first_point: tuple[CanonicalRational, ...] = Field(min_length=1, max_length=4)
    second_point: tuple[CanonicalRational, ...] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def require_point_dimensions(self) -> Self:
        dimension = len(self.map.variables)
        if len(self.first_point) != dimension or len(self.second_point) != dimension:
            raise ValueError("collision point dimensions must match the polynomial map")
        return self


class PolynomialMapEvaluation(ContractModel):
    evaluation_schema_version: Literal["1"] = "1"
    map_uri: ArtifactUri
    point: RationalPolynomialPoint
    image: tuple[CanonicalRational, ...] = Field(min_length=1, max_length=4)
    backend: Literal["sympy"] = "sympy"
    backend_version: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def require_equal_point_and_image_dimensions(self) -> Self:
        if len(self.point.values) != len(self.image):
            raise ValueError("evaluation point and image dimensions must agree")
        return self


class PolynomialJacobian(ContractModel):
    jacobian_schema_version: Literal["1"] = "1"
    map_uri: ArtifactUri
    variable_order: tuple[PolynomialVariable, ...] = Field(
        min_length=1,
        max_length=4,
    )
    matrix: tuple[tuple[SparseRationalPolynomial, ...], ...] = Field(
        min_length=1,
        max_length=4,
    )
    determinant: SparseRationalPolynomial
    backend: Literal["sympy"] = "sympy"
    backend_version: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def require_square_jacobian(self) -> Self:
        dimension = len(self.variable_order)
        if len(self.matrix) != dimension or any(
            len(row) != dimension for row in self.matrix
        ):
            raise ValueError("Jacobian matrix must match the variable order")
        if any(
            len(term.exponents) != dimension
            for row in self.matrix
            for polynomial in row
            for term in polynomial.terms
        ) or any(len(term.exponents) != dimension for term in self.determinant.terms):
            raise ValueError("Jacobian monomials must match the variable order")
        return self


class PolynomialInjectivityClaim(ContractModel):
    claim_schema_version: Literal["1"] = "1"
    predicate: Literal["POLYNOMIAL_MAP_INJECTIVE"] = "POLYNOMIAL_MAP_INJECTIVE"
    domain: Literal["QQ"] = "QQ"
    map_uri: ArtifactUri


class PolynomialJacobianClaim(ContractModel):
    claim_schema_version: Literal["1"] = "1"
    predicate: Literal["EXACT_POLYNOMIAL_JACOBIAN"] = "EXACT_POLYNOMIAL_JACOBIAN"
    source_map_uri: ArtifactUri


class PolynomialJacobianReplayPayload(ContractModel):
    method: Literal["DIRECT_SPARSE_REPLAY"] = "DIRECT_SPARSE_REPLAY"
    source_map_uri: ArtifactUri
    jacobian_uri: ArtifactUri


class PolynomialCollisionPayload(ContractModel):
    first_point: tuple[CanonicalRational, ...] = Field(min_length=1, max_length=4)
    second_point: tuple[CanonicalRational, ...] = Field(min_length=1, max_length=4)
    image: tuple[CanonicalRational, ...] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def require_matching_dimensions(self) -> Self:
        if not (len(self.first_point) == len(self.second_point) == len(self.image)):
            raise ValueError("collision points and image dimensions must agree")
        return self


class PolynomialExactness(StrEnum):
    EXACT = "EXACT"


class PolynomialDeterminism(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"


class PolynomialVerificationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"


class PolynomialEvaluationOutput(ContractModel):
    map_uri: ArtifactUri
    evaluation_uri: ArtifactUri
    point: tuple[CanonicalRational, ...]
    image: tuple[CanonicalRational, ...]
    exactness: PolynomialExactness = PolynomialExactness.EXACT
    determinism: PolynomialDeterminism = PolynomialDeterminism.DETERMINISTIC
    verification: PolynomialVerificationStatus = PolynomialVerificationStatus.UNVERIFIED
    certificate_available: Literal[False] = False
    checker_id: None = None
    backend: Literal["sympy"] = "sympy"
    backend_version: str

    @model_validator(mode="after")
    def require_equal_point_and_image_dimensions(self) -> Self:
        if len(self.point) != len(self.image):
            raise ValueError("evaluation output dimensions must agree")
        return self


class PolynomialJacobianOutput(ContractModel):
    map_uri: ArtifactUri
    jacobian_uri: ArtifactUri
    claim_uri: ArtifactUri
    certificate_uri: ArtifactUri
    checker_id: CheckerUri | None = None
    matrix: tuple[tuple[SparseRationalPolynomial, ...], ...]
    determinant: SparseRationalPolynomial
    exactness: PolynomialExactness = PolynomialExactness.EXACT
    determinism: PolynomialDeterminism = PolynomialDeterminism.DETERMINISTIC
    verification: PolynomialVerificationStatus = PolynomialVerificationStatus.UNVERIFIED
    certificate_available: Literal[True] = True
    backend: Literal["sympy"] = "sympy"
    backend_version: str


class PolynomialCollisionOutput(ContractModel):
    claim_uri: ArtifactUri
    candidate_uri: ArtifactUri
    first_evaluation_uri: ArtifactUri
    second_evaluation_uri: ArtifactUri
    first_point: tuple[CanonicalRational, ...]
    second_point: tuple[CanonicalRational, ...]
    first_image: tuple[CanonicalRational, ...]
    second_image: tuple[CanonicalRational, ...]
    is_collision: bool
    witness_uri: ArtifactUri | None = None
    checker_id: CheckerUri | None = None
    exactness: PolynomialExactness = PolynomialExactness.EXACT
    determinism: PolynomialDeterminism = PolynomialDeterminism.DETERMINISTIC
    verification: PolynomialVerificationStatus = PolynomialVerificationStatus.UNVERIFIED
    certificate_available: bool
    backend: Literal["sympy"] = "sympy"
    backend_version: str

    @model_validator(mode="after")
    def witness_matches_collision(self) -> Self:
        if not (
            len(self.first_point)
            == len(self.second_point)
            == len(self.first_image)
            == len(self.second_image)
        ):
            raise ValueError("collision output point and image dimensions must agree")
        expected_collision = (
            self.first_point != self.second_point
            and self.first_image == self.second_image
        )
        if self.is_collision != expected_collision:
            raise ValueError(
                "collision status must match distinct points with equal images"
            )
        if self.is_collision != (self.witness_uri is not None):
            raise ValueError("only exact collisions may carry a witness")
        if self.certificate_available != (
            self.witness_uri is not None and self.checker_id is not None
        ):
            raise ValueError("certificate availability requires witness and checker")
        return self
