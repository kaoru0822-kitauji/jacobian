"""Domain-owned request contracts for the integer-matrix reference plugin."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, StrictInt, StrictStr, model_validator

from jacobian.contracts.claims import ClaimSpec
from jacobian.contracts.plugin_protocol import PluginRequestContext
from jacobian.contracts.results import ContractModel


def _flatten_claim(value: object) -> object:
    if not isinstance(value, dict) or not isinstance(value.get("predicate"), dict):
        return value
    claim = ClaimSpec.model_validate(value)
    return {
        "predicate": claim.predicate.name,
        **claim.predicate.parameters,
        **claim.bounds,
    }


class MatrixScope(ContractModel):
    rows: StrictInt = Field(ge=1, le=32)
    cols: StrictInt = Field(ge=1, le=32)
    entries: tuple[StrictInt | StrictStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_entries(self) -> Self:
        for value in self.entries:
            if isinstance(value, str) and (
                not value or not value.lstrip("-").isdigit()
            ):
                raise ValueError("scope entries must be exact integers")
        return self


class MatrixClaim(ContractModel):
    predicate: Literal["is_nonsingular", "maximize_absolute_determinant"]
    scope: MatrixScope | None = None

    @model_validator(mode="before")
    @classmethod
    def flatten_generic_claim(cls, value: object) -> object:
        return _flatten_claim(value)

    @model_validator(mode="after")
    def validate_scope_for_predicate(self) -> Self:
        if self.predicate == "maximize_absolute_determinant":
            if self.scope is None:
                raise ValueError("maximize_absolute_determinant requires a scope")
            if self.scope.rows != self.scope.cols:
                raise ValueError("determinant scope must be square")
        return self


class MatrixCandidate(ContractModel):
    rows: StrictInt = Field(ge=1, le=32)
    cols: StrictInt = Field(ge=1, le=32)
    entries: tuple[tuple[StrictInt | StrictStr, ...], ...]

    @model_validator(mode="after")
    def validate_matrix_shape(self) -> Self:
        if len(self.entries) != self.rows or any(
            len(row) != self.cols for row in self.entries
        ):
            raise ValueError("matrix entries must match rows and cols")
        for value in (item for row in self.entries for item in row):
            if (
                isinstance(value, bool)
                or (
                    isinstance(value, str)
                    and (not value or not value.lstrip("-").isdigit())
                )
                or not isinstance(value, (int, str))
            ):
                raise ValueError("matrix entries must be exact integers")
        return self


class MatrixEvaluationRequest(PluginRequestContext):
    claim: MatrixClaim
    candidate: MatrixCandidate | None = None
    candidates: tuple[MatrixCandidate, ...] | None = None

    @model_validator(mode="after")
    def require_candidates(self) -> Self:
        if self.candidate is not None and self.candidates is not None:
            raise ValueError("candidate and candidates cannot be combined")
        if self.candidate is None and not self.candidates:
            raise ValueError("at least one candidate is required")
        return self


class MatrixCapabilityRequest(PluginRequestContext):
    claim: MatrixClaim
    candidate: MatrixCandidate | None = None
    witness_role: Literal["DEFEATS_CANDIDATE", "SUPPORTS_CLAIM"] = "DEFEATS_CANDIDATE"


class MatrixReductionRequest(PluginRequestContext):
    target_kind: Literal["candidate"] = "candidate"
    target: MatrixCandidate
    claim: MatrixClaim
    reducers: tuple[Literal["delete_row_column", "zero_entry"], ...] = ()
    objectives: tuple[Literal["elements", "max_abs_entry"], ...] = ()


class MatrixCursor(ContractModel):
    offset: StrictInt = Field(ge=0)


class MatrixEnumerationRequest(PluginRequestContext):
    bounds: MatrixScope
    page_size: StrictInt = Field(ge=1)
    cursor: MatrixCursor | None = None


class MatrixTransformRequest(PluginRequestContext):
    requested_relation: Literal[
        "EQUIVALENT", "OVER_APPROXIMATION", "UNDER_APPROXIMATION", "HEURISTIC"
    ] = "EQUIVALENT"
    target_schema_uri: StrictStr | None = None
    target_semantics_uri: StrictStr | None = None
    source: MatrixCandidate


class MatrixMaterializeRequest(PluginRequestContext):
    claim: MatrixClaim


__all__ = [
    "MatrixCandidate",
    "MatrixCapabilityRequest",
    "MatrixClaim",
    "MatrixCursor",
    "MatrixEnumerationRequest",
    "MatrixEvaluationRequest",
    "MatrixMaterializeRequest",
    "MatrixReductionRequest",
    "MatrixScope",
    "MatrixTransformRequest",
]
