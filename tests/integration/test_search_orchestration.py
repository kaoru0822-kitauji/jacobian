from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from jacobian.canonical import canonicalize_json
from jacobian.contracts.claims import ClaimSpec
from jacobian.contracts.discovery import ExperimentState
from jacobian.contracts.evidence import WitnessRole
from jacobian.contracts.plugins import PluginManifest
from jacobian.contracts.search import (
    SearchArchivePage,
    SearchBudget,
    SearchCheckpoint,
    SearchExperimentSnapshot,
    SearchRunRequest,
    SearchStopReason,
)
from jacobian.kernel import JacobianKernel
from jacobian.search import SearchError
from jacobian.store import StoreError, StoreLimits

pytestmark = [
    pytest.mark.conformance,
    pytest.mark.usefixtures("initialized_kernel_store"),
]


def _install_search_plugin(
    kernel: JacobianKernel,
    *,
    proposer_entrypoint: str = (
        "tests.fixtures.plugin_functions:propose_fixture_values"
    ),
    refiner_entrypoint: str = ("tests.fixtures.plugin_functions:refine_fixture_search"),
    include_witness_oracle: bool = False,
) -> tuple[str, str]:
    claim_schema_uri = kernel.schemas.register(
        name="fixture.search-claim",
        version="1",
        schema=ClaimSpec.model_json_schema(),
    )
    candidate_schema_uri = kernel.schemas.register(
        name="fixture.search-candidate",
        version="1",
        schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
            "additionalProperties": False,
        },
    )
    semantics_uri = kernel.store.register_descriptor(
        kind="semantics",
        name="fixture.search-domain",
        version="1",
        definition={"description": "finite integer search fixture"},
    )
    entrypoints = {
        "Proposer": proposer_entrypoint,
        "Refiner": refiner_entrypoint,
        "Evaluator": "tests.fixtures.plugin_functions:evaluate_candidate",
    }
    if include_witness_oracle:
        entrypoints["WitnessOracle"] = (
            "tests.fixtures.plugin_functions:find_fixture_witness"
        )
    capabilities: dict[str, dict[str, str]] = {}
    for name, entrypoint in entrypoints.items():
        capabilities[name] = {
            "implementation_uri": kernel.plugins.register_implementation(entrypoint),
            "entrypoint": entrypoint,
            "version": "1",
        }
    manifest = kernel.artifacts.put(
        schema_uri=kernel.reference_installer.manifest_schema_uri,
        semantics_uri=kernel.reference_installer.manifest_semantics_uri,
        payload=PluginManifest(
            domain_id="fixture.search-domain",
            domain_version="1",
            semantics_uri=semantics_uri,
            claim_schema_uri=claim_schema_uri,
            candidate_schema_uri=candidate_schema_uri,
            capabilities=capabilities,
        ).model_dump(mode="json"),
    )
    kernel.plugins.install(manifest.artifact_uri)
    claim = kernel.artifacts.put(
        schema_uri=claim_schema_uri,
        semantics_uri=semantics_uri,
        payload={
            "claim_schema_version": "1",
            "domain_id": "fixture.search-domain",
            "domain_version": "1",
            "semantics_uri": semantics_uri,
            "quantifiers": [],
            "predicate": {"name": "fixture_predicate", "parameters": {}},
            "bounds": {},
            "required_capabilities": ["Proposer", "Refiner", "Evaluator"],
            "correspondence_status": "UNREVIEWED",
        },
    )
    return claim.artifact_uri, manifest.artifact_uri


def _request(
    claim_uri: str,
    plugin_id: str,
    *,
    idempotency_key: str,
    batch_size: int = 1,
    wall_seconds: int = 30,
    witness_role: WitnessRole | None = None,
    counterexample_checker_id: str | None = None,
) -> SearchRunRequest:
    return SearchRunRequest(
        idempotency_key=idempotency_key,
        claim_uri=claim_uri,
        plugin_id=plugin_id,
        initial_state={"cursor": 0},
        witness_role=witness_role,
        counterexample_checker_id=counterexample_checker_id,
        budget=SearchBudget(
            candidates_max=8,
            iterations_max=8,
            wall_seconds=wall_seconds,
            batch_size=batch_size,
            workers=1,
        ),
    )


@pytest.mark.integration
def test_search_run_checkpoints_strategy_neutral_lineage(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(kernel)

    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-lineage-001",
            batch_size=4,
        )
    )
    snapshot = kernel.search.wait(handle.experiment_uri, timeout_seconds=30)

    assert snapshot.state is ExperimentState.COMPLETED
    assert snapshot.stop_reason is SearchStopReason.STRATEGY_COMPLETE
    assert snapshot.strategy_reported_complete is True
    assert snapshot.verification.value == "UNVERIFIED"
    assert snapshot.accounting.proposed_candidates == 4
    assert snapshot.accounting.unique_candidates == 4
    assert snapshot.accounting.evaluated_candidates == 4
    assert snapshot.accounting.iterations == 1
    assert snapshot.accounting.checkpoints == 1
    assert snapshot.accounting.nominations == 1
    assert snapshot.effective_budget.workers == 1
    assert len(snapshot.archive_page_uris) == 1
    assert snapshot.checkpoint_uri is not None
    assert snapshot.archive_uri is not None
    assert set(kernel.store.get(snapshot.archive_uri).manifest.parents) == {
        claim_uri,
        plugin_id,
        snapshot.checkpoint_uri,
    }
    events = kernel.search.events(handle.experiment_uri)
    assert events[0].event_type == "REQUEST_ACCEPTED"
    assert events[-1].event_type == "COMPLETED"
    proposer_event = next(
        event for event in events if event.event_type == "PROPOSER_COMPLETED"
    )
    assert proposer_event.payload["request_digest"].startswith("sha256:")
    assert proposer_event.payload["output_digest"].startswith("sha256:")


@pytest.mark.integration
def test_resume_rejects_archive_page_rebound_to_another_plugin(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(kernel)
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-rebound-page-001",
            batch_size=4,
        )
    )
    completed = kernel.search.wait(handle.experiment_uri, timeout_seconds=30)
    original_page = kernel.store.get(completed.archive_page_uris[0])
    rebound_page = SearchArchivePage.model_validate(original_page.payload).model_copy(
        update={"plugin_id": claim_uri}
    )
    stored_rebound_page = kernel.search._put_internal_artifact(
        schema_uri=kernel.search.archive_page_schema_uri,
        payload=rebound_page.model_dump(mode="json"),
        parents=original_page.manifest.parents,
        summary="search archive page",
    )
    paused = completed.model_copy(
        update={
            "state": ExperimentState.PAUSED,
            "stop_reason": None,
            "strategy_reported_complete": False,
            "archive_uri": None,
            "archive_page_uris": (stored_rebound_page.artifact_uri,),
        }
    )
    with sqlite3.connect(kernel.store.db_path) as connection:
        connection.execute(
            """
            UPDATE search_experiments
            SET state = ?, snapshot_json = ?
            WHERE experiment_uri = ?
            """,
            (
                paused.state.value,
                canonicalize_json(paused.model_dump(mode="json")),
                paused.experiment_uri,
            ),
        )

    resumed = kernel.search.resume(handle.experiment_uri)
    assert resumed.accepted is True
    recovered = kernel.search.wait(handle.experiment_uri, timeout_seconds=30)

    assert recovered.state is ExperimentState.ERROR
    assert "archive page identity does not match the search" in recovered.detail


@pytest.mark.integration
def test_checkpoint_persistence_is_included_in_wall_accounting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(kernel)
    original_put = kernel.search._put_internal_artifact
    current_time = 0.0

    def clock() -> float:
        return current_time

    def delayed_put(**kwargs: object) -> object:
        nonlocal current_time
        if kwargs.get("summary") == "immutable search checkpoint":
            current_time += 1
        return original_put(**kwargs)

    monkeypatch.setattr(kernel.search, "_clock", clock)
    monkeypatch.setattr(kernel.search, "_put_internal_artifact", delayed_put)
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-accounting-persistence-001",
            batch_size=4,
        )
    )
    snapshot = kernel.search.wait(handle.experiment_uri, timeout_seconds=30)

    assert snapshot.state is ExperimentState.COMPLETED
    assert snapshot.accounting.wall_time_ms == 1_000


@pytest.mark.integration
def test_checkpoint_persistence_cannot_complete_past_wall_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(kernel)
    original_put = kernel.search._put_internal_artifact
    current_time = 0.0

    def clock() -> float:
        return current_time

    def delayed_put(**kwargs: object) -> object:
        nonlocal current_time
        if kwargs.get("summary") == "immutable search checkpoint":
            current_time += 5.1
        return original_put(**kwargs)

    monkeypatch.setattr(kernel.search, "_clock", clock)
    monkeypatch.setattr(kernel.search, "_put_internal_artifact", delayed_put)
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-accounting-timeout-001",
            batch_size=4,
            wall_seconds=5,
        )
    )
    snapshot = kernel.search.wait(handle.experiment_uri, timeout_seconds=30)

    assert snapshot.state is ExperimentState.TIMEOUT
    assert snapshot.stop_reason is SearchStopReason.WALL_TIME_LIMIT
    assert snapshot.strategy_reported_complete is False
    assert snapshot.accounting.wall_time_ms >= 5_000


@pytest.mark.integration
def test_concurrent_retries_create_one_search_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(kernel)
    request = _request(
        claim_uri,
        plugin_id,
        idempotency_key="search-concurrent-001",
        batch_size=4,
    )

    with ThreadPoolExecutor(max_workers=8) as pool:
        handles = tuple(pool.map(lambda _index: kernel.search.start(request), range(8)))

    experiment_uris = {handle.experiment_uri for handle in handles}
    assert len(experiment_uris) == 1
    experiment_uri = experiment_uris.pop()
    snapshot = kernel.search.wait(experiment_uri, timeout_seconds=30)
    assert snapshot.accounting.proposed_candidates == 4

    def fail_if_resolved(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("durable retries must not re-resolve plugin code")

    monkeypatch.setattr(kernel.plugins, "resolve", fail_if_resolved)
    retried = kernel.search.start(request)
    assert retried.experiment_uri == experiment_uri

    event_types = [event.event_type for event in kernel.search.events(experiment_uri)]
    assert event_types.count("REQUEST_ACCEPTED") == 1
    assert event_types.count("REQUEST_REUSED") == 8


@pytest.mark.integration
def test_search_lifecycle_events_are_append_only(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(kernel)
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-events-001",
            batch_size=4,
        )
    )
    kernel.search.wait(handle.experiment_uri, timeout_seconds=30)

    with (
        sqlite3.connect(kernel.store.db_path) as connection,
        pytest.raises(
            sqlite3.IntegrityError,
            match="append-only",
        ),
    ):
        connection.execute(
            """
            UPDATE search_events
            SET event_digest = ?
            WHERE experiment_uri = ? AND sequence = 0
            """,
            (
                "sha256:" + "0" * 64,
                handle.experiment_uri,
            ),
        )


@pytest.mark.integration
def test_idempotency_key_cannot_be_rebound(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(kernel)
    first = _request(
        claim_uri,
        plugin_id,
        idempotency_key="search-rebind-001",
    )
    kernel.search.start(first)

    with pytest.raises(
        SearchError,
        match=(
            r"This idempotency key is already bound to a different request\. "
            r"Reuse the original request or choose a new idempotency key\."
        ),
    ):
        kernel.search.start(
            first.model_copy(
                update={
                    "initial_state": {"cursor": 2},
                }
            )
        )


@pytest.mark.integration
def test_search_pauses_and_resumes_without_duplicate_lineage(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(
        kernel,
        proposer_entrypoint=(
            "tests.fixtures.plugin_functions:propose_fixture_values_slowly"
        ),
    )
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-pause-001",
        )
    )

    pause = kernel.search.pause(handle.experiment_uri)
    assert pause.accepted is True
    paused = kernel.search.wait(handle.experiment_uri, timeout_seconds=30)
    assert paused.state is ExperimentState.PAUSED
    before_pages = paused.archive_page_uris

    resumed = kernel.search.resume(handle.experiment_uri)
    assert resumed.accepted is True
    completed = kernel.search.wait(handle.experiment_uri, timeout_seconds=30)

    assert completed.state is ExperimentState.COMPLETED
    assert completed.accounting.unique_candidates == 4
    assert len(completed.archive_page_uris) == 4
    assert completed.archive_page_uris[: len(before_pages)] == before_pages
    assert len(set(completed.archive_page_uris)) == 4


@pytest.mark.integration
def test_interrupted_search_recovers_from_checkpoint_without_chat_state(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(
        kernel,
        proposer_entrypoint=(
            "tests.fixtures.plugin_functions:propose_fixture_values_slowly"
        ),
    )
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-recovery-001",
        )
    )
    kernel.search.pause(handle.experiment_uri)
    paused = kernel.search.wait(handle.experiment_uri, timeout_seconds=30)
    thread = kernel.search._threads.get(handle.experiment_uri)
    if thread is not None:
        thread.join(timeout=5)

    simulated_running = SearchExperimentSnapshot.model_validate(
        {
            **paused.model_dump(mode="json"),
            "state": "RUNNING",
            "detail": "simulated process loss",
        }
    )
    with sqlite3.connect(kernel.store.db_path) as connection:
        connection.execute(
            """
            UPDATE search_experiments
            SET state = ?, snapshot_json = ?
            WHERE experiment_uri = ?
            """,
            (
                ExperimentState.RUNNING.value,
                canonicalize_json(simulated_running.model_dump(mode="json")),
                handle.experiment_uri,
            ),
        )

    recovered_kernel = JacobianKernel(tmp_path)
    recovered = recovered_kernel.search.inspect(handle.experiment_uri)
    assert recovered.state is ExperimentState.PAUSED
    assert recovered.checkpoint_uri == paused.checkpoint_uri
    recovered_kernel.search.resume(handle.experiment_uri)
    completed = recovered_kernel.search.wait(
        handle.experiment_uri,
        timeout_seconds=30,
    )

    assert completed.state is ExperimentState.COMPLETED
    assert completed.accounting.unique_candidates == 4
    assert len(set(completed.archive_page_uris)) == 4


@pytest.mark.integration
def test_interrupted_cancellation_remains_cancelled_after_recovery(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(
        kernel,
        proposer_entrypoint=(
            "tests.fixtures.plugin_functions:propose_fixture_values_slowly"
        ),
    )
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-recovery-cancel-001",
        )
    )
    kernel.search.pause(handle.experiment_uri)
    paused = kernel.search.wait(handle.experiment_uri, timeout_seconds=30)
    thread = kernel.search._threads.get(handle.experiment_uri)
    if thread is not None:
        thread.join(timeout=5)

    interrupted = SearchExperimentSnapshot.model_validate(
        {
            **paused.model_dump(mode="json"),
            "state": "CANCEL_REQUESTED",
            "detail": "simulated process loss after cancellation",
        }
    )
    with sqlite3.connect(kernel.store.db_path) as connection:
        connection.execute(
            """
            UPDATE search_experiments
            SET state = ?, snapshot_json = ?
            WHERE experiment_uri = ?
            """,
            (
                ExperimentState.CANCEL_REQUESTED.value,
                canonicalize_json(interrupted.model_dump(mode="json")),
                handle.experiment_uri,
            ),
        )

    recovered_kernel = JacobianKernel(tmp_path)
    recovered = recovered_kernel.search.inspect(handle.experiment_uri)

    assert recovered.state is ExperimentState.CANCELLED
    assert recovered.stop_reason is SearchStopReason.CANCELLED
    assert recovered.checkpoint_uri == paused.checkpoint_uri
    assert recovered.archive_uri is not None
    event_types = [
        event.event_type
        for event in recovered_kernel.search.events(handle.experiment_uri)
    ]
    assert event_types[-2:] == [
        "RECOVERED_CANCELLED",
        "RECOVERY_ARCHIVE_COMMITTED",
    ]


@pytest.mark.integration
def test_corrupt_snapshot_is_quarantined_without_blocking_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(kernel)
    monkeypatch.setattr(kernel.search, "_launch", lambda _experiment_uri: None)
    valid = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-recovery-valid-001",
        )
    )
    valid_snapshot = kernel.search.inspect(valid.experiment_uri)
    corrupt_uri = "experiment://ffffffffffffffffffffffffffffffff"
    mismatched_uri = "experiment://eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    invalid_state_uri = "experiment://dddddddddddddddddddddddddddddddd"
    with sqlite3.connect(kernel.store.db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            INSERT INTO search_experiments (
                experiment_uri, state, snapshot_json
            ) VALUES (?, 'RUNNING', ?)
            """,
            (corrupt_uri, b"{"),
        )
        connection.execute(
            """
            INSERT INTO search_experiments (
                experiment_uri, state, snapshot_json
            ) VALUES (?, 'PENDING', ?)
            """,
            (
                mismatched_uri,
                canonicalize_json(valid_snapshot.model_dump(mode="json")),
            ),
        )
        invalid_state_snapshot = valid_snapshot.model_copy(
            update={"experiment_uri": invalid_state_uri}
        )
        connection.execute(
            """
            INSERT INTO search_experiments (
                experiment_uri, state, snapshot_json
            ) VALUES (?, 'BROKEN', ?)
            """,
            (
                invalid_state_uri,
                canonicalize_json(invalid_state_snapshot.model_dump(mode="json")),
            ),
        )

    recovered = JacobianKernel(tmp_path)

    assert (
        recovered.search.inspect(valid.experiment_uri).state is ExperimentState.PAUSED
    )
    with sqlite3.connect(recovered.store.db_path) as connection:
        states = connection.execute(
            """
            SELECT experiment_uri, state
            FROM search_experiments
            WHERE experiment_uri IN (?, ?, ?)
            ORDER BY experiment_uri
            """,
            (corrupt_uri, mismatched_uri, invalid_state_uri),
        ).fetchall()
        failures = connection.execute(
            """
            SELECT experiment_uri, snapshot_digest, detail
            FROM search_recovery_failures
            WHERE experiment_uri IN (?, ?, ?)
            ORDER BY experiment_uri
            """,
            (corrupt_uri, mismatched_uri, invalid_state_uri),
        ).fetchall()
    assert states == [
        (invalid_state_uri, "ERROR"),
        (mismatched_uri, "ERROR"),
        (corrupt_uri, "ERROR"),
    ]
    assert len(failures) == 3
    assert all(str(failure[1]).startswith("sha256:") for failure in failures)
    assert all("invalid" in str(failure[2]) for failure in failures)
    assert recovered.search.events(corrupt_uri)[-1].event_type == "RECOVERY_REJECTED"
    assert recovered.search.events(mismatched_uri)[-1].event_type == "RECOVERY_REJECTED"
    assert (
        recovered.search.events(invalid_state_uri)[-1].event_type == "RECOVERY_REJECTED"
    )


@pytest.mark.integration
@pytest.mark.subprocess
def test_proposer_timeout_fails_closed(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(
        kernel,
        proposer_entrypoint=("tests.fixtures.plugin_functions:propose_search_forever"),
    )
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-timeout-001",
            wall_seconds=1,
        )
    )

    with pytest.raises(
        TimeoutError,
        match="Inspect the experiment or wait again with a larger timeout",
    ):
        kernel.search.wait(handle.experiment_uri, timeout_seconds=0)

    snapshot = kernel.search.wait(handle.experiment_uri, timeout_seconds=10)

    assert snapshot.state is ExperimentState.TIMEOUT
    assert snapshot.stop_reason is SearchStopReason.WALL_TIME_LIMIT
    assert snapshot.verification.value == "UNVERIFIED"
    assert snapshot.accounting.proposed_candidates == 0
    assert snapshot.accounting.wall_time_ms > 0
    assert snapshot.archive_page_uris == ()


@pytest.mark.integration
def test_malformed_proposal_fails_without_evidence_promotion(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(
        kernel,
        proposer_entrypoint=(
            "tests.fixtures.plugin_functions:propose_malformed_search"
        ),
    )
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-malformed-001",
        )
    )

    snapshot = kernel.search.wait(handle.experiment_uri, timeout_seconds=15)

    assert snapshot.state is ExperimentState.ERROR
    assert snapshot.verification.value == "UNVERIFIED"
    assert "artifact or plugin response was invalid" in snapshot.detail
    assert "reference contract" in snapshot.detail
    assert "input_value" not in snapshot.detail
    assert snapshot.archive_page_uris == ()


@pytest.mark.integration
@pytest.mark.subprocess
def test_partial_iteration_accounting_survives_malformed_candidate(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(
        kernel,
        proposer_entrypoint=(
            "tests.fixtures.plugin_functions:propose_partially_invalid_search"
        ),
    )
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-partial-accounting-001",
            batch_size=2,
        )
    )

    snapshot = kernel.search.wait(handle.experiment_uri, timeout_seconds=15)

    assert snapshot.state is ExperimentState.ERROR
    assert snapshot.accounting.proposed_candidates == 1
    assert snapshot.accounting.unique_candidates == 1
    assert snapshot.accounting.evaluated_candidates == 0


@pytest.mark.integration
@pytest.mark.parametrize(
    ("entrypoint", "detail", "case_id"),
    [
        (
            "tests.fixtures.plugin_functions:propose_declared_failure",
            (
                "The plugin stopped before returning a result. Retry once; "
                "if it happens again, inspect the local plugin log."
            ),
            "declared",
        ),
        (
            "tests.fixtures.plugin_functions:propose_large_search_output",
            "The plugin returned too much data. Retry with a smaller request.",
            "output",
        ),
    ],
)
def test_search_plugin_failures_remain_operational(
    tmp_path: Path,
    entrypoint: str,
    detail: str,
    case_id: str,
) -> None:
    kernel = JacobianKernel(tmp_path)
    if entrypoint.endswith("propose_large_search_output"):
        kernel.plugin_executor.max_output_bytes = 1024
    claim_uri, plugin_id = _install_search_plugin(
        kernel,
        proposer_entrypoint=entrypoint,
    )
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key=f"search-failure-{case_id}",
        )
    )

    snapshot = kernel.search.wait(handle.experiment_uri, timeout_seconds=15)

    assert snapshot.state is ExperimentState.ERROR
    assert snapshot.verification.value == "UNVERIFIED"
    assert detail in snapshot.detail
    assert snapshot.archive_page_uris == ()


@pytest.mark.integration
def test_terminal_archive_failure_marks_search_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(kernel)

    def fail_archive(*_args: object, **_kwargs: object) -> object:
        raise StoreError("fixture archive failure")

    monkeypatch.setattr(kernel.search, "_store_archive", fail_archive)
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-terminal-archive-failure-001",
            batch_size=4,
        )
    )

    snapshot = kernel.search.wait(handle.experiment_uri, timeout_seconds=15)

    assert snapshot.state is ExperimentState.ERROR
    assert snapshot.stop_reason is SearchStopReason.ERROR
    assert snapshot.archive_uri is None
    assert "could not save the final experiment archive" in snapshot.detail
    assert "experiment remains unverified" in snapshot.detail
    assert "StoreError" not in snapshot.detail
    assert "fixture archive failure" not in snapshot.detail
    assert "fixture archive failure" in caplog.text


@pytest.mark.integration
def test_plugin_cannot_widen_operator_batch_policy(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    kernel.search.max_batch_size = 1
    claim_uri, plugin_id = _install_search_plugin(
        kernel,
        proposer_entrypoint=(
            "tests.fixtures.plugin_functions:propose_beyond_authority"
        ),
    )
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-policy-001",
            batch_size=8,
        )
    )

    snapshot = kernel.search.wait(handle.experiment_uri, timeout_seconds=15)

    assert snapshot.effective_budget.batch_size == 1
    assert snapshot.state is ExperimentState.ERROR
    assert "more candidates than authorized" in snapshot.detail
    assert snapshot.accounting.proposed_candidates == 0


@pytest.mark.integration
def test_search_batch_respects_evaluator_limit(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    kernel.evaluation.max_batch_size = 2
    kernel.search.max_batch_size = 3
    claim_uri, plugin_id = _install_search_plugin(kernel)
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-evaluator-batch-policy-001",
            batch_size=3,
        )
    )

    snapshot = kernel.search.wait(handle.experiment_uri, timeout_seconds=30)

    assert snapshot.state is ExperimentState.COMPLETED
    assert snapshot.effective_budget.batch_size == 2
    assert snapshot.accounting.unique_candidates == 4
    assert snapshot.accounting.iterations == 2


@pytest.mark.integration
def test_search_batch_respects_archive_parent_limit(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(kernel)
    kernel.store.limits = StoreLimits(max_parents=6)
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-archive-parent-policy-001",
            batch_size=4,
        )
    )

    snapshot = kernel.search.wait(handle.experiment_uri, timeout_seconds=30)

    assert snapshot.state is ExperimentState.COMPLETED
    assert snapshot.effective_budget.batch_size == 3
    assert snapshot.accounting.unique_candidates == 4
    assert snapshot.accounting.iterations == 2
    for page_uri in snapshot.archive_page_uris:
        assert len(kernel.store.get(page_uri).manifest.parents) <= 6


@pytest.mark.integration
def test_refiner_cannot_claim_verification(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(
        kernel,
        refiner_entrypoint=(
            "tests.fixtures.plugin_functions:refine_with_verification_claim"
        ),
    )
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-promotion-001",
            batch_size=4,
        )
    )

    snapshot = kernel.search.wait(handle.experiment_uri, timeout_seconds=15)

    assert snapshot.state is ExperimentState.ERROR
    assert snapshot.verification.value == "UNVERIFIED"
    assert "artifact or plugin response was invalid" in snapshot.detail
    assert "verification" not in snapshot.detail
    assert snapshot.archive_page_uris == ()


@pytest.mark.integration
@pytest.mark.subprocess
@pytest.mark.conformance
def test_verified_counterexample_feedback_reaches_refiner(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(
        kernel,
        refiner_entrypoint=(
            "tests.fixtures.plugin_functions:refine_from_verified_counterexample"
        ),
        include_witness_oracle=True,
    )
    manifest = kernel.plugins.get(plugin_id)
    checker = kernel.checkers.authorize(
        name="fixture-value-v1",
        entrypoint="tests.fixtures.checker_functions:check_fixture_value",
        evidence_kind="WITNESS",
        format_id="fixture.value",
        format_version="1",
        claim_schema_uris=(manifest.claim_schema_uri,),
        semantics_uris=(manifest.semantics_uri,),
        candidate_schema_uris=(manifest.candidate_schema_uri,),
        reason="search orchestration conformance fixture",
    )
    kernel.store.limits = StoreLimits(max_parents=9)
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-feedback-001",
            batch_size=4,
            witness_role=WitnessRole.DEFEATS_CANDIDATE,
            counterexample_checker_id=checker.checker_id,
        )
    )

    snapshot = kernel.search.wait(handle.experiment_uri, timeout_seconds=30)

    assert snapshot.state is ExperimentState.COMPLETED
    assert snapshot.effective_budget.batch_size == 2
    assert snapshot.accounting.iterations == 2
    assert snapshot.accounting.attacked_candidates == 4
    assert snapshot.accounting.verified_counterexamples == 4
    assert snapshot.checkpoint_uri is not None
    checkpoint = SearchCheckpoint.model_validate(
        kernel.store.get(snapshot.checkpoint_uri).payload
    )
    assert checkpoint.state["saw_verified_counterexample"] is True
    assert all(record.counterexample_verified for record in checkpoint.latest_records)
    assert all(
        record.verification_record_uri is not None
        for record in checkpoint.latest_records
    )


@pytest.mark.integration
@pytest.mark.subprocess
@pytest.mark.conformance
def test_supporting_checker_decision_is_not_counted_as_counterexample(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id = _install_search_plugin(
        kernel,
        include_witness_oracle=True,
    )
    manifest = kernel.plugins.get(plugin_id)
    checker = kernel.checkers.authorize(
        name="fixture-value-true-v1",
        entrypoint=("tests.fixtures.checker_functions:check_fixture_value_as_true"),
        evidence_kind="WITNESS",
        format_id="fixture.value",
        format_version="1",
        claim_schema_uris=(manifest.claim_schema_uri,),
        semantics_uris=(manifest.semantics_uri,),
        candidate_schema_uris=(manifest.candidate_schema_uri,),
        reason="counterexample conclusion boundary fixture",
    )
    handle = kernel.search.start(
        _request(
            claim_uri,
            plugin_id,
            idempotency_key="search-supporting-decision-001",
            batch_size=4,
            witness_role=WitnessRole.DEFEATS_CANDIDATE,
            counterexample_checker_id=checker.checker_id,
        )
    )

    snapshot = kernel.search.wait(handle.experiment_uri, timeout_seconds=30)

    assert snapshot.state is ExperimentState.COMPLETED
    assert snapshot.accounting.verified_counterexamples == 0
    assert snapshot.checkpoint_uri is not None
    checkpoint = SearchCheckpoint.model_validate(
        kernel.store.get(snapshot.checkpoint_uri).payload
    )
    assert all(
        not record.counterexample_verified for record in checkpoint.latest_records
    )
