"""Contracts for pinned Lean certificate workflows."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, StrictInt, model_validator

from jacobian.contracts.common import ArtifactUri, Sha256Digest
from jacobian.contracts.results import ContractModel, ResultEnvelope


class LeanEnvironment(StrEnum):
    CORE = "CORE"
    MATHLIB = "MATHLIB"


class LeanClaim(ContractModel):
    lean_contract_version: Literal["1"] = "1"
    environment: LeanEnvironment = LeanEnvironment.CORE
    statement: str = Field(min_length=1, max_length=2_000)
    allowed_axioms: tuple[str, ...] = ()


class LeanCandidate(ContractModel):
    lean_contract_version: Literal["1"] = "1"
    environment: LeanEnvironment = LeanEnvironment.CORE
    statement: str = Field(min_length=1, max_length=2_000)
    proof: str = Field(min_length=1, max_length=20_000)


class LeanVerifyResult(ContractModel):
    claim_uri: ArtifactUri
    candidate_uri: ArtifactUri
    certificate_uri: ArtifactUri
    result: ResultEnvelope
    cache_hit: bool = False


class LeanDeclarationKind(StrEnum):
    AXIOM = "AXIOM"
    DEFINITION = "DEFINITION"
    THEOREM = "THEOREM"
    OPAQUE = "OPAQUE"
    QUOTIENT = "QUOTIENT"
    INDUCTIVE = "INDUCTIVE"
    CONSTRUCTOR = "CONSTRUCTOR"
    RECURSOR = "RECURSOR"


class LeanDeclarationMatchReason(StrEnum):
    NAME_SUBSTRING = "NAME_SUBSTRING"
    TYPE_CONSTANTS = "TYPE_CONSTANTS"


class LeanDeclarationSearchStopReason(StrEnum):
    RESULT_LIMIT = "RESULT_LIMIT"
    EXHAUSTED = "EXHAUSTED"


class LeanDeclarationSource(ContractModel):
    module: str | None = Field(default=None, min_length=1, max_length=512)
    line: StrictInt = Field(ge=1)
    column: StrictInt = Field(ge=0)
    end_line: StrictInt = Field(ge=1)
    end_column: StrictInt = Field(ge=0)


class LeanDeclarationRecord(ContractModel):
    name: str = Field(min_length=1, max_length=512)
    type: str = Field(min_length=1, max_length=20_000)
    kind: LeanDeclarationKind
    namespace: str | None = Field(default=None, min_length=1, max_length=512)
    docstring: str | None = Field(default=None, max_length=20_000)
    source: LeanDeclarationSource | None = None
    match_reasons: tuple[LeanDeclarationMatchReason, ...] = ()

    @model_validator(mode="after")
    def require_unique_match_reasons(self) -> Self:
        if len(set(self.match_reasons)) != len(self.match_reasons):
            raise ValueError("declaration match reasons must be unique")
        return self


class LeanDeclarationTypePattern(ContractModel):
    """All named constants must occur in the elaborated declaration type."""

    constants: tuple[str, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def require_distinct_constant_names(self) -> Self:
        _require_distinct_lean_names(
            self.constants, field_name="type pattern constants"
        )
        return self


class LeanDeclarationSearchRequest(ContractModel):
    environment: LeanEnvironment = LeanEnvironment.CORE
    name_contains: str | None = Field(default=None, min_length=1, max_length=256)
    type_pattern: LeanDeclarationTypePattern | None = None
    namespace_prefixes: tuple[str, ...] = Field(default=(), max_length=16)
    kinds: tuple[LeanDeclarationKind, ...] = ()
    result_limit: StrictInt = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def require_query_and_distinct_filters(self) -> Self:
        if self.name_contains is None and self.type_pattern is None:
            raise ValueError("name_contains or type_pattern is required")
        if self.name_contains is not None:
            _require_lean_text(self.name_contains, field_name="name_contains")
        _require_distinct_lean_names(
            self.namespace_prefixes,
            field_name="namespace prefixes",
        )
        if len(set(self.kinds)) != len(self.kinds):
            raise ValueError("declaration kinds must be unique")
        return self


class LeanDeclarationSearchOutput(ContractModel):
    environment: LeanEnvironment
    environment_digest: Sha256Digest
    query: LeanDeclarationSearchRequest
    declarations: tuple[LeanDeclarationRecord, ...]
    scanned_declarations: StrictInt = Field(ge=0)
    stop_reason: LeanDeclarationSearchStopReason

    @model_validator(mode="after")
    def bind_result_budget(self) -> Self:
        if len(self.declarations) > self.query.result_limit:
            raise ValueError("declaration results exceed the requested result limit")
        return self


class LeanDeclarationInspectRequest(ContractModel):
    environment: LeanEnvironment = LeanEnvironment.CORE
    declaration_name: str = Field(min_length=1, max_length=512)

    @model_validator(mode="after")
    def require_exact_name_text(self) -> Self:
        _require_lean_text(self.declaration_name, field_name="declaration_name")
        return self


class LeanDeclarationInspectOutput(ContractModel):
    environment: LeanEnvironment
    environment_digest: Sha256Digest
    query: LeanDeclarationInspectRequest
    declaration: LeanDeclarationRecord

    @model_validator(mode="after")
    def bind_exact_name(self) -> Self:
        if self.declaration.name != self.query.declaration_name:
            raise ValueError(
                "inspected declaration differs from the requested exact name"
            )
        return self


def _require_lean_text(value: str, *, field_name: str) -> None:
    if not value.strip() or "\x00" in value or any(char in "\r\n" for char in value):
        raise ValueError(f"{field_name} must be one non-empty Lean name fragment")


def _require_distinct_lean_names(
    values: tuple[str, ...],
    *,
    field_name: str,
) -> None:
    for value in values:
        _require_lean_text(value, field_name=field_name)
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must be unique")
