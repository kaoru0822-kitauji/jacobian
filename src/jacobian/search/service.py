"""Durable search experiment service."""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.claims import ClaimValidationService
from jacobian.contracts.artifacts import ArtifactPutResult
from jacobian.contracts.discovery import ExperimentHandle, ExperimentState
from jacobian.contracts.evaluation import EvaluationBatchResult
from jacobian.contracts.plugins import CapabilityName
from jacobian.contracts.results import (
    ExecutionStatus,
    InputStatus,
    InputValidation,
    Verification,
)
from jacobian.contracts.search import (
    ExperimentControlResult,
    SearchAccounting,
    SearchArchiveManifest,
    SearchArchivePage,
    SearchBudget,
    SearchCheckpoint,
    SearchExperimentSnapshot,
    SearchLifecycleEvent,
    SearchRunRequest,
    SearchStopReason,
)
from jacobian.evaluation import (
    EvaluationService,
)
from jacobian.experiment_identity import new_experiment_uri
from jacobian.persistence.recovery import (
    put_internal_artifact,
    quarantine_recovery_snapshot,
)
from jacobian.plugin_execution import PluginExecutor
from jacobian.plugins.registry import (
    PluginRegistry,
    PluginRegistryError,
    ResolvedCapability,
)
from jacobian.schema_registry import SchemaRegistry, SchemaRegistryError, model_schema
from jacobian.search._helpers import (
    _digest,
    _environment_digest,
    _event_digest,
    _now,
    _record_parents,
    _updated_accounting,
    _updated_snapshot,
)
from jacobian.search.errors import SearchError
from jacobian.store import ArtifactStore, StoreError
from jacobian.verification import VerificationService
from jacobian.witnesses import WitnessSearchService

_LOGGER = logging.getLogger(__name__)

_TERMINAL_STATES = {
    ExperimentState.COMPLETED,
    ExperimentState.CANCELLED,
    ExperimentState.TIMEOUT,
    ExperimentState.ERROR,
}
_SETTLED_STATES = _TERMINAL_STATES | {ExperimentState.PAUSED}


class SearchService:
    """Coordinate untrusted strategies over durable verification boundaries.

    SQLite owns idempotent request acceptance, current lifecycle state, and
    append-only events. Immutable artifacts own checkpoints and archive
    lineage. The service may replay work after the last committed checkpoint,
    but it never derives a mathematical conclusion from strategy completion,
    timeout, cancellation, or recovery state.

    The reference scheduler assumes one active coordinator per state directory
    and accepts exactly one strategy worker.
    """

    def __init__(
        self,
        store: ArtifactStore,
        schemas: SchemaRegistry,
        plugins: PluginRegistry,
        claims: ClaimValidationService,
        executor: PluginExecutor,
        evaluation: EvaluationService,
        witnesses: WitnessSearchService,
        verification: VerificationService,
        *,
        max_candidates: int = 10_000_000,
        max_iterations: int = 10_000_000,
        max_wall_seconds: int = 86_400,
        max_batch_size: int = 256,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.store = store
        self.schemas = schemas
        self.plugins = plugins
        self.claims = claims
        self.executor = executor
        self.evaluation = evaluation
        self.witnesses = witnesses
        self.verification = verification
        self.max_candidates = max_candidates
        self.max_iterations = max_iterations
        self.max_wall_seconds = max_wall_seconds
        self.max_batch_size = max_batch_size
        self._clock = clock
        self._threads: dict[str, threading.Thread] = {}
        self._thread_lock = threading.Lock()
        self._starts_in_flight = 0
        self._closing = False
        self._closed = False
        self.semantics_uri = store.register_descriptor(
            kind="semantics",
            name="jacobian.search-experiment",
            version="1",
            definition={
                "description": (
                    "untrusted strategy state, durable progress, and archive lineage"
                )
            },
        )
        self.checkpoint_schema_uri = schemas.register(
            name="jacobian.search-checkpoint",
            version="1",
            schema=model_schema(SearchCheckpoint),
        )
        self.archive_page_schema_uri = schemas.register(
            name="jacobian.search-archive-page",
            version="1",
            schema=model_schema(SearchArchivePage),
        )
        self.archive_manifest_schema_uri = schemas.register(
            name="jacobian.search-archive",
            version="1",
            schema=model_schema(SearchArchiveManifest),
        )
        self.evaluation_schema_uri = schemas.register(
            name="jacobian.evaluation-batch-result",
            version="1",
            schema=model_schema(EvaluationBatchResult),
        )
        self._recover_interrupted_searches()

    def close(self, *, timeout_seconds: float = 30) -> None:
        """Quiesce runtime-owned workers before their shared store is closed."""

        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative")
        deadline = time.monotonic() + timeout_seconds
        with self._thread_lock:
            if self._closed:
                return
            self._closing = True
        while True:
            with self._thread_lock:
                active = tuple(
                    thread for thread in self._threads.values() if thread.is_alive()
                )
                if not active and self._starts_in_flight == 0:
                    self._closed = True
                    self._closing = False
                    return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SearchError(
                    "search workers did not quiesce before runtime shutdown"
                )
            if not active:
                time.sleep(min(remaining, 0.01))
                continue
            for thread in active:
                thread.join(timeout=min(remaining, 0.05))

    def _require_open(self) -> None:
        with self._thread_lock:
            if self._closing or self._closed:
                raise SearchError("search service is closing")

    def _recover_interrupted_searches(self) -> None:
        """Isolate interrupted search state one row at a time.

        Active runs recover as paused, pending cancellation recovers as
        cancelled, and malformed or index-inconsistent snapshots are
        quarantined as errors. A corrupt row must not prevent unrelated
        experiments from recovering.
        """

        archive_recoveries: list[SearchExperimentSnapshot] = []
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT experiment_uri, state, snapshot_json
                FROM search_experiments
                WHERE state IN (
                    'PENDING', 'RUNNING', 'PAUSE_REQUESTED',
                    'CANCEL_REQUESTED', 'CANCELLED'
                )
                OR state NOT IN (
                    'PENDING', 'RUNNING', 'PAUSE_REQUESTED', 'PAUSED',
                    'COMPLETED', 'CANCEL_REQUESTED', 'CANCELLED',
                    'TIMEOUT', 'ERROR'
                )
                """
            ).fetchall()
            for row in rows:
                try:
                    snapshot = SearchExperimentSnapshot.model_validate(
                        loads_strict_json(row["snapshot_json"])
                    )
                except (TypeError, ValidationError, ValueError) as exc:
                    self._quarantine_recovery_snapshot(connection, row, exc)
                    continue
                if snapshot.experiment_uri != str(
                    row["experiment_uri"]
                ) or snapshot.state.value != str(row["state"]):
                    self._quarantine_recovery_snapshot(
                        connection,
                        row,
                        ValueError(
                            "stored search snapshot identity or state differs "
                            "from its database index"
                        ),
                    )
                    continue
                if snapshot.state is ExperimentState.CANCELLED:
                    if snapshot.archive_uri is None:
                        archive_recoveries.append(snapshot)
                    continue
                cancelled = snapshot.state is ExperimentState.CANCEL_REQUESTED
                recovered = _updated_snapshot(
                    snapshot,
                    state=(
                        ExperimentState.CANCELLED
                        if cancelled
                        else ExperimentState.PAUSED
                    ),
                    stop_reason=(SearchStopReason.CANCELLED if cancelled else None),
                    strategy_reported_complete=False,
                    updated_at=_now(),
                    detail=(
                        "cancellation completed during process recovery"
                        if cancelled
                        else (
                            "experiment process ended before completion; "
                            "resume from the last committed checkpoint"
                        )
                    ),
                )
                self._update_snapshot(connection, recovered)
                self._append_event(
                    connection,
                    recovered.experiment_uri,
                    event_type=(
                        "RECOVERED_CANCELLED" if cancelled else "RECOVERED_PAUSED"
                    ),
                    payload={
                        "checkpoint_uri": recovered.checkpoint_uri,
                        "accounting": recovered.accounting.model_dump(mode="json"),
                    },
                )
                if cancelled:
                    archive_recoveries.append(recovered)
        for snapshot in archive_recoveries:
            self._commit_recovery_archive(snapshot)

    def _quarantine_recovery_snapshot(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        error: Exception,
    ) -> None:
        """Isolate one corrupt row without blocking unrelated recovery."""

        detail = (
            "Stored search state is invalid. Restore the Jacobian state directory "
            "from a trusted backup or start a new search."
        )
        snapshot_digest = quarantine_recovery_snapshot(
            connection,
            row,
            error,
            experiments_table="search_experiments",
            recovery_table="search_recovery_failures",
            detail=detail,
            logger=_LOGGER,
            logger_message="quarantining invalid search snapshot for %s",
        )
        experiment_uri = str(row["experiment_uri"])
        try:
            self._append_event(
                connection,
                experiment_uri,
                event_type="RECOVERY_REJECTED",
                payload={
                    "snapshot_digest": snapshot_digest,
                    "detail": detail,
                },
            )
        except ValidationError:
            # The quarantine row remains authoritative when the corrupt
            # experiment identifier cannot itself satisfy the event contract.
            return

    def _commit_recovery_archive(
        self,
        snapshot: SearchExperimentSnapshot,
    ) -> None:
        archive = self._store_archive(snapshot, snapshot.accounting)
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            latest = self._read_snapshot(connection, snapshot.experiment_uri)
            if (
                latest.state is not ExperimentState.CANCELLED
                or latest.archive_uri is not None
            ):
                return
            archived = _updated_snapshot(
                latest,
                archive_uri=archive.artifact_uri,
                updated_at=_now(),
            )
            self._update_snapshot(connection, archived)
            self._append_event(
                connection,
                archived.experiment_uri,
                event_type="RECOVERY_ARCHIVE_COMMITTED",
                payload={"archive_uri": archive.artifact_uri},
            )

    def start(
        self,
        request: SearchRunRequest | dict[str, Any],
    ) -> ExperimentHandle:
        """Commit one idempotent search request and launch it locally."""

        with self._thread_lock:
            if self._closing or self._closed:
                raise SearchError("search service is closing")
            self._starts_in_flight += 1
        try:
            return self._start_reserved(request)
        finally:
            with self._thread_lock:
                self._starts_in_flight -= 1

    def _start_reserved(
        self,
        request: SearchRunRequest | dict[str, Any],
    ) -> ExperimentHandle:
        """Start after reserving the service lifecycle through worker launch."""

        selected = SearchRunRequest.model_validate(request)
        request_digest = _digest(selected.model_dump(mode="json"))
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing_handle = self._reuse_request(
                connection,
                selected,
                request_digest,
            )
        if existing_handle is not None:
            return existing_handle

        validation = self.claims.validate(
            claim_uri=selected.claim_uri,
            plugin_id=selected.plugin_id,
        )
        if not validation.valid:
            raise SearchError("; ".join(validation.input.errors))
        try:
            proposer = self.plugins.resolve(
                selected.plugin_id,
                CapabilityName.PROPOSER,
            )
            refiner = self.plugins.resolve(
                selected.plugin_id,
                CapabilityName.REFINER,
            )
            evaluator = self.plugins.resolve(
                selected.plugin_id,
                CapabilityName.EVALUATOR,
            )
            if selected.witness_role is not None:
                witness_oracle = self.plugins.resolve(
                    selected.plugin_id,
                    CapabilityName.WITNESS_ORACLE,
                )
        except PluginRegistryError as exc:
            _LOGGER.warning("search capability resolution failed", exc_info=exc)
            raise SearchError(
                "The search plugin is unavailable or incomplete. Call "
                "capability.describe, choose a reference domain with proposer, "
                "refiner, and evaluator capabilities, then retry."
            ) from exc

        effective_budget = self._effective_budget(
            selected.budget,
            include_witness_lineage=selected.witness_role is not None,
        )
        registry_snapshot_uri = proposer.registry_snapshot_uri
        resolved_snapshot_uris = {
            proposer.registry_snapshot_uri,
            refiner.registry_snapshot_uri,
            evaluator.registry_snapshot_uri,
        }
        if selected.witness_role is not None:
            resolved_snapshot_uris.add(witness_oracle.registry_snapshot_uri)
        if resolved_snapshot_uris != {registry_snapshot_uri}:
            raise SearchError("resolved capabilities use different registry snapshots")
        environment_digest = _environment_digest()
        experiment_uri = new_experiment_uri()
        now = _now()
        snapshot = SearchExperimentSnapshot(
            experiment_uri=experiment_uri,
            state=ExperimentState.PENDING,
            request=selected,
            input=InputValidation(status=InputStatus.ACCEPTED),
            created_at=now,
            updated_at=now,
            request_digest=request_digest,
            effective_budget=effective_budget,
            registry_snapshot_uri=registry_snapshot_uri,
            proposer_digest=proposer.implementation_digest,
            refiner_digest=refiner.implementation_digest,
            evaluator_digest=evaluator.implementation_digest,
            environment_digest=environment_digest,
        )

        created = False
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing_handle = self._reuse_request(
                connection,
                selected,
                request_digest,
            )
            if existing_handle is not None:
                return existing_handle
            connection.execute(
                """
                INSERT INTO search_experiments (
                    experiment_uri, state, snapshot_json
                ) VALUES (?, ?, ?)
                """,
                (
                    experiment_uri,
                    snapshot.state.value,
                    canonicalize_json(snapshot.model_dump(mode="json")),
                ),
            )
            connection.execute(
                """
                INSERT INTO search_idempotency (
                    idempotency_key, request_digest, experiment_uri
                ) VALUES (?, ?, ?)
                """,
                (
                    selected.idempotency_key,
                    request_digest,
                    experiment_uri,
                ),
            )
            self._append_event(
                connection,
                experiment_uri,
                event_type="REQUEST_ACCEPTED",
                payload={
                    "request": selected.model_dump(mode="json"),
                    "request_digest": request_digest,
                    "effective_budget": effective_budget.model_dump(mode="json"),
                    "plugin_identity": {
                        "plugin_id": selected.plugin_id,
                        "registry_snapshot_uri": registry_snapshot_uri,
                        "proposer_digest": proposer.implementation_digest,
                        "refiner_digest": refiner.implementation_digest,
                        "evaluator_digest": evaluator.implementation_digest,
                    },
                    "environment_digest": environment_digest,
                },
            )
            created = True

        if created:
            self._launch(experiment_uri, lifecycle_reserved=True)
        return ExperimentHandle(
            experiment_uri=experiment_uri,
            state=ExperimentState.PENDING,
        )

    def _reuse_request(
        self,
        connection: sqlite3.Connection,
        request: SearchRunRequest,
        request_digest: str,
    ) -> ExperimentHandle | None:
        existing = connection.execute(
            """
            SELECT request_digest, experiment_uri
            FROM search_idempotency
            WHERE idempotency_key = ?
            """,
            (request.idempotency_key,),
        ).fetchone()
        if existing is None:
            return None
        if existing["request_digest"] != request_digest:
            raise SearchError(
                "This idempotency key is already bound to a different request. "
                "Reuse the original request or choose a new idempotency key."
            )
        existing_snapshot = self._read_snapshot(
            connection,
            existing["experiment_uri"],
        )
        self._append_event(
            connection,
            existing_snapshot.experiment_uri,
            event_type="REQUEST_REUSED",
            payload={
                "idempotency_key": request.idempotency_key,
                "request_digest": request_digest,
                "accepted_experiment_uri": existing_snapshot.experiment_uri,
            },
        )
        return ExperimentHandle(
            experiment_uri=existing_snapshot.experiment_uri,
            state=existing_snapshot.state,
        )

    def inspect(self, experiment_uri: str) -> SearchExperimentSnapshot:
        """Read the latest durable search snapshot."""

        with self.store.connection() as connection:
            return self._read_snapshot(connection, experiment_uri)

    def contains(self, experiment_uri: str) -> bool:
        """Return whether this service owns the experiment identity."""

        with self.store.connection() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM search_experiments
                WHERE experiment_uri = ?
                """,
                (experiment_uri,),
            ).fetchone()
        return row is not None

    def wait(
        self,
        experiment_uri: str,
        *,
        timeout_seconds: float = 30,
    ) -> SearchExperimentSnapshot:
        """Wait until the search is paused or terminal."""

        deadline = time.monotonic() + timeout_seconds
        while True:
            snapshot = self.inspect(experiment_uri)
            if snapshot.state in _SETTLED_STATES:
                return snapshot
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    "The search is still running. Inspect the experiment or wait "
                    "again with a larger timeout."
                )
            with self._thread_lock:
                thread = self._threads.get(experiment_uri)
            if thread is not None:
                thread.join(timeout=min(remaining, 0.05))
            else:
                time.sleep(min(remaining, 0.05))

    def pause(self, experiment_uri: str) -> ExperimentControlResult:
        """Request a pause at the next committed checkpoint boundary."""

        return self._request_control(
            experiment_uri,
            requested_state=ExperimentState.PAUSE_REQUESTED,
            event_type="PAUSE_REQUESTED",
            detail="pause requested",
        )

    def cancel(self, experiment_uri: str) -> ExperimentControlResult:
        """Request cancellation without deleting committed lineage."""

        result = self._request_control(
            experiment_uri,
            requested_state=ExperimentState.CANCEL_REQUESTED,
            event_type="CANCEL_REQUESTED",
            detail="cancellation requested",
        )
        if result.accepted and result.state == ExperimentState.CANCEL_REQUESTED:
            self._launch(experiment_uri)
        return result

    def resume(self, experiment_uri: str) -> ExperimentControlResult:
        """Resume the same invocation from its immutable checkpoint."""

        self._require_open()
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            snapshot = self._read_snapshot(connection, experiment_uri)
            if snapshot.state != ExperimentState.PAUSED:
                return ExperimentControlResult(
                    experiment_uri=experiment_uri,
                    state=snapshot.state,
                    accepted=False,
                    detail="only a paused search can resume",
                )
            resumed = _updated_snapshot(
                snapshot,
                state=ExperimentState.PENDING,
                updated_at=_now(),
                detail="resume requested from committed checkpoint",
            )
            self._update_snapshot(connection, resumed)
            self._append_event(
                connection,
                experiment_uri,
                event_type="RESUME_REQUESTED",
                payload={
                    "checkpoint_uri": resumed.checkpoint_uri,
                    "accounting": resumed.accounting.model_dump(mode="json"),
                },
            )
        self._launch(experiment_uri)
        return ExperimentControlResult(
            experiment_uri=experiment_uri,
            state=ExperimentState.PENDING,
            accepted=True,
            detail="resume requested",
        )

    def events(self, experiment_uri: str) -> tuple[SearchLifecycleEvent, ...]:
        """Return the validated append-only lifecycle event chain."""

        with self.store.connection() as connection:
            if (
                connection.execute(
                    """
                    SELECT 1 FROM search_experiments
                    WHERE experiment_uri = ?
                    """,
                    (experiment_uri,),
                ).fetchone()
                is None
            ):
                _LOGGER.warning("search experiment not found: %s", experiment_uri)
                raise SearchError(
                    "The experiment was not found. Check the URI returned by "
                    "search.run or search.enumerate, or start a new experiment."
                )
            rows = connection.execute(
                """
                SELECT event_json
                FROM search_events
                WHERE experiment_uri = ?
                ORDER BY sequence
                """,
                (experiment_uri,),
            ).fetchall()
        events = tuple(
            SearchLifecycleEvent.model_validate(loads_strict_json(row["event_json"]))
            for row in rows
        )
        previous: str | None = None
        for event in events:
            if event.previous_event_digest != previous:
                raise SearchError("stored search event chain is invalid")
            expected = _event_digest(event)
            if event.event_digest != expected:
                raise SearchError("stored search event digest is invalid")
            previous = event.event_digest
        return events

    def _effective_budget(
        self,
        requested: SearchBudget,
        *,
        include_witness_lineage: bool,
    ) -> SearchBudget:
        """Apply the restrictive intersection of request and operator limits."""

        fixed_page_parents = 3  # claim, plugin, and one shared evaluation
        parents_per_candidate = 3 if include_witness_lineage else 1
        lineage_batch_size = (
            self.store.limits.max_parents - fixed_page_parents
        ) // parents_per_candidate
        if lineage_batch_size < 1:
            raise SearchError(
                "store parent limit cannot represent one search archive record"
            )
        return SearchBudget(
            candidates_max=min(requested.candidates_max, self.max_candidates),
            iterations_max=min(requested.iterations_max, self.max_iterations),
            wall_seconds=min(requested.wall_seconds, self.max_wall_seconds),
            batch_size=min(
                requested.batch_size,
                self.max_batch_size,
                self.evaluation.max_batch_size,
                lineage_batch_size,
            ),
            workers=requested.workers,
        )

    def _launch(
        self,
        experiment_uri: str,
        *,
        lifecycle_reserved: bool = False,
    ) -> None:
        with self._thread_lock:
            if self._closed or (self._closing and not lifecycle_reserved):
                raise SearchError("search service is closing")
            current = self._threads.get(experiment_uri)
            if current is not None and current.is_alive():
                return
            thread = threading.Thread(
                target=self._run,
                args=(experiment_uri,),
                name=(
                    f"jacobian-search-{experiment_uri.removeprefix('experiment://')}"
                ),
                daemon=True,
            )
            self._threads[experiment_uri] = thread
            thread.start()

    def _budget_exhausted(
        self,
        experiment_uri: str,
        accounting: SearchAccounting,
        budget: SearchBudget,
        *,
        wall_time_ms: int,
    ) -> bool:
        """Check if the search budget is exhausted, finishing if so.

        Returns True when the search has been finished as TIMEOUT or COMPLETED.
        The caller should return immediately when this returns True.
        """

        if wall_time_ms >= budget.wall_seconds * 1000:
            self._finish(
                experiment_uri,
                state=ExperimentState.TIMEOUT,
                stop_reason=SearchStopReason.WALL_TIME_LIMIT,
                strategy_complete=False,
                detail="search wall-clock budget exhausted",
                wall_time_ms=wall_time_ms,
            )
            return True
        if accounting.iterations >= budget.iterations_max:
            self._finish(
                experiment_uri,
                state=ExperimentState.COMPLETED,
                stop_reason=SearchStopReason.ITERATION_LIMIT,
                strategy_complete=False,
                detail="search iteration limit reached",
                wall_time_ms=wall_time_ms,
            )
            return True
        if accounting.proposed_candidates >= budget.candidates_max:
            self._finish(
                experiment_uri,
                state=ExperimentState.COMPLETED,
                stop_reason=SearchStopReason.CANDIDATE_LIMIT,
                strategy_complete=False,
                detail="search candidate limit reached",
                wall_time_ms=wall_time_ms,
            )
            return True
        return False

    def _run(self, experiment_uri: str) -> None:
        from jacobian.search.run_loop import execute_search

        execute_search(self, experiment_uri)

    def _resolve_strategy(
        self,
        snapshot: SearchExperimentSnapshot,
    ) -> tuple[ResolvedCapability, ResolvedCapability, str]:
        if (
            snapshot.proposer_digest is None
            or snapshot.refiner_digest is None
            or snapshot.evaluator_digest is None
        ):
            raise SearchError("search snapshot is missing implementation identity")
        proposer = self.plugins.resolve(
            snapshot.request.plugin_id,
            CapabilityName.PROPOSER,
        )
        refiner = self.plugins.resolve(
            snapshot.request.plugin_id,
            CapabilityName.REFINER,
        )
        evaluator = self.plugins.resolve(
            snapshot.request.plugin_id,
            CapabilityName.EVALUATOR,
        )
        if {
            proposer.registry_snapshot_uri,
            refiner.registry_snapshot_uri,
            evaluator.registry_snapshot_uri,
        } != {snapshot.registry_snapshot_uri}:
            raise SearchError("resolved strategy uses a different registry snapshot")
        if proposer.implementation_digest != snapshot.proposer_digest:
            raise SearchError("proposer identity changed after request acceptance")
        if refiner.implementation_digest != snapshot.refiner_digest:
            raise SearchError("refiner identity changed after request acceptance")
        if evaluator.implementation_digest != snapshot.evaluator_digest:
            raise SearchError("evaluator identity changed after request acceptance")
        return proposer, refiner, evaluator.implementation_digest

    def _validate_archive_page(
        self,
        *,
        snapshot: SearchExperimentSnapshot,
        page_uri: str,
        iteration: int,
        seen_uris: set[str],
        nominated_uris: set[str],
        seen_page_uris: set[str],
    ) -> tuple[SearchArchivePage, int]:
        if page_uri in seen_page_uris:
            raise SearchError("search archive contains a repeated page")
        seen_page_uris.add(page_uri)
        page_artifact = self.store.get(page_uri)
        if (
            page_artifact.manifest.schema_uri != self.archive_page_schema_uri
            or page_artifact.manifest.semantics_uri != self.semantics_uri
        ):
            raise SearchError("archive page uses the wrong contract")
        page = SearchArchivePage.model_validate(page_artifact.payload)
        if (
            page.experiment_uri != snapshot.experiment_uri
            or page.request_digest != snapshot.request_digest
            or page.claim_uri != snapshot.request.claim_uri
            or page.plugin_id != snapshot.request.plugin_id
            or page.registry_snapshot_uri != snapshot.registry_snapshot_uri
            or page.proposer_digest != snapshot.proposer_digest
            or page.refiner_digest != snapshot.refiner_digest
            or page.evaluator_digest != snapshot.evaluator_digest
        ):
            raise SearchError("archive page identity does not match the search")
        if page.iteration != iteration:
            raise SearchError("archive page iteration sequence is invalid")
        required_parents = {
            snapshot.request.claim_uri,
            snapshot.request.plugin_id,
            *_record_parents(list(page.records), page.nominations),
        }
        if not required_parents.issubset(page_artifact.manifest.parents):
            raise SearchError("archive page is missing its declared lineage")
        verified = 0
        for record in page.records:
            if record.candidate_uri in seen_uris:
                raise SearchError("candidate appears in multiple archive pages")
            seen_uris.add(record.candidate_uri)
            verified += int(record.counterexample_verified)
        for nomination in page.nominations:
            if nomination.candidate_uri not in seen_uris:
                raise SearchError("archive page nominates an unknown candidate")
            if nomination.candidate_uri in nominated_uris:
                raise SearchError("candidate is nominated more than once")
            nominated_uris.add(nomination.candidate_uri)
        return page, verified

    def _validate_checkpoint(
        self,
        *,
        snapshot: SearchExperimentSnapshot,
        page_uris: list[str],
        seen_uris: set[str],
        nominated_uris: set[str],
        verified_counterexamples: int,
        last_page: SearchArchivePage,
    ) -> dict[str, Any]:
        assert snapshot.checkpoint_uri is not None
        checkpoint_artifact = self.store.get(snapshot.checkpoint_uri)
        if (
            checkpoint_artifact.manifest.schema_uri != self.checkpoint_schema_uri
            or checkpoint_artifact.manifest.semantics_uri != self.semantics_uri
        ):
            raise SearchError("checkpoint uses the wrong contract")
        checkpoint = SearchCheckpoint.model_validate(checkpoint_artifact.payload)
        checkpoint_counts = checkpoint.accounting.model_copy(
            update={"wall_time_ms": snapshot.accounting.wall_time_ms}
        )
        if (
            checkpoint.experiment_uri != snapshot.experiment_uri
            or checkpoint.request_digest != snapshot.request_digest
            or checkpoint_counts != snapshot.accounting
            or checkpoint.accounting.wall_time_ms > snapshot.accounting.wall_time_ms
            or checkpoint.effective_budget != snapshot.effective_budget
            or checkpoint.registry_snapshot_uri != snapshot.registry_snapshot_uri
            or checkpoint.proposer_digest != snapshot.proposer_digest
            or checkpoint.refiner_digest != snapshot.refiner_digest
            or checkpoint.evaluator_digest != snapshot.evaluator_digest
            or checkpoint.environment_digest != snapshot.environment_digest
        ):
            raise SearchError("checkpoint identity does not match the search")
        if (
            checkpoint.iteration != len(page_uris)
            or checkpoint.accounting.iterations != len(page_uris)
            or checkpoint.accounting.checkpoints != len(page_uris)
            or checkpoint.latest_records != last_page.records
            or checkpoint.nominations != last_page.nominations
        ):
            raise SearchError("checkpoint progress does not match the archive")
        checkpoint_parents = {page_uris[-1]}
        if checkpoint.previous_checkpoint_uri is not None:
            checkpoint_parents.add(checkpoint.previous_checkpoint_uri)
        if not checkpoint_parents.issubset(checkpoint_artifact.manifest.parents):
            raise SearchError("checkpoint is missing its declared lineage")
        if (checkpoint.previous_checkpoint_uri is None) != (len(page_uris) == 1):
            raise SearchError("checkpoint predecessor does not match the archive")
        expected_attacks = (
            len(seen_uris) if snapshot.request.witness_role is not None else 0
        )
        if (
            snapshot.accounting.unique_candidates != len(seen_uris)
            or snapshot.accounting.evaluated_candidates != len(seen_uris)
            or snapshot.accounting.attacked_candidates != expected_attacks
            or snapshot.accounting.verified_counterexamples != verified_counterexamples
            or snapshot.accounting.nominations != len(nominated_uris)
        ):
            raise SearchError("search accounting does not match the archive")
        return checkpoint.state

    def _restore(
        self,
        snapshot: SearchExperimentSnapshot,
    ) -> tuple[
        dict[str, Any],
        list[str],
        set[str],
        set[str],
        SearchAccounting,
    ]:
        """Rebind immutable progress before returning opaque strategy state.

        Archive pages and the checkpoint must agree with the experiment,
        request, installed registry snapshot, implementation identities,
        environment, effective budget, and committed accounting. The snapshot's
        later wall-time sample may exceed the checkpoint payload because it
        includes checkpoint artifact persistence.
        """

        page_uris = list(snapshot.archive_page_uris)
        seen_uris: set[str] = set()
        nominated_uris: set[str] = set()
        seen_page_uris: set[str] = set()
        verified_counterexamples = 0
        last_page: SearchArchivePage | None = None
        for iteration, page_uri in enumerate(page_uris, start=1):
            page, verified = self._validate_archive_page(
                snapshot=snapshot,
                page_uri=page_uri,
                iteration=iteration,
                seen_uris=seen_uris,
                nominated_uris=nominated_uris,
                seen_page_uris=seen_page_uris,
            )
            verified_counterexamples += verified
            last_page = page
        if snapshot.checkpoint_uri is None:
            if page_uris or snapshot.accounting != SearchAccounting():
                raise SearchError("search progress is missing its checkpoint")
            return (
                snapshot.request.initial_state,
                page_uris,
                seen_uris,
                nominated_uris,
                snapshot.accounting,
            )
        if last_page is None:
            raise SearchError("checkpoint progress does not match the archive")
        state = self._validate_checkpoint(
            snapshot=snapshot,
            page_uris=page_uris,
            seen_uris=seen_uris,
            nominated_uris=nominated_uris,
            verified_counterexamples=verified_counterexamples,
            last_page=last_page,
        )
        return (
            state,
            page_uris,
            seen_uris,
            nominated_uris,
            snapshot.accounting,
        )

    def _mark_running(
        self,
        snapshot: SearchExperimentSnapshot,
    ) -> ExperimentState:
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._read_snapshot(connection, snapshot.experiment_uri)
            if current.state == ExperimentState.PAUSE_REQUESTED:
                paused = _updated_snapshot(
                    current,
                    state=ExperimentState.PAUSED,
                    updated_at=_now(),
                    detail="search paused before new work began",
                )
                self._update_snapshot(connection, paused)
                self._append_event(
                    connection,
                    current.experiment_uri,
                    event_type="PAUSED",
                    payload={"checkpoint_uri": paused.checkpoint_uri},
                )
                return ExperimentState.PAUSED
            if current.state == ExperimentState.CANCEL_REQUESTED:
                return ExperimentState.CANCEL_REQUESTED
            if current.state != ExperimentState.PENDING:
                raise SearchError(f"cannot start search from {current.state.value}")
            running = _updated_snapshot(
                current,
                state=ExperimentState.RUNNING,
                updated_at=_now(),
                detail="search running",
            )
            self._update_snapshot(connection, running)
            self._append_event(
                connection,
                current.experiment_uri,
                event_type="RUNNING",
                payload={"checkpoint_uri": running.checkpoint_uri},
            )
        return ExperimentState.RUNNING

    def _commit_progress(
        self,
        progress: SearchExperimentSnapshot,
    ) -> ExperimentState:
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._read_snapshot(connection, progress.experiment_uri)
            if current.state == ExperimentState.PAUSE_REQUESTED:
                committed = _updated_snapshot(
                    progress,
                    state=ExperimentState.PAUSED,
                    detail="search paused at a committed checkpoint",
                )
                event_type = "PAUSED"
            elif current.state == ExperimentState.CANCEL_REQUESTED:
                committed = _updated_snapshot(
                    progress,
                    state=ExperimentState.CANCEL_REQUESTED,
                    detail="checkpoint committed before cancellation",
                )
                event_type = "CHECKPOINT_COMMITTED"
            elif current.state == ExperimentState.RUNNING:
                committed = progress
                event_type = "CHECKPOINT_COMMITTED"
            else:
                raise SearchError(f"cannot commit progress from {current.state.value}")
            self._update_snapshot(connection, committed)
            self._append_event(
                connection,
                committed.experiment_uri,
                event_type=event_type,
                payload={
                    "checkpoint_uri": committed.checkpoint_uri,
                    "archive_page_uri": committed.archive_page_uris[-1],
                    "accounting": committed.accounting.model_dump(mode="json"),
                },
            )
        return committed.state

    def _finish_execution_failure(
        self,
        experiment_uri: str,
        execution_status: ExecutionStatus,
        detail: str,
        *,
        wall_time_ms: int,
        accounting_override: SearchAccounting | None = None,
    ) -> None:
        if execution_status == ExecutionStatus.TIMEOUT:
            self._finish(
                experiment_uri,
                state=ExperimentState.TIMEOUT,
                stop_reason=SearchStopReason.WALL_TIME_LIMIT,
                strategy_complete=False,
                detail=detail,
                wall_time_ms=wall_time_ms,
                accounting_override=accounting_override,
            )
            return
        self._finish(
            experiment_uri,
            state=ExperimentState.ERROR,
            stop_reason=SearchStopReason.ERROR,
            strategy_complete=False,
            detail=detail,
            wall_time_ms=wall_time_ms,
            accounting_override=accounting_override,
        )

    def _store_archive(
        self,
        snapshot: SearchExperimentSnapshot,
        accounting: SearchAccounting,
    ) -> ArtifactPutResult:
        manifest = SearchArchiveManifest(
            experiment_uri=snapshot.experiment_uri,
            request_digest=snapshot.request_digest,
            claim_uri=snapshot.request.claim_uri,
            plugin_id=snapshot.request.plugin_id,
            registry_snapshot_uri=snapshot.registry_snapshot_uri,
            page_uris=snapshot.archive_page_uris,
            accounting=accounting,
            effective_budget=snapshot.effective_budget,
            environment_digest=snapshot.environment_digest,
        )
        return self._put_internal_artifact(
            schema_uri=self.archive_manifest_schema_uri,
            payload=manifest.model_dump(mode="json"),
            parents=(
                snapshot.request.claim_uri,
                snapshot.request.plugin_id,
                *((snapshot.checkpoint_uri,) if snapshot.checkpoint_uri else ()),
            ),
            summary="search archive manifest",
        )

    def _finish(
        self,
        experiment_uri: str,
        *,
        state: ExperimentState,
        stop_reason: SearchStopReason,
        strategy_complete: bool,
        detail: str,
        wall_time_ms: int,
        accounting_override: SearchAccounting | None = None,
    ) -> None:
        current = self.inspect(experiment_uri)
        terminal_accounting = _updated_accounting(
            accounting_override or current.accounting,
            wall_time_ms=max(current.accounting.wall_time_ms, wall_time_ms),
        )
        archive = self._store_archive(current, terminal_accounting)
        terminal = _updated_snapshot(
            current,
            state=state,
            updated_at=_now(),
            stop_reason=stop_reason,
            strategy_reported_complete=strategy_complete,
            verification=Verification.UNVERIFIED,
            archive_uri=archive.artifact_uri,
            accounting=terminal_accounting,
            detail=detail,
        )
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            latest = self._read_snapshot(connection, experiment_uri)
            if latest.state == ExperimentState.CANCEL_REQUESTED:
                terminal = _updated_snapshot(
                    terminal,
                    state=ExperimentState.CANCELLED,
                    stop_reason=SearchStopReason.CANCELLED,
                    strategy_reported_complete=False,
                    detail=f"search cancelled; {detail}",
                )
            elif latest.state in _TERMINAL_STATES:
                raise SearchError(f"search is already terminal: {latest.state.value}")
            self._update_snapshot(connection, terminal)
            self._append_event(
                connection,
                experiment_uri,
                event_type=terminal.state.value,
                payload={
                    "stop_reason": terminal.stop_reason,
                    "archive_uri": terminal.archive_uri,
                    "checkpoint_uri": terminal.checkpoint_uri,
                    "accounting": terminal.accounting.model_dump(mode="json"),
                    "detail": terminal.detail,
                },
            )

    def _finish_if_possible(
        self,
        experiment_uri: str,
        *,
        state: ExperimentState,
        stop_reason: SearchStopReason,
        detail: str,
        wall_time_ms: int,
        accounting_override: SearchAccounting | None = None,
    ) -> None:
        try:
            snapshot = self.inspect(experiment_uri)
            if snapshot.state in _TERMINAL_STATES:
                return
            self._finish(
                experiment_uri,
                state=state,
                stop_reason=stop_reason,
                strategy_complete=False,
                detail=detail,
                wall_time_ms=wall_time_ms,
                accounting_override=accounting_override,
            )
        except (
            SearchError,
            StoreError,
            SchemaRegistryError,
            ValidationError,
        ) as exc:
            self._record_terminal_persistence_failure(
                experiment_uri,
                detail=detail,
                error=exc,
                wall_time_ms=wall_time_ms,
                accounting_override=accounting_override,
            )

    def _record_terminal_persistence_failure(
        self,
        experiment_uri: str,
        *,
        detail: str,
        error: Exception,
        wall_time_ms: int,
        accounting_override: SearchAccounting | None,
    ) -> None:
        """Fail closed when the terminal archive cannot be committed."""

        _LOGGER.warning(
            "search terminal archive persistence failed",
            exc_info=error,
        )
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._read_snapshot(connection, experiment_uri)
            if current.state in _TERMINAL_STATES:
                return
            terminal_detail = (
                "Jacobian could not save the final experiment archive. "
                "The experiment remains unverified. Check state-directory space and "
                "permissions, then inspect the experiment."
            )
            terminal = _updated_snapshot(
                current,
                state=ExperimentState.ERROR,
                updated_at=_now(),
                stop_reason=SearchStopReason.ERROR,
                strategy_reported_complete=False,
                verification=Verification.UNVERIFIED,
                archive_uri=None,
                accounting=_updated_accounting(
                    accounting_override or current.accounting,
                    wall_time_ms=max(
                        current.accounting.wall_time_ms,
                        wall_time_ms,
                    ),
                ),
                detail=terminal_detail,
            )
            self._update_snapshot(connection, terminal)
            self._append_event(
                connection,
                experiment_uri,
                event_type=ExperimentState.ERROR.value,
                payload={
                    "stop_reason": terminal.stop_reason,
                    "archive_uri": None,
                    "checkpoint_uri": terminal.checkpoint_uri,
                    "accounting": terminal.accounting.model_dump(mode="json"),
                    "detail": terminal.detail,
                },
            )

    def _request_control(
        self,
        experiment_uri: str,
        *,
        requested_state: ExperimentState,
        event_type: str,
        detail: str,
    ) -> ExperimentControlResult:
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            snapshot = self._read_snapshot(connection, experiment_uri)
            if snapshot.state in _TERMINAL_STATES:
                return ExperimentControlResult(
                    experiment_uri=experiment_uri,
                    state=snapshot.state,
                    accepted=False,
                    detail="search is already terminal",
                )
            if requested_state == ExperimentState.PAUSE_REQUESTED and (
                snapshot.state
                in {ExperimentState.PAUSED, ExperimentState.CANCEL_REQUESTED}
            ):
                return ExperimentControlResult(
                    experiment_uri=experiment_uri,
                    state=snapshot.state,
                    accepted=False,
                    detail="search cannot pause from its current state",
                )
            if requested_state == ExperimentState.CANCEL_REQUESTED and (
                snapshot.state == ExperimentState.CANCEL_REQUESTED
            ):
                return ExperimentControlResult(
                    experiment_uri=experiment_uri,
                    state=snapshot.state,
                    accepted=False,
                    detail="cancellation is already requested",
                )
            controlled = _updated_snapshot(
                snapshot,
                state=requested_state,
                updated_at=_now(),
                detail=detail,
            )
            self._update_snapshot(connection, controlled)
            self._append_event(
                connection,
                experiment_uri,
                event_type=event_type,
                payload={"checkpoint_uri": controlled.checkpoint_uri},
            )
        return ExperimentControlResult(
            experiment_uri=experiment_uri,
            state=requested_state,
            accepted=True,
            detail=detail,
        )

    def _record_operation(
        self,
        experiment_uri: str,
        *,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._append_event(
                connection,
                experiment_uri,
                event_type=event_type,
                payload=payload,
            )

    def _put_internal_artifact(
        self,
        *,
        schema_uri: str,
        payload: Any,
        parents: tuple[str, ...] = (),
        summary: str,
    ) -> ArtifactPutResult:
        return put_internal_artifact(
            self.store,
            self.schemas,
            self.semantics_uri,
            schema_uri=schema_uri,
            payload=payload,
            parents=parents,
            summary=summary,
        )

    def _read_snapshot(
        self,
        connection: sqlite3.Connection,
        experiment_uri: str,
    ) -> SearchExperimentSnapshot:
        row = connection.execute(
            """
            SELECT snapshot_json
            FROM search_experiments
            WHERE experiment_uri = ?
            """,
            (experiment_uri,),
        ).fetchone()
        if row is None:
            _LOGGER.warning("search experiment not found: %s", experiment_uri)
            raise SearchError(
                "The experiment was not found. Check the URI returned by search.run "
                "or search.enumerate, or start a new experiment."
            )
        try:
            return SearchExperimentSnapshot.model_validate(
                loads_strict_json(row["snapshot_json"])
            )
        except (ValidationError, ValueError) as exc:
            raise SearchError("stored search snapshot is invalid") from exc

    @staticmethod
    def _update_snapshot(
        connection: sqlite3.Connection,
        snapshot: SearchExperimentSnapshot,
    ) -> None:
        connection.execute(
            """
            UPDATE search_experiments
            SET state = ?, snapshot_json = ?
            WHERE experiment_uri = ?
            """,
            (
                snapshot.state.value,
                canonicalize_json(snapshot.model_dump(mode="json")),
                snapshot.experiment_uri,
            ),
        )

    @staticmethod
    def _append_event(
        connection: sqlite3.Connection,
        experiment_uri: str,
        *,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        row = connection.execute(
            """
            SELECT sequence, event_digest
            FROM search_events
            WHERE experiment_uri = ?
            ORDER BY sequence DESC
            LIMIT 1
            """,
            (experiment_uri,),
        ).fetchone()
        sequence = 0 if row is None else int(row["sequence"]) + 1
        previous_digest = None if row is None else str(row["event_digest"])
        occurred_at = _now()
        unsigned_event = SearchLifecycleEvent(
            experiment_uri=experiment_uri,
            sequence=sequence,
            event_type=event_type,
            occurred_at=occurred_at,
            payload=payload,
            previous_event_digest=previous_digest,
            event_digest="sha256:" + "0" * 64,
        )
        event = unsigned_event.model_copy(
            update={"event_digest": _event_digest(unsigned_event)}
        )
        connection.execute(
            """
            INSERT INTO search_events (
                experiment_uri, sequence, event_json, event_digest
            ) VALUES (?, ?, ?, ?)
            """,
            (
                experiment_uri,
                sequence,
                canonicalize_json(event.model_dump(mode="json")),
                event.event_digest,
            ),
        )
