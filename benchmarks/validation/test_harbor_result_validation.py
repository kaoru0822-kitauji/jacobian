"""Fail-closed tests for Harbor Oracle result validation."""

from __future__ import annotations

from benchmarks.tooling.validate_harbor_results import _validate_payload


def _payload(*, reward: object = 1.0, **trial_overrides: object) -> dict:
    trial = {
        "task_name": "jacobian/example-task",
        "task_checksum": "sha256:digest",
        "verifier_result": {"rewards": {"correctness": reward}},
        "exception_info": None,
    }
    trial.update(trial_overrides)
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
        "trial_results": [trial],
    }


def test_complete_result_binds_task_and_digest() -> None:
    assert (
        _validate_payload(
            _payload(),
            expected_tasks={"example-task"},
            expected_digests={"example-task": "sha256:digest"},
        )
        == []
    )


def test_missing_reward_is_not_a_certifying_result() -> None:
    failures = _validate_payload(
        _payload(verifier_result={"rewards": {}}),
        expected_tasks={"example-task"},
        expected_digests={"example-task": "sha256:digest"},
    )

    assert any("incomplete verifier reward" in failure for failure in failures)


def test_exception_and_digest_mismatch_fail_closed() -> None:
    failures = _validate_payload(
        _payload(
            task_checksum="sha256:wrong",
            exception_info={"exception_type": "TimeoutError"},
        ),
        expected_tasks={"example-task"},
        expected_digests={"example-task": "sha256:digest"},
    )

    assert any("digest mismatch" in failure for failure in failures)
    assert any("exception result" in failure for failure in failures)
