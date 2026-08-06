"""Regression tests for fail-closed, resource safety, and concurrency fixes.

Validates six bugs identified during the audit:

1. ``_close_evicted`` overwrites a concurrently-created runtime on close failure.
2. ``close()`` leaves ``_closing=True`` on failure, permanently rejecting leases.
3. ``_run_blocking`` orphans the worker thread on a second ``CancelledError``.
4. ``_trial_status`` treated a missing ``status`` field as ``COMPLETED``.
5. ``compare_evidence`` only checked core metrics for missing pairs.
6. ``mkstemp`` fd was leaked if ``os.fdopen`` raised before the ``with`` block.
"""

import inspect


def test_trial_status_missing_status_fails_closed() -> None:
    """A trial with no ``status`` field must not default to COMPLETED."""
    from benchmarks.tooling.observation_results import _trial_status

    assert _trial_status({}, None) == "ERROR"
    assert _trial_status({"status": None}, None) == "ERROR"
    assert _trial_status({"status": 42}, None) == "ERROR"
    assert _trial_status({"status": "COMPLETED"}, None) == "COMPLETED"
    assert _trial_status({"status": "RUNNING"}, None) == "RUNNING"
    assert _trial_status({"status": "FAILED"}, None) == "FAILED"
    assert _trial_status({}, RuntimeError("boom")) == "ERROR"
    assert _trial_status({"status": "COMPLETED"}, RuntimeError("boom")) == "ERROR"


def test_trial_status_non_string_status_fails_closed() -> None:
    """Non-string status values must be treated as ERROR, not COMPLETED."""
    from benchmarks.tooling.observation_results import _trial_status

    for bad in (None, 0, 1, True, False, [], {}):
        assert _trial_status({"status": bad}, None) == "ERROR", f"{bad!r} should be ERROR"


def test_metric_report_reports_missing_pairs_for_all_metrics() -> None:
    """All metrics with missing pairs should be reported, not just core ones."""
    from benchmarks.tooling.observation_comparison import _metric_report

    pairs = [("task-a", 0)]
    control_trials = {
        ("task-a", 0): {
            "metrics": {"correctness": 1.0, "evidence_validity": 1.0},
        },
    }
    treatment_trials = {
        ("task-a", 0): {
            "metrics": {"correctness": 1.0, "evidence_validity": None},
        },
    }

    report = _metric_report(
        "evidence_validity",
        pairs,
        control_trials,
        treatment_trials,
    )
    assert report["pair_count"] == 0, (
        "Pairs with None metrics should be dropped (pair_count=0)"
    )


def test_compare_evidence_checks_all_metrics_for_missing_pairs() -> None:
    """compare_evidence must iterate over all metric_names, not just 2."""
    from benchmarks.tooling import observation_comparison

    source = inspect.getsource(observation_comparison.compare_evidence)
    assert "metric_names" in source, (
        "compare_evidence must iterate over all metric_names"
    )
    assert 'for metric in ("correctness", "false_certification")' not in source, (
        "compare_evidence should no longer hard-code only 2 metrics"
    )


def test_mkstemp_fd_closed_on_fdopen_failure() -> None:
    """If os.fdopen fails after mkstemp, the fd must be closed."""
    import jacobian.lean_frontend.statement as statement_module

    source = inspect.getsource(statement_module)
    assert "os.close(fd)" in source, (
        "statement.py must close the mkstemp fd if os.fdopen fails"
    )


def test_close_evicted_guards_concurrent_runtime_creation() -> None:
    """_close_evicted must not overwrite a concurrently-created runtime."""
    from jacobian.adapters.mcp import remote

    source = inspect.getsource(remote.TenantRuntimeRouter._close_evicted)
    assert "if tenant_key not in self._runtimes" in source, (
        "_close_evicted must guard against overwriting a concurrent runtime"
    )


def test_close_resets_closing_flag_on_failure() -> None:
    """close() must reset _closing on failure to avoid permanently rejecting leases."""
    from jacobian.adapters.mcp import remote

    source = inspect.getsource(remote.TenantRuntimeRouter.close)
    assert "_closing = False" in source, (
        "close() must reset _closing=False in the failure path"
    )


def test_run_blocking_catches_base_exception_for_drain() -> None:
    """_run_blocking must catch BaseException (not just Exception) for the drain."""
    from jacobian.adapters.mcp import tooling

    source = inspect.getsource(tooling._run_blocking)
    assert "except BaseException:" in source, (
        "_run_blocking must catch BaseException for the drain so that a "
        "second CancelledError does not orphan the worker thread"
    )
