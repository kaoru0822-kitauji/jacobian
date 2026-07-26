"""Integration tests for Lean statement proposal, repair, and comparison."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import jacobian.lean_statement_capabilities as lean_statements
from jacobian.artifacts import ArtifactService
from jacobian.capabilities import CapabilityInvocationError
from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityRequest,
)
from jacobian.contracts.lean_statement import LeanElaborationOption
from jacobian.contracts.results import ExecutionStatus
from jacobian.lean_statement_capabilities import (
    LeanProofRepairAdapter,
    LeanStatementCompareAdapter,
    LeanStatementProposalAdapter,
    install_lean_statement_capabilities,
)
from jacobian.schema_registry import SchemaRegistry
from jacobian.store import ArtifactStore

LEAN_AVAILABLE = shutil.which("lean") is not None

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


def _build_adapters(
    tmp_path: Path,
) -> tuple[
    LeanStatementProposalAdapter,
    LeanProofRepairAdapter,
    LeanStatementCompareAdapter,
]:
    store = ArtifactStore(tmp_path)
    schemas = SchemaRegistry(store)
    artifacts = ArtifactService(store, schemas)
    adapters, _installation = install_lean_statement_capabilities(
        store, schemas, artifacts
    )
    return adapters


# ---------------------------------------------------------------------------
# lean.statement.propose
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not LEAN_AVAILABLE, reason="Lean is not installed")
def test_propose_elaborates_valid_statement(tmp_path: Path) -> None:
    propose, _, _ = _build_adapters(tmp_path)

    result = propose.invoke(
        CapabilityRequest(
            capability_id="lean.statement.propose",
            input={
                "environment": "CORE",
                "informal_claim": "one plus one equals two",
                "proposed_statement": "1 + 1 = 2",
            },
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["elaborates"] is True
    assert result.output["sorry_count"] == 1
    assert result.output["verification"] == "UNVERIFIED"
    assert result.output["proposal_uri"] in result.artifact_uris
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert "does not certify" in result.assurance.basis


@pytest.mark.skipif(not LEAN_AVAILABLE, reason="Lean is not installed")
def test_propose_reports_elaboration_failure(tmp_path: Path) -> None:
    propose, _, _ = _build_adapters(tmp_path)

    result = propose.invoke(
        CapabilityRequest(
            capability_id="lean.statement.propose",
            input={
                "environment": "CORE",
                "informal_claim": "bogus claim",
                "proposed_statement": "1 + + 1 = 2",
            },
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["elaborates"] is False
    assert result.output["sorry_count"] == 0
    assert len(result.output["messages"]) > 0


def test_propose_rejects_forbidden_statement(tmp_path: Path) -> None:
    propose, _, _ = _build_adapters(tmp_path)

    with pytest.raises(CapabilityInvocationError) as exc_info:
        propose.invoke(
            CapabilityRequest(
                capability_id="lean.statement.propose",
                input={
                    "environment": "CORE",
                    "informal_claim": "bogus",
                    "proposed_statement": "sorry",
                },
            )
        )

    assert exc_info.value.diagnostic.code == "INVALID_LEAN_STATEMENT_PROPOSAL"


def test_propose_rejects_mathlib_environment(tmp_path: Path) -> None:
    propose, _, _ = _build_adapters(tmp_path)

    with pytest.raises(CapabilityInvocationError) as exc_info:
        propose.invoke(
            CapabilityRequest(
                capability_id="lean.statement.propose",
                input={
                    "environment": "MATHLIB",
                    "informal_claim": "claim",
                    "proposed_statement": "1 + 1 = 2",
                },
            )
        )

    assert exc_info.value.diagnostic.code == "LEAN_ENVIRONMENT_UNSUPPORTED"


def test_propose_returns_diagnostic_when_lean_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    propose, _, _ = _build_adapters(tmp_path)

    with pytest.raises(CapabilityInvocationError) as exc_info:
        propose.invoke(
            CapabilityRequest(
                capability_id="lean.statement.propose",
                input={
                    "environment": "CORE",
                    "informal_claim": "one plus one equals two",
                    "proposed_statement": "1 + 1 = 2",
                },
            )
        )

    assert exc_info.value.diagnostic.code == "LEAN_BACKEND_UNAVAILABLE"


def test_propose_directly_elaborates_environment_bound_proposition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        lean_statements,
        "_elaborate_proposition",
        lambda _statement: lean_statements._ElaborationResult(
            elaborates=True,
            sorry_count=0,
            messages=(
                "fixture.lean:4:0: info: "
                "@Eq.{1} Nat (@OfNat.ofNat Nat 1 instOfNatNat) "
                "(@OfNat.ofNat Nat 1 instOfNatNat) : Prop",
            ),
            errors=(),
            elaborated_expression=(
                "@Eq.{1} Nat (@OfNat.ofNat Nat 1 instOfNatNat) "
                "(@OfNat.ofNat Nat 1 instOfNatNat)"
            ),
            used_imports=("Init.Prelude",),
            used_declarations=("Eq", "Nat", "OfNat.ofNat", "instOfNatNat"),
            options=(
                LeanElaborationOption(name="pp.all", value="true"),
                LeanElaborationOption(name="pp.explicit", value="true"),
                LeanElaborationOption(name="pp.universes", value="true"),
            ),
        ),
    )
    monkeypatch.setattr(
        lean_statements,
        "_lean_version_info",
        lambda: ("4.31.0", "lean-commit"),
    )
    propose, _, _ = _build_adapters(tmp_path)

    result = propose.invoke(
        CapabilityRequest(
            capability_id="lean.statement.propose",
            input={
                "operation": "ELABORATE_PROPOSITION",
                "environment": "CORE",
                "proposed_statement": "1 = 1",
            },
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["operation"] == "ELABORATE_PROPOSITION"
    assert result.output["informal_claim"] is None
    assert result.output["elaborates"] is True
    assert result.output["sorry_count"] == 0
    assert result.output["elaborated_expression"].startswith("@Eq")
    assert result.output["used_imports"] == ["Init.Prelude"]
    assert "Eq" in result.output["used_declarations"]
    assert result.output["options"][0] == {"name": "pp.all", "value": "true"}
    assert result.output["semantic_scope"] == "ELABORATION_ONLY"
    assert result.output["truth_status"] == "NOT_ASSESSED"
    assert result.output["verification"] == "UNVERIFIED"
    assert result.output["environment_digest"].startswith("sha256:")

    artifact = propose.resources.store.get(result.output["proposal_uri"])
    assert artifact.payload["environment_digest"] == result.output["environment_digest"]
    assert (
        artifact.payload["elaborated_expression"]
        == result.output["elaborated_expression"]
    )
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert "does not establish truth" in result.assurance.basis


def test_direct_elaboration_parser_preserves_multiline_core_expression() -> None:
    output = (
        "fixture.lean:4:0: info: @Eq.{1} Nat\n"
        "  (@OfNat.ofNat Nat 1 instOfNatNat)\n"
        "  (@OfNat.ofNat Nat 1 instOfNatNat) : Prop\n"
    )

    assert lean_statements._parse_elaborated_expression(output) == (
        "@Eq.{1} Nat (@OfNat.ofNat Nat 1 instOfNatNat) "
        "(@OfNat.ofNat Nat 1 instOfNatNat)"
    )


# ---------------------------------------------------------------------------
# lean.proof.repair_once
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not LEAN_AVAILABLE, reason="Lean is not installed")
def test_repair_appends_sorry_for_unsolved_goals(tmp_path: Path) -> None:
    _, repair, _ = _build_adapters(tmp_path)

    result = repair.invoke(
        CapabilityRequest(
            capability_id="lean.proof.repair_once",
            input={
                "environment": "CORE",
                "statement": "True ∧ True",
                "failing_proof": "constructor",
                "compiler_errors": ["unsolved goals"],
            },
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["repair_strategy"] == "append_sorry"
    assert result.output["diff"] != ""
    assert result.output["repaired_proof"] != result.output["failing_proof"]
    assert result.output["compile_checked"] is True
    assert result.output["verification"] == "UNVERIFIED"
    assert result.output["repair_uri"] in result.artifact_uris


@pytest.mark.skipif(not LEAN_AVAILABLE, reason="Lean is not installed")
def test_repair_adds_by_when_missing(tmp_path: Path) -> None:
    _, repair, _ = _build_adapters(tmp_path)

    result = repair.invoke(
        CapabilityRequest(
            capability_id="lean.proof.repair_once",
            input={
                "environment": "CORE",
                "statement": "True",
                "failing_proof": "trivial",
                "compiler_errors": ["expected tactic"],
            },
        )
    )

    assert result.output["repair_strategy"] == "add_by"
    assert result.output["repaired_proof"].startswith("by")


def test_repair_returns_none_strategy_when_no_errors(tmp_path: Path) -> None:
    _, repair, _ = _build_adapters(tmp_path)

    result = repair.invoke(
        CapabilityRequest(
            capability_id="lean.proof.repair_once",
            input={
                "environment": "CORE",
                "statement": "True",
                "failing_proof": "trivial",
                "compiler_errors": [],
            },
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["repair_strategy"] == "none"
    assert result.output["diff"] == ""
    assert result.output["repaired_proof"] == result.output["failing_proof"]


def test_repair_produces_diff_without_compile_check_when_lean_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    _, repair, _ = _build_adapters(tmp_path)

    result = repair.invoke(
        CapabilityRequest(
            capability_id="lean.proof.repair_once",
            input={
                "environment": "CORE",
                "statement": "True",
                "failing_proof": "trivial",
                "compiler_errors": ["expected tactic"],
            },
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["repair_strategy"] == "add_by"
    assert result.output["diff"] != ""
    assert result.output["compile_checked"] is False
    assert result.output["compiles"] is False
    assert result.completeness.status is CapabilityCompletenessStatus.PARTIAL


def test_repair_rejects_dangerous_proof(tmp_path: Path) -> None:
    _, repair, _ = _build_adapters(tmp_path)

    with pytest.raises(CapabilityInvocationError) as exc_info:
        repair.invoke(
            CapabilityRequest(
                capability_id="lean.proof.repair_once",
                input={
                    "environment": "CORE",
                    "statement": "True",
                    "failing_proof": "import Mathlib",
                    "compiler_errors": [],
                },
            )
        )

    assert exc_info.value.diagnostic.code == "INVALID_LEAN_PROOF_REPAIR_REQUEST"


# ---------------------------------------------------------------------------
# lean.statement.compare
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not LEAN_AVAILABLE, reason="Lean is not installed")
def test_compare_identical_statements(tmp_path: Path) -> None:
    _, _, compare = _build_adapters(tmp_path)

    result = compare.invoke(
        CapabilityRequest(
            capability_id="lean.statement.compare",
            input={
                "environment": "CORE",
                "statement_a": "1 + 1 = 2",
                "statement_b": "1 + 1 = 2",
                "axiom_set_a": [],
                "axiom_set_b": [],
            },
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["statements_identical"] is True
    assert result.output["axiom_sets_identical"] is True
    assert result.output["elaboration_checked"] is True
    assert result.output["both_elaborate"] is True
    assert result.output["verification"] == "UNVERIFIED"
    assert result.output["comparison_uri"] in result.artifact_uris


@pytest.mark.skipif(not LEAN_AVAILABLE, reason="Lean is not installed")
def test_compare_different_statements(tmp_path: Path) -> None:
    _, _, compare = _build_adapters(tmp_path)

    result = compare.invoke(
        CapabilityRequest(
            capability_id="lean.statement.compare",
            input={
                "environment": "CORE",
                "statement_a": "1 + 1 = 2",
                "statement_b": "1 + 1 = 3",
                "axiom_set_a": ["Classical.choice"],
                "axiom_set_b": [],
            },
        )
    )

    assert result.output["statements_identical"] is False
    assert result.output["axiom_sets_identical"] is False


def test_compare_works_without_lean_for_syntactic_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    _, _, compare = _build_adapters(tmp_path)

    result = compare.invoke(
        CapabilityRequest(
            capability_id="lean.statement.compare",
            input={
                "environment": "CORE",
                "statement_a": "1 + 1 = 2",
                "statement_b": "1 + 1 = 2",
            },
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["statements_identical"] is True
    assert result.output["elaboration_checked"] is False
    assert result.output["both_elaborate"] is False
    assert result.completeness.status is CapabilityCompletenessStatus.PARTIAL


def test_compare_normalizes_whitespace(tmp_path: Path) -> None:
    _, _, compare = _build_adapters(tmp_path)

    result = compare.invoke(
        CapabilityRequest(
            capability_id="lean.statement.compare",
            input={
                "environment": "CORE",
                "statement_a": "1 + 1  =  2",
                "statement_b": "1 + 1 = 2",
            },
        )
    )

    assert result.output["statements_identical"] is True


def test_compare_rejects_forbidden_statement(tmp_path: Path) -> None:
    _, _, compare = _build_adapters(tmp_path)

    with pytest.raises(CapabilityInvocationError) as exc_info:
        compare.invoke(
            CapabilityRequest(
                capability_id="lean.statement.compare",
                input={
                    "environment": "CORE",
                    "statement_a": "sorry",
                    "statement_b": "True",
                },
            )
        )

    assert exc_info.value.diagnostic.code == "INVALID_LEAN_STATEMENT_COMPARISON"


# ---------------------------------------------------------------------------
# Descriptor checks.
# ---------------------------------------------------------------------------


def test_descriptors_have_correct_ids_and_modes(tmp_path: Path) -> None:
    propose, repair, compare = _build_adapters(tmp_path)

    assert propose.descriptor.capability_id == "lean.statement.propose"
    assert repair.descriptor.capability_id == "lean.proof.repair_once"
    assert compare.descriptor.capability_id == "lean.statement.compare"
    for adapter in (propose, repair, compare):
        assert adapter.descriptor.modes == (
            __import__(
                "jacobian.contracts.capabilities", fromlist=["CapabilityMode"]
            ).CapabilityMode.EXPLORE,
        )
