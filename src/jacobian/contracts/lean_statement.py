"""Contracts for atomic Lean statement proposal, repair, and comparison.

Each contract exposes exactly one inspectable artifact. None of these
capabilities certify that a formal statement matches an informal claim,
that a repaired proof proves a theorem, or that two statements are
semantically equivalent. The ``verification`` field is always
``UNVERIFIED`` to enforce the fail-closed boundary.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from jacobian.contracts.common import ArtifactUri
from jacobian.contracts.lean import LeanEnvironment
from jacobian.contracts.results import ContractModel

# ---------------------------------------------------------------------------
# lean.statement.propose
# ---------------------------------------------------------------------------


class LeanStatementProposalRequest(ContractModel):
    """Type-check one proposed Lean statement against an informal claim."""

    environment: LeanEnvironment = LeanEnvironment.CORE
    informal_claim: str = Field(min_length=1, max_length=4_000)
    proposed_statement: str = Field(min_length=1, max_length=2_000)
    source_locator: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def require_single_line_statement(self) -> Self:
        if "\n" in self.proposed_statement or "\r" in self.proposed_statement:
            raise ValueError("proposed_statement must be one Lean expression")
        if ":=" in self.proposed_statement:
            raise ValueError("proposed_statement must not contain ':='")
        return self


class LeanStatementProposalArtifact(ContractModel):
    """One type-checked Lean statement proposal with elaboration status."""

    proposal_schema_version: Literal["1"] = "1"
    environment: LeanEnvironment
    informal_claim: str
    proposed_statement: str
    elaborates: bool
    sorry_count: int = Field(ge=0)
    goals: tuple[str, ...]
    messages: tuple[str, ...]
    lean_version: str
    lean_commit: str
    mathlib_commit: str | None = None
    source_locator: str | None = None

    @model_validator(mode="after")
    def require_nonnegative_sorry_when_elaborates(self) -> Self:
        if self.elaborates and self.sorry_count < 1:
            raise ValueError(
                "an elaborating proposal must report at least one sorry "
                "because the type-check proof uses sorry"
            )
        return self


class LeanStatementProposalOutput(LeanStatementProposalArtifact):
    """Proposal output with artifact URI and explicit UNVERIFIED label."""

    proposal_uri: ArtifactUri
    verification: Literal["UNVERIFIED"] = "UNVERIFIED"


# ---------------------------------------------------------------------------
# lean.proof.repair_once
# ---------------------------------------------------------------------------


class LeanProofRepairRequest(ContractModel):
    """Attempt one deterministic repair on a failing Lean proof."""

    environment: LeanEnvironment = LeanEnvironment.CORE
    statement: str = Field(min_length=1, max_length=2_000)
    failing_proof: str = Field(min_length=1, max_length=20_000)
    compiler_errors: tuple[str, ...] = Field(default=(), max_length=20)

    @model_validator(mode="after")
    def require_single_line_statement(self) -> Self:
        if "\n" in self.statement or "\r" in self.statement:
            raise ValueError("statement must be one Lean expression")
        if ":=" in self.statement:
            raise ValueError("statement must not contain ':='")
        return self


class LeanProofRepairArtifact(ContractModel):
    """One repair attempt with diff and compile status."""

    repair_schema_version: Literal["1"] = "1"
    environment: LeanEnvironment
    statement: str
    failing_proof: str
    repaired_proof: str
    diff: str
    repair_strategy: str = Field(min_length=1, max_length=64)
    compiles: bool
    compile_checked: bool
    sorry_count: int = Field(ge=0)
    messages: tuple[str, ...]
    lean_version: str
    lean_commit: str

    @model_validator(mode="after")
    def require_diff_when_strategy_applied(self) -> Self:
        if self.repair_strategy != "none" and self.repaired_proof == self.failing_proof:
            raise ValueError("a non-'none' repair strategy must change the proof")
        if self.repair_strategy == "none" and self.repaired_proof != self.failing_proof:
            raise ValueError("the 'none' strategy must not change the proof")
        return self


class LeanProofRepairOutput(LeanProofRepairArtifact):
    """Repair output with artifact URI and explicit UNVERIFIED label."""

    repair_uri: ArtifactUri
    verification: Literal["UNVERIFIED"] = "UNVERIFIED"


# ---------------------------------------------------------------------------
# lean.statement.compare
# ---------------------------------------------------------------------------


class LeanStatementComparisonRequest(ContractModel):
    """Compare two Lean statements and their axiom sets (fail-closed)."""

    environment: LeanEnvironment = LeanEnvironment.CORE
    statement_a: str = Field(min_length=1, max_length=2_000)
    statement_b: str = Field(min_length=1, max_length=2_000)
    axiom_set_a: tuple[str, ...] = Field(default=(), max_length=64)
    axiom_set_b: tuple[str, ...] = Field(default=(), max_length=64)

    @model_validator(mode="after")
    def require_single_line_statements(self) -> Self:
        for value, field_name in (
            (self.statement_a, "statement_a"),
            (self.statement_b, "statement_b"),
        ):
            if "\n" in value or "\r" in value:
                raise ValueError(f"{field_name} must be one Lean expression")
            if ":=" in value:
                raise ValueError(f"{field_name} must not contain ':='")
        return self

    @model_validator(mode="after")
    def require_valid_axiom_names(self) -> Self:
        for axioms, field_name in (
            (self.axiom_set_a, "axiom_set_a"),
            (self.axiom_set_b, "axiom_set_b"),
        ):
            for axiom in axioms:
                if not axiom.strip() or "\x00" in axiom or "\n" in axiom:
                    raise ValueError(f"{field_name} contains an invalid axiom name")
        return self


class LeanStatementComparisonArtifact(ContractModel):
    """Syntactic and axiom-set comparison result (no semantic equivalence)."""

    comparison_schema_version: Literal["1"] = "1"
    environment: LeanEnvironment
    statement_a: str
    statement_b: str
    axiom_set_a: tuple[str, ...]
    axiom_set_b: tuple[str, ...]
    statements_identical: bool
    axiom_sets_identical: bool
    both_elaborate: bool
    elaboration_checked: bool
    elaboration_messages_a: tuple[str, ...]
    elaboration_messages_b: tuple[str, ...]
    lean_version: str
    lean_commit: str

    @model_validator(mode="after")
    def require_elaboration_checked_when_both_elaborate(self) -> Self:
        if self.both_elaborate and not self.elaboration_checked:
            raise ValueError(
                "both_elaborate cannot be True when elaboration was not checked"
            )
        return self


class LeanStatementComparisonOutput(LeanStatementComparisonArtifact):
    """Comparison output with artifact URI and explicit UNVERIFIED label."""

    comparison_uri: ArtifactUri
    verification: Literal["UNVERIFIED"] = "UNVERIFIED"
