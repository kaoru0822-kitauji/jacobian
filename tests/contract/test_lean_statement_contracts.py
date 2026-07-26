"""Contract tests for Lean statement proposal, repair, and comparison."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.lean_statement import (
    LeanProofRepairArtifact,
    LeanProofRepairRequest,
    LeanStatementComparisonArtifact,
    LeanStatementComparisonRequest,
    LeanStatementProposalArtifact,
    LeanStatementProposalRequest,
)

ARTIFACT_URI = "artifact://sha256/" + "a" * 64


# ---------------------------------------------------------------------------
# LeanStatementProposalRequest
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_proposal_request_rejects_multiline_statement() -> None:
    with pytest.raises(ValidationError, match="one Lean expression"):
        LeanStatementProposalRequest(
            informal_claim="trivial",
            proposed_statement="1 + 1\n= 2",
        )


@pytest.mark.contract
def test_proposal_request_rejects_declaration_syntax() -> None:
    with pytest.raises(ValidationError, match=":="):
        LeanStatementProposalRequest(
            informal_claim="trivial",
            proposed_statement="theorem foo : True := trivial",
        )


@pytest.mark.contract
def test_proposal_request_accepts_valid_input() -> None:
    req = LeanStatementProposalRequest(
        informal_claim="one plus one equals two",
        proposed_statement="1 + 1 = 2",
        source_locator="https://example.com/claim",
    )
    assert req.environment.value == "CORE"
    assert req.source_locator == "https://example.com/claim"


# ---------------------------------------------------------------------------
# LeanStatementProposalArtifact
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_proposal_artifact_requires_sorry_when_elaborates() -> None:
    with pytest.raises(ValidationError, match="at least one sorry"):
        LeanStatementProposalArtifact(
            environment="CORE",
            informal_claim="trivial",
            proposed_statement="1 + 1 = 2",
            elaborates=True,
            sorry_count=0,
            goals=(),
            messages=(),
            lean_version="4.0.0",
            lean_commit="abc",
        )


@pytest.mark.contract
def test_proposal_artifact_accepts_non_elaborating_with_zero_sorry() -> None:
    artifact = LeanStatementProposalArtifact(
        environment="CORE",
        informal_claim="trivial",
        proposed_statement="bogus syntax",
        elaborates=False,
        sorry_count=0,
        goals=(),
        messages=("error: unknown identifier",),
        lean_version="4.0.0",
        lean_commit="abc",
    )
    assert artifact.elaborates is False
    assert artifact.sorry_count == 0


# ---------------------------------------------------------------------------
# LeanProofRepairRequest
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_repair_request_rejects_multiline_statement() -> None:
    with pytest.raises(ValidationError, match="one Lean expression"):
        LeanProofRepairRequest(
            statement="True\n",
            failing_proof="trivial",
        )


@pytest.mark.contract
def test_repair_request_accepts_multiline_proof() -> None:
    req = LeanProofRepairRequest(
        statement="True",
        failing_proof="intro\n  trivial",
        compiler_errors=("unsolved goals",),
    )
    assert "\n" in req.failing_proof
    assert len(req.compiler_errors) == 1


# ---------------------------------------------------------------------------
# LeanProofRepairArtifact
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_repair_artifact_requires_proof_change_for_non_none_strategy() -> None:
    with pytest.raises(ValidationError, match="must change the proof"):
        LeanProofRepairArtifact(
            environment="CORE",
            statement="True",
            failing_proof="trivial",
            repaired_proof="trivial",
            diff="",
            repair_strategy="append_sorry",
            compiles=False,
            compile_checked=False,
            sorry_count=0,
            messages=(),
            lean_version="4.0.0",
            lean_commit="abc",
        )


@pytest.mark.contract
def test_repair_artifact_rejects_proof_change_for_none_strategy() -> None:
    with pytest.raises(ValidationError, match="must not change the proof"):
        LeanProofRepairArtifact(
            environment="CORE",
            statement="True",
            failing_proof="trivial",
            repaired_proof="sorry",
            diff="diff",
            repair_strategy="none",
            compiles=False,
            compile_checked=False,
            sorry_count=0,
            messages=(),
            lean_version="4.0.0",
            lean_commit="abc",
        )


@pytest.mark.contract
def test_repair_artifact_accepts_none_strategy_with_unchanged_proof() -> None:
    artifact = LeanProofRepairArtifact(
        environment="CORE",
        statement="True",
        failing_proof="trivial",
        repaired_proof="trivial",
        diff="",
        repair_strategy="none",
        compiles=False,
        compile_checked=False,
        sorry_count=0,
        messages=(),
        lean_version="4.0.0",
        lean_commit="abc",
    )
    assert artifact.repair_strategy == "none"


# ---------------------------------------------------------------------------
# LeanStatementComparisonRequest
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_comparison_request_rejects_multiline_statement_a() -> None:
    with pytest.raises(ValidationError, match="statement_a"):
        LeanStatementComparisonRequest(
            statement_a="True\n",
            statement_b="True",
        )


@pytest.mark.contract
def test_comparison_request_rejects_declaration_in_statement_b() -> None:
    with pytest.raises(ValidationError, match="statement_b"):
        LeanStatementComparisonRequest(
            statement_a="True",
            statement_b="theorem foo : True := trivial",
        )


@pytest.mark.contract
def test_comparison_request_accepts_axiom_sets() -> None:
    req = LeanStatementComparisonRequest(
        statement_a="True",
        statement_b="True",
        axiom_set_a=("Classical.choice",),
        axiom_set_b=("Classical.choice",),
    )
    assert req.axiom_set_a == ("Classical.choice",)


# ---------------------------------------------------------------------------
# LeanStatementComparisonArtifact
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_comparison_artifact_rejects_both_elaborate_without_check() -> None:
    with pytest.raises(ValidationError, match="both_elaborate"):
        LeanStatementComparisonArtifact(
            environment="CORE",
            statement_a="True",
            statement_b="True",
            axiom_set_a=(),
            axiom_set_b=(),
            statements_identical=True,
            axiom_sets_identical=True,
            both_elaborate=True,
            elaboration_checked=False,
            elaboration_messages_a=(),
            elaboration_messages_b=(),
            lean_version="4.0.0",
            lean_commit="abc",
        )


@pytest.mark.contract
def test_comparison_artifact_accepts_no_elaboration_when_unchecked() -> None:
    artifact = LeanStatementComparisonArtifact(
        environment="CORE",
        statement_a="True",
        statement_b="True",
        axiom_set_a=(),
        axiom_set_b=(),
        statements_identical=True,
        axiom_sets_identical=True,
        both_elaborate=False,
        elaboration_checked=False,
        elaboration_messages_a=(),
        elaboration_messages_b=(),
        lean_version="unknown",
        lean_commit="unknown",
    )
    assert artifact.elaboration_checked is False
    assert artifact.both_elaborate is False
