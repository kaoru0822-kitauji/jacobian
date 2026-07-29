"""Contracts for deterministic formal-dataset row materialization."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from jacobian.contracts.common import ArtifactUri, Sha256Digest
from jacobian.contracts.results import ContractModel


class MiniF2FRow(ContractModel):
    dataset_id: Literal["MINIF2F"]
    name: str = Field(min_length=1, max_length=256)
    split: Literal["train", "valid", "test"]
    formal_statement: str = Field(min_length=1, max_length=40_000)
    informal_statement: str | None = Field(default=None, max_length=40_000)
    informal_proof: str | None = Field(default=None, max_length=80_000)
    header: str = Field(default="", max_length=20_000)


class ProofNetRow(ContractModel):
    dataset_id: Literal["PROOFNET"]
    name: str = Field(min_length=1, max_length=256)
    split: str = Field(min_length=1, max_length=64)
    formal_statement: str = Field(min_length=1, max_length=80_000)
    informal_statement: str = Field(min_length=1, max_length=80_000)
    informal_proof: str | None = Field(default=None, max_length=120_000)
    header: str = Field(default="", max_length=20_000)


FormalDatasetRow = Annotated[
    MiniF2FRow | ProofNetRow,
    Field(discriminator="dataset_id"),
]


class FormalProjectFile(ContractModel):
    path: str = Field(min_length=1, max_length=512)
    digest: Sha256Digest

    @model_validator(mode="after")
    def require_safe_relative_path(self) -> Self:
        parts = self.path.split("/")
        if (
            self.path.startswith("/")
            or "\\" in self.path
            or "\x00" in self.path
            or ".." in parts
        ):
            raise ValueError("project file path must be a safe relative path")
        return self


class FormalDatasetEnvironment(ContractModel):
    lean_version: str = Field(min_length=1, max_length=64)
    project_revision: str = Field(min_length=1, max_length=128)
    mathlib_revision: str | None = Field(default=None, max_length=128)
    imports: tuple[str, ...] = Field(default=(), max_length=128)
    namespace: str | None = Field(default=None, max_length=512)
    theorem_context: tuple[str, ...] = Field(default=(), max_length=128)
    project_files: tuple[FormalProjectFile, ...] = Field(default=(), max_length=512)

    @model_validator(mode="after")
    def require_unique_ordered_bindings(self) -> Self:
        if len(set(self.imports)) != len(self.imports):
            raise ValueError("imports must be unique and ordered")
        if len(set(self.theorem_context)) != len(self.theorem_context):
            raise ValueError("theorem_context entries must be unique and ordered")
        paths = [item.path for item in self.project_files]
        if len(set(paths)) != len(paths):
            raise ValueError("project file paths must be unique")
        return self


class FormalPreprocessingDecision(ContractModel):
    operation: Literal[
        "NORMALIZE_NEWLINES",
        "TRIM_TRAILING_WHITESPACE",
        "ENSURE_FINAL_NEWLINE",
    ]
    applied: bool


class FormalDatasetMaterializeRequest(ContractModel):
    dataset_revision: str = Field(min_length=7, max_length=128)
    sample_id: str = Field(min_length=1, max_length=512)
    source_url: str = Field(min_length=1, max_length=2_000)
    row: FormalDatasetRow
    environment: FormalDatasetEnvironment
    expected_row_digest: Sha256Digest | None = None

    @model_validator(mode="after")
    def bind_dataset_identity(self) -> Self:
        if self.sample_id != self.row.name:
            raise ValueError("sample_id must equal the dataset row name")
        return self


class FormalDatasetDiagnostic(ContractModel):
    code: Literal[
        "EXECUTION_NOT_REQUESTED",
        "LEAN_VERSION_NOT_PINNED_RUNTIME",
        "MATHLIB_REVISION_NOT_PINNED_RUNTIME",
        "PROJECT_FILES_UNDECLARED",
    ]
    message: str = Field(min_length=1, max_length=2_000)


class FormalDatasetArtifact(ContractModel):
    artifact_version: Literal["1"] = "1"
    dataset_id: Literal["MINIF2F", "PROOFNET"]
    dataset_revision: str
    sample_id: str
    source_url: str
    row_digest: Sha256Digest
    normalized_source_digest: Sha256Digest
    normalized_source: str
    formal_statement: str
    informal_statement: str | None
    informal_proof: str | None
    header: str
    environment: FormalDatasetEnvironment
    environment_digest: Sha256Digest
    preprocessing: tuple[FormalPreprocessingDecision, ...]
    execution_status: Literal["NOT_EXECUTED"] = "NOT_EXECUTED"
    diagnostics: tuple[FormalDatasetDiagnostic, ...]
    assurance: Literal["UNVERIFIED"] = "UNVERIFIED"


class FormalDatasetMaterializeOutput(FormalDatasetArtifact):
    artifact_uri: ArtifactUri
