"""Closed wire contracts for small exact arithmetic capabilities."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.results import ContractModel

BoundedInteger = Annotated[
    str,
    StringConstraints(
        pattern=r"^-?(?:0|[1-9][0-9]*)$",
        max_length=256,
        strict=True,
    ),
]
PrimitiveMathValue = str | bool | tuple[str, ...] | dict[str, str | bool]


class IntegerValueRequest(ContractModel):
    value: BoundedInteger


class NonnegativeIntegerRequest(ContractModel):
    n: int = Field(ge=0, le=1_000)


class IntegerPairRequest(ContractModel):
    left: BoundedInteger
    right: BoundedInteger


class NonnegativePairRequest(ContractModel):
    n: int = Field(ge=0, le=1_000)
    k: int = Field(ge=0, le=1_000)


class IntegerModulusRequest(ContractModel):
    value: BoundedInteger
    modulus: int = Field(ge=2, le=10_000)


class IntegerListRequest(ContractModel):
    values: tuple[BoundedInteger, ...] = Field(min_length=1, max_length=256)


class IntegerSetPairRequest(ContractModel):
    left: tuple[BoundedInteger, ...] = Field(max_length=128)
    right: tuple[BoundedInteger, ...] = Field(max_length=128)


class RationalValueRequest(ContractModel):
    value: CanonicalRational


class RationalPairRequest(ContractModel):
    left: CanonicalRational
    right: CanonicalRational


class ChineseRemainderRequest(ContractModel):
    residues: tuple[int, ...] = Field(min_length=1, max_length=64)
    moduli: tuple[int, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def require_parallel_positive_moduli(self) -> ChineseRemainderRequest:
        if len(self.residues) != len(self.moduli):
            raise ValueError("residues and moduli must have equal length")
        if any(modulus < 2 or modulus > 10_000 for modulus in self.moduli):
            raise ValueError("every modulus must be between 2 and 10,000")
        return self


class PrimitiveMathArtifact(ContractModel):
    artifact_schema_version: str = "1"
    capability_id: str
    input_uri: str
    result: PrimitiveMathValue
    backend_version: str


class PrimitiveMathOutput(ContractModel):
    input_uri: str
    result_uri: str
    result: PrimitiveMathValue
    backend_version: str
