"""Fail-closed tests for Harbor Oracle result validation."""

from __future__ import annotations

import pytest
from benchmarks.tooling.validate_harbor_results import _validate_payload


def _trial(*, reward: object = 1.0, **trial_overrides: object) -> dict:
    trial = {
        "task_name": "jacobian/example-task",
        "task_checksum": "sha256:digest",
        "verifier_result": {
            "rewards": {
                "correctness": reward,
                "evidence_validity": 1.0,
                "scope_accuracy": 1.0,
                "assurance_calibration": 1.0,
                "reward": 0.9999999999999999,
                "false_certification": False,
            }
        },
        "exception_info": None,
    }
    trial.update(trial_overrides)
    return trial


def _payload() -> dict:
    return {
        "id": "job",
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:01:00Z",
        "n_total_trials": 1,
        "stats": {
            "n_completed_trials": 1,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 0,
            "n_cancelled_trials": 0,
        },
    }


def test_complete_result_binds_task_and_digest() -> None:
    assert (
        _validate_payload(
            _payload(),
            trial_results=[_trial()],
            expected_tasks={"example-task"},
            expected_digests={"example-task": "sha256:digest"},
        )
        == []
    )


def test_missing_reward_is_not_a_certifying_result() -> None:
    failures = _validate_payload(
        _payload(),
        trial_results=[_trial(verifier_result={"rewards": {}})],
        expected_tasks={"example-task"},
        expected_digests={"example-task": "sha256:digest"},
    )

    assert any("incomplete verifier reward" in failure for failure in failures)


def test_exception_and_digest_mismatch_fail_closed() -> None:
    failures = _validate_payload(
        _payload(),
        trial_results=[
            _trial(
                task_checksum="sha256:wrong",
                exception_info={"exception_type": "TimeoutError"},
            )
        ],
        expected_tasks={"example-task"},
        expected_digests={"example-task": "sha256:digest"},
    )

    assert any("digest mismatch" in failure for failure in failures)
    assert any("exception result" in failure for failure in failures)


def test_non_certifying_reward_fails_closed() -> None:
    failures = _validate_payload(
        _payload(),
        trial_results=[_trial(reward=0.5)],
        expected_tasks={"example-task"},
        expected_digests={"example-task": "sha256:digest"},
    )

    assert any("correctness must be full reward" in failure for failure in failures)


@pytest.mark.parametrize("signal", [True, 1.0])
def test_false_certification_signal_fails_closed(signal: bool | float) -> None:
    trial = _trial()
    trial["verifier_result"]["rewards"]["false_certification"] = signal

    failures = _validate_payload(
        _payload(),
        trial_results=[trial],
        expected_tasks={"example-task"},
        expected_digests={"example-task": "sha256:digest"},
    )

    assert any("false_certification must be zero" in failure for failure in failures)


def test_duplicate_task_trials_fail_closed() -> None:
    payload = _payload()
    payload["n_total_trials"] = 2
    payload["stats"]["n_completed_trials"] = 2
    failures = _validate_payload(
        payload,
        trial_results=[_trial(), _trial()],
        expected_tasks={"example-task"},
        expected_digests={"example-task": "sha256:digest"},
    )

    assert any("exactly one trial" in failure for failure in failures)
