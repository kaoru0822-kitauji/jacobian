"""Domain-independent claim specification and validation results."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from jacobian.canonical import canonicalize_json
from jacobian.contracts.common import ArtifactUri, Sha256Digest
from jacobian.contracts.plugins import (
    CapabilityName,
    DomainIdentifier,
)
from jacobian.contracts.results import (
    ContractModel,
    Execution,
    InputValidation,
)

ClaimName = Annotated[
    str,
    StringConstraints(
        pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*$",
        min_length=1,
        max_length=128,
        strict=True,
    ),
]
VariableName = Annotated[
    str,
    StringConstraints(
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
        min_length=1,
        max_length=128,
        strict=True,
    ),
]


class QuantifierKind(StrEnum):
    FOR_ALL = "FOR_ALL"
    EXISTS = "EXISTS"


class CorrespondenceStatus(StrEnum):
    UNREVIEWED = "UNREVIEWED"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"
    FORMALLY_LINKED = "FORMALLY_LINKED"


class QuantifierSpec(ContractModel):
    kind: QuantifierKind
    variable: VariableName
    domain: str = Field(min_length=1, max_length=256)


class PredicateSpec(ContractModel):
    name: ClaimName
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_canonical_parameters(self) -> Self:
        canonicalize_json(self.parameters)
        return self


class ClaimSpec(ContractModel):
    """Auditable bounded claim metadata.

    The model intentionally describes quantifier structure and bindings rather
    than attempting to define a universal language for mathematics.
    """

    claim_schema_version: Literal["1"] = "1"
    domain_id: DomainIdentifier
    domain_version: str = Field(min_length=1, max_length=64)
    semantics_uri: ArtifactUri
    quantifiers: tuple[QuantifierSpec, ...] = ()
    predicate: PredicateSpec
    bounds: dict[str, Any] = Field(default_factory=dict)
    required_capabilities: tuple[CapabilityName, ...] = ()
    correspondence_status: CorrespondenceStatus

    @model_validator(mode="after")
    def validate_generic_structure(self) -> Self:
        variables = tuple(item.variable for item in self.quantifiers)
        if len(set(variables)) != len(variables):
            raise ValueError("quantified variable names must be unique")
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise ValueError("required capabilities must be unique")
        canonicalize_json(self.bounds)
        return self


def flatten_claim_spec(value: object) -> object:
    """Project a generic claim artifact into a plugin request claim shape."""

    if not isinstance(value, dict) or not isinstance(value.get("predicate"), dict):
        return value
    claim = ClaimSpec.model_validate(value)
    return {
        "predicate": claim.predicate.name,
        **claim.predicate.parameters,
        **claim.bounds,
    }


class ClaimValidationResult(ContractModel):
    schema_version: Literal["1"] = "1"
    execution: Execution
    input: InputValidation
    valid: bool
    claim_uri: ArtifactUri
    plugin_id: ArtifactUri
    claim_digest: Sha256Digest | None = None
    resolved_semantics_digest: Sha256Digest | None = None
    required_capabilities: tuple[CapabilityName, ...] = ()
    available_capabilities: tuple[CapabilityName, ...] = ()
    missing_capabilities: tuple[CapabilityName, ...] = ()

    @model_validator(mode="after")
    def keep_validity_and_input_status_consistent(self) -> Self:
        accepted = self.input.status.value == "ACCEPTED"
        if self.valid != accepted:
            raise ValueError("valid must agree with input validation status")
        if self.valid and self.missing_capabilities:
            raise ValueError("valid claims cannot have missing capabilities")
        return self
