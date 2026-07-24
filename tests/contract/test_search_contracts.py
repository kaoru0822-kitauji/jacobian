from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from jacobian.contracts.discovery import ExperimentState
from jacobian.contracts.results import (
    InputStatus,
    InputValidation,
    Verification,
)
from jacobian.contracts.search import (
    PluginProposalResponse,
    SearchAccounting,
    SearchBudget,
    SearchCandidateRecord,
    SearchExperimentSnapshot,
    SearchRunRequest,
    SearchStopReason,
)

ARTIFACT = "artifact://sha256/" + "a" * 64
PLUGIN = "artifact://sha256/" + "b" * 64
CHECKER = "checker://sha256/" + "c" * 64
EXPERIMENT = "experiment://0123456789abcdef0123456789abcdef"
NOW = datetime(2026, 7, 24, tzinfo=UTC)
DIGEST = "sha256:" + "d" * 64


def _request() -> SearchRunRequest:
    return SearchRunRequest(
        idempotency_key="search-contract-001",
        claim_uri=ARTIFACT,
        plugin_id=PLUGIN,
        initial_state={"cursor": 0},
        witness_role="DEFEATS_CANDIDATE",
        counterexample_checker_id=CHECKER,
        budget=SearchBudget(
            candidates_max=10,
            iterations_max=5,
            wall_seconds=30,
            batch_size=2,
            workers=1,
        ),
    )


def _snapshot(**changes: object) -> SearchExperimentSnapshot:
    values: dict[str, object] = {
        "experiment_uri": EXPERIMENT,
        "state": ExperimentState.RUNNING,
        "request": _request(),
        "input": InputValidation(status=InputStatus.ACCEPTED),
        "created_at": NOW,
        "updated_at": NOW,
        "request_digest": DIGEST,
        "effective_budget": _request().budget,
        "registry_snapshot_uri": ARTIFACT,
        "environment_digest": DIGEST,
    }
    values.update(changes)
    return SearchExperimentSnapshot.model_validate(values)


def test_search_budget_rejects_unimplemented_parallel_workers() -> None:
    with pytest.raises(ValidationError, match="less than or equal to 1"):
        SearchBudget(
            candidates_max=10,
            iterations_max=5,
            wall_seconds=30,
            workers=2,
        )


def test_search_request_requires_complete_counterexample_verification_policy() -> None:
    with pytest.raises(
        ValidationError,
        match="witness role and counterexample checker must be configured together",
    ):
        SearchRunRequest(
            idempotency_key="search-contract-002",
            claim_uri=ARTIFACT,
            plugin_id=PLUGIN,
            initial_state={},
            witness_role="DEFEATS_CANDIDATE",
            budget=SearchBudget(
                candidates_max=1,
                iterations_max=1,
                wall_seconds=1,
            ),
        )


def test_search_counterexample_policy_rejects_supporting_witness_roles() -> None:
    with pytest.raises(
        ValidationError,
        match="requires a defeating or refuting witness",
    ):
        SearchRunRequest(
            idempotency_key="search-contract-003",
            claim_uri=ARTIFACT,
            plugin_id=PLUGIN,
            witness_role="RESCUES_CANDIDATE",
            counterexample_checker_id=CHECKER,
            budget=SearchBudget(
                candidates_max=1,
                iterations_max=1,
                wall_seconds=1,
            ),
        )


def test_proposer_cannot_stall_without_reporting_completion() -> None:
    with pytest.raises(
        ValidationError,
        match="proposer must return candidates or report completion",
    ):
        PluginProposalResponse(
            candidates=(),
            state={"cursor": 0},
            complete=False,
        )


def test_verified_counterexample_requires_bound_witness_and_record() -> None:
    with pytest.raises(
        ValidationError,
        match="verified counterexample requires witness and verification record",
    ):
        SearchCandidateRecord(
            candidate_uri=ARTIFACT,
            evaluation_uri=ARTIFACT,
            counterexample_verified=True,
        )


def test_search_accounting_rejects_impossible_counts() -> None:
    with pytest.raises(
        ValidationError,
        match="unique and duplicate counts must equal proposed candidates",
    ):
        SearchAccounting(
            proposed_candidates=3,
            unique_candidates=1,
            duplicate_candidates=1,
        )


def test_search_snapshot_keeps_pause_and_terminal_states_distinct() -> None:
    paused = _snapshot(state=ExperimentState.PAUSED)
    assert paused.stop_reason is None

    with pytest.raises(
        ValidationError,
        match="terminal search state and stop reason disagree",
    ):
        _snapshot(
            state=ExperimentState.TIMEOUT,
            stop_reason=SearchStopReason.STRATEGY_COMPLETE,
        )


def test_search_snapshot_can_never_self_certify() -> None:
    with pytest.raises(
        ValidationError,
        match="search experiments cannot self-certify",
    ):
        _snapshot(verification=Verification.VERIFIED)


def test_strategy_completion_is_an_operational_stop_not_verification() -> None:
    snapshot = _snapshot(
        state=ExperimentState.COMPLETED,
        stop_reason=SearchStopReason.STRATEGY_COMPLETE,
        strategy_reported_complete=True,
    )

    assert snapshot.verification is Verification.UNVERIFIED
