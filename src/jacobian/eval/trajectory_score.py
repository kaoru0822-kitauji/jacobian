"""Observation-only replay scoring for offline trajectory-value estimates.

The scorer joins an immutable PR2 comparison into an inspectable trajectory.
It does not invoke a model or tool, choose an action, mutate a prompt or
runtime, or participate in mathematical assurance.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal, Self

from pydantic import ConfigDict, Field, model_validator

from jacobian.contracts.results import ContractModel
from jacobian.eval.trajectory_state import StateBoundary
from jacobian.eval.trajectory_value import (
    ClusterSummary,
    EstimatorEvaluation,
    EstimatorKind,
    OfflineValueComparison,
    StateValueEstimate,
    ValueSource,
)

_DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"
_IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9._-]{0,127}$"


class TrajectoryScoreError(ValueError):
    """A comparison cannot support the requested observation-only replay."""


class TerminalResult(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class CreditReason(StrEnum):
    INITIAL_STATE = "INITIAL_STATE"
    NON_MILESTONE_ZERO = "NON_MILESTONE_ZERO"
    MILESTONE_VALUE_DELTA = "MILESTONE_VALUE_DELTA"


class ScoredTrajectoryState(ContractModel):
    observation_id: str = Field(min_length=3, max_length=256)
    trajectory_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    task_group: str = Field(pattern=_IDENTIFIER_PATTERN)
    state_index: int = Field(ge=0, strict=True)
    boundary: StateBoundary
    typed_state_digest: str = Field(pattern=_DIGEST_PATTERN)
    milestone_eligible: bool
    estimator: EstimatorKind
    cluster_id: str = Field(pattern=_DIGEST_PATTERN)
    cluster_feature_summary: str = Field(min_length=1, max_length=1024)
    value_source: ValueSource
    supporting_trajectory_ids: tuple[str, ...] = Field(min_length=1)
    estimated_value: float = Field(ge=0.0, le=1.0)
    previous_observation_id: str | None = Field(default=None, max_length=256)
    value_delta: float | None = Field(default=None, ge=-1.0, le=1.0)
    transition_credit: float = Field(ge=-1.0, le=1.0)
    cumulative_milestone_credit: float = Field(ge=-1000.0, le=1000.0)
    credit_reason: CreditReason
    eventual_terminal_result: TerminalResult
    eventual_terminal_reward: Literal[0, 1]
    observation_only: Literal[True] = True
    assurance_authority: Literal[False] = False

    @model_validator(mode="after")
    def require_local_credit_semantics(self) -> Self:
        if self.previous_observation_id is None:
            if self.value_delta is not None or self.transition_credit != 0.0:
                raise ValueError("initial state has no delta and zero credit")
            if self.credit_reason is not CreditReason.INITIAL_STATE:
                raise ValueError("initial state requires the initial credit reason")
        elif self.value_delta is None:
            raise ValueError("non-initial state requires a value delta")
        if not self.milestone_eligible and self.transition_credit != 0.0:
            raise ValueError("non-milestone transition credit must be zero")
        if (
            self.previous_observation_id is not None
            and self.milestone_eligible
            and self.transition_credit != self.value_delta
        ):
            raise ValueError("milestone credit must equal the estimated value delta")
        return self


class TrajectoryScoreReplay(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "$id": "https://jacobian.invalid/docs/reference/evaluations/schemas/trajectory-score-replay-v1.schema.json"
        },
    )

    replay_schema_version: Literal["1"] = "1"
    scorer_id: Literal["jacobian.observation-only-trajectory-scorer.v1"] = (
        "jacobian.observation-only-trajectory-scorer.v1"
    )
    comparison_digest: str = Field(pattern=_DIGEST_PATTERN)
    source_corpus_digest: str = Field(pattern=_DIGEST_PATTERN)
    trajectory_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    task_group: str = Field(pattern=_IDENTIFIER_PATTERN)
    estimator: EstimatorKind
    eventual_terminal_result: TerminalResult
    eventual_terminal_reward: Literal[0, 1]
    states: tuple[ScoredTrajectoryState, ...] = Field(min_length=1)
    total_milestone_credit: float = Field(ge=-1000.0, le=1000.0)
    credit_semantics: Literal[
        "non-milestone=0;milestone=current-value-minus-previous-selected-value"
    ] = "non-milestone=0;milestone=current-value-minus-previous-selected-value"
    observation_only: Literal[True] = True
    chooses_tools: Literal[False] = False
    changes_prompts: Literal[False] = False
    mutates_runtime: Literal[False] = False
    assurance_authority: Literal[False] = False

    @model_validator(mode="after")
    def require_bound_ordered_replay(self) -> Self:
        _require_bound_ordered_replay(self)
        return self


def _require_bound_ordered_replay(replay: TrajectoryScoreReplay) -> None:
    _require_replay_boundaries(replay.states)
    _require_replay_state_bindings(replay)
    _require_replay_state_order(replay.states)
    _require_replay_terminal_bindings(replay)
    _require_replay_total_credit(replay)
    _require_replay_credit_chain(replay.states)


def _require_replay_boundaries(states: tuple[ScoredTrajectoryState, ...]) -> None:
    if states[0].boundary is not StateBoundary.PLAN:
        raise ValueError("replay must begin at a PLAN observation")


def _require_replay_state_bindings(replay: TrajectoryScoreReplay) -> None:
    if any(state.trajectory_id != replay.trajectory_id for state in replay.states):
        raise ValueError("replay state trajectory identity mismatch")
    if any(state.task_group != replay.task_group for state in replay.states):
        raise ValueError("replay state task-group mismatch")
    if any(state.estimator is not replay.estimator for state in replay.states):
        raise ValueError("replay state estimator mismatch")


def _require_replay_state_order(states: tuple[ScoredTrajectoryState, ...]) -> None:
    state_indices = tuple(state.state_index for state in states)
    if state_indices != tuple(sorted(state_indices)):
        raise ValueError("replay states must be ordered by source state index")
    if len(set(state_indices)) != len(states):
        raise ValueError("replay state indices must be unique")


def _require_replay_terminal_bindings(replay: TrajectoryScoreReplay) -> None:
    if any(
        state.eventual_terminal_reward != replay.eventual_terminal_reward
        or state.eventual_terminal_result is not replay.eventual_terminal_result
        for state in replay.states
    ):
        raise ValueError("replay states must share the bound terminal result")


def _require_replay_total_credit(replay: TrajectoryScoreReplay) -> None:
    if replay.total_milestone_credit != replay.states[-1].cumulative_milestone_credit:
        raise ValueError("total credit must equal the last cumulative credit")


def _require_replay_credit_chain(states: tuple[ScoredTrajectoryState, ...]) -> None:
    running_cumulative = 0.0
    previous_id: str | None = None
    previous_value: float | None = None
    for index, state in enumerate(states):
        _require_replay_previous_link(index, state, previous_id, previous_value)
        running_cumulative = _round_value(running_cumulative + state.transition_credit)
        if state.cumulative_milestone_credit != running_cumulative:
            raise ValueError(
                "replay cumulative credit must equal the running total of transition credits"
            )
        previous_id = state.observation_id
        previous_value = state.estimated_value


def _require_replay_previous_link(
    index: int,
    state: ScoredTrajectoryState,
    previous_id: str | None,
    previous_value: float | None,
) -> None:
    if index == 0:
        if state.previous_observation_id is not None:
            raise ValueError(
                "initial replay state must not reference a previous observation"
            )
        return
    if state.previous_observation_id != previous_id:
        raise ValueError(
            "replay state previous observation must chain to its predecessor"
        )
    if previous_value is None:
        raise ValueError("non-initial replay state requires a previous estimated value")
    expected_delta = _round_value(state.estimated_value - previous_value)
    if state.value_delta is None or state.value_delta != expected_delta:
        raise ValueError(
            "replay value delta must equal the adjacent estimated value difference"
        )


def _round_value(value: float) -> float:
    return round(value, 12)


def _comparison_digest(comparison: OfflineValueComparison) -> str:
    payload = json.dumps(
        comparison.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _evaluation(
    comparison: OfflineValueComparison, estimator: EstimatorKind
) -> EstimatorEvaluation:
    matches = tuple(
        evaluation
        for evaluation in comparison.evaluations
        if evaluation.estimator is estimator
    )
    if len(matches) != 1:
        raise TrajectoryScoreError(
            "comparison does not contain one requested estimator"
        )
    return matches[0]


def _terminal_result(reward: Literal[0, 1]) -> TerminalResult:
    return TerminalResult.ACCEPTED if reward == 1 else TerminalResult.REJECTED


def _trajectory_bindings(
    estimates: tuple[StateValueEstimate, ...],
) -> tuple[Literal[0, 1], str, TerminalResult]:
    rewards = {estimate.eventual_terminal_reward for estimate in estimates}
    task_groups = {estimate.task_group for estimate in estimates}
    if len(rewards) != 1 or len(task_groups) != 1:
        raise TrajectoryScoreError("trajectory estimates have inconsistent bindings")
    reward = rewards.pop()
    return reward, task_groups.pop(), _terminal_result(reward)


def _comparison_trajectory_rewards(
    comparison: OfflineValueComparison,
) -> dict[str, Literal[0, 1]]:
    trajectory_rewards: dict[str, Literal[0, 1]] = {}
    for evaluation_check in comparison.evaluations:
        for estimate in evaluation_check.estimates:
            trajectory_rewards.setdefault(
                estimate.trajectory_id, estimate.eventual_terminal_reward
            )
    return trajectory_rewards


def _validate_estimates(
    evaluation: EstimatorEvaluation,
    trajectory_id: str,
) -> tuple[tuple[StateValueEstimate, ...], dict[str, ClusterSummary]]:
    estimates = tuple(
        sorted(
            (
                estimate
                for estimate in evaluation.estimates
                if estimate.trajectory_id == trajectory_id
            ),
            key=lambda estimate: estimate.state_index,
        )
    )
    if not estimates:
        raise TrajectoryScoreError("trajectory is absent from the comparison")
    if len({estimate.observation_id for estimate in estimates}) != len(estimates):
        raise TrajectoryScoreError(
            "trajectory estimates have duplicate observation ids"
        )
    if len({estimate.state_index for estimate in estimates}) != len(estimates):
        raise TrajectoryScoreError("trajectory estimates have duplicate state indices")
    if any(
        estimate.observation_id != f"{trajectory_id}:{estimate.state_index}"
        for estimate in estimates
    ):
        raise TrajectoryScoreError(
            "observation identity is not bound to its state index"
        )
    if (
        estimates[0].boundary is not StateBoundary.PLAN
        or estimates[0].state_index != 0
        or estimates[0].milestone_eligible
    ):
        raise TrajectoryScoreError("trajectory replay must begin with PLAN")
    clusters = {cluster.cluster_id: cluster for cluster in evaluation.clusters}
    if len(clusters) != len(evaluation.clusters):
        raise TrajectoryScoreError("estimator has duplicate cluster ids")
    if any(
        len(set(cluster.member_observation_ids)) != len(cluster.member_observation_ids)
        for cluster in evaluation.clusters
    ):
        raise TrajectoryScoreError("cluster has duplicate observation members")
    return estimates, clusters


def _validated_cluster(
    estimate: StateValueEstimate,
    cluster: ClusterSummary | None,
) -> ClusterSummary:
    if cluster is None or estimate.observation_id not in cluster.member_observation_ids:
        raise TrajectoryScoreError("estimate is not bound to its declared cluster")
    if estimate.cluster_member_observation_ids != cluster.member_observation_ids:
        raise TrajectoryScoreError("estimate carries a stale cluster member set")
    if estimate.value_source is ValueSource.CLUSTER:
        _validate_cluster_support(estimate, cluster)
    return cluster


def _validate_cluster_support(
    estimate: StateValueEstimate,
    cluster: ClusterSummary,
) -> None:
    cluster_trajectories = set(cluster.member_trajectory_ids)
    if estimate.trajectory_id in cluster_trajectories:
        cluster_trajectories.discard(estimate.trajectory_id)
    support_set = set(estimate.supporting_trajectory_ids)
    if not support_set or not support_set.issubset(cluster_trajectories):
        raise TrajectoryScoreError(
            "estimate declares cluster support outside its cluster members"
        )


def _estimate_delta(
    previous: StateValueEstimate | None,
    estimate: StateValueEstimate,
) -> float | None:
    if previous is None:
        return None
    return _round_value(estimate.estimated_value - previous.estimated_value)


def _transition_credit(delta: float | None, milestone_eligible: bool) -> float:
    if milestone_eligible and delta is not None:
        return delta
    return 0.0


def _credit_reason(
    previous: StateValueEstimate | None,
    estimate: StateValueEstimate,
) -> CreditReason:
    if previous is None:
        return CreditReason.INITIAL_STATE
    if estimate.milestone_eligible:
        return CreditReason.MILESTONE_VALUE_DELTA
    return CreditReason.NON_MILESTONE_ZERO


def _previous_observation_id(previous: StateValueEstimate | None) -> str | None:
    if previous is None:
        return None
    return previous.observation_id


def _scored_state(
    estimate: StateValueEstimate,
    *,
    estimator: EstimatorKind,
    cluster: ClusterSummary,
    previous: StateValueEstimate | None,
    cumulative: float,
    terminal: TerminalResult,
    reward: Literal[0, 1],
) -> tuple[ScoredTrajectoryState, float]:
    delta = _estimate_delta(previous, estimate)
    credit = _transition_credit(delta, estimate.milestone_eligible)
    next_cumulative = _round_value(cumulative + credit)
    state = ScoredTrajectoryState(
        observation_id=estimate.observation_id,
        trajectory_id=estimate.trajectory_id,
        task_group=estimate.task_group,
        state_index=estimate.state_index,
        boundary=estimate.boundary,
        typed_state_digest=estimate.typed_compatibility_digest,
        milestone_eligible=estimate.milestone_eligible,
        estimator=estimator,
        cluster_id=estimate.cluster_id,
        cluster_feature_summary=cluster.feature_summary,
        value_source=estimate.value_source,
        supporting_trajectory_ids=estimate.supporting_trajectory_ids,
        estimated_value=estimate.estimated_value,
        previous_observation_id=_previous_observation_id(previous),
        value_delta=delta,
        transition_credit=credit,
        cumulative_milestone_credit=next_cumulative,
        credit_reason=_credit_reason(previous, estimate),
        eventual_terminal_result=terminal,
        eventual_terminal_reward=reward,
    )
    return state, next_cumulative


def replay_offline_values(
    comparison: OfflineValueComparison,
    *,
    trajectory_id: str,
    estimator: EstimatorKind = EstimatorKind.HYBRID_TYPED_TEXT,
) -> TrajectoryScoreReplay:
    """Replay frozen estimates as state, cluster, value, delta, and credit.

    This function is read-only.  It consumes estimates already computed by
    PR2 and never invokes a model, mathematical capability, or verifier.
    """

    evaluation = _evaluation(comparison, estimator)
    raw_estimates, raw_clusters = _validate_estimates(evaluation, trajectory_id)
    estimates = tuple(raw_estimates)
    clusters = dict(raw_clusters)
    reward, task_group, terminal = _trajectory_bindings(estimates)
    _comparison_trajectory_rewards(comparison)
    states: list[ScoredTrajectoryState] = []
    cumulative = 0.0
    previous = None
    for estimate in estimates:
        cluster = _validated_cluster(estimate, clusters.get(estimate.cluster_id))
        state, cumulative = _scored_state(
            estimate,
            estimator=estimator,
            cluster=cluster,
            previous=previous,
            cumulative=cumulative,
            terminal=terminal,
            reward=reward,
        )
        states.append(state)
        previous = estimate
    return TrajectoryScoreReplay(
        comparison_digest=_comparison_digest(comparison),
        source_corpus_digest=comparison.corpus_digest,
        trajectory_id=trajectory_id,
        task_group=task_group,
        estimator=estimator,
        eventual_terminal_result=terminal,
        eventual_terminal_reward=reward,
        states=tuple(states),
        total_milestone_credit=cumulative,
    )


__all__ = [
    "CreditReason",
    "ScoredTrajectoryState",
    "TerminalResult",
    "TrajectoryScoreError",
    "TrajectoryScoreReplay",
    "replay_offline_values",
]
