"""Search experiment execution loop."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError

from jacobian.contracts.discovery import ExperimentState
from jacobian.contracts.results import ExecutionStatus
from jacobian.contracts.search import (
    PluginProposalResponse,
    PluginRefinementResponse,
    SearchAccounting,
    SearchArchivePage,
    SearchCandidateRecord,
    SearchCheckpoint,
    SearchStopReason,
)
from jacobian.contracts.witness_search import WitnessSearchStatus
from jacobian.evaluation import require_complete_evaluation_batch
from jacobian.plugins.registry import PluginRegistryError
from jacobian.schema_registry import SchemaRegistryError
from jacobian.search._helpers import (
    _deduplicate_nominations,
    _digest,
    _is_verified_counterexample,
    _now,
    _record_parents,
    _require_remaining_seconds,
    _search_failure_detail,
    _updated_accounting,
    _updated_snapshot,
    _used_wall_ms,
)
from jacobian.search.errors import SearchError, _SearchBudgetExhaustedError
from jacobian.store import StoreError

if TYPE_CHECKING:
    from jacobian.search.service import SearchService


def execute_search(service: SearchService, experiment_uri: str) -> None:
    """Execute one durable search experiment until a terminal state."""
    started = service._clock()
    accounting = SearchAccounting()
    partial_accounting = accounting
    try:
        snapshot = service.inspect(experiment_uri)
        transition = service._mark_running(snapshot)
        if transition == ExperimentState.PAUSED:
            return
        if transition == ExperimentState.CANCEL_REQUESTED:
            service._finish(
                experiment_uri,
                state=ExperimentState.CANCELLED,
                stop_reason=SearchStopReason.CANCELLED,
                strategy_complete=False,
                detail="search cancelled before execution",
                wall_time_ms=_used_wall_ms(accounting, started, service._clock),
            )
            return

        snapshot = service.inspect(experiment_uri)
        request = snapshot.request
        proposer, refiner, evaluator_digest = service._resolve_strategy(snapshot)

        (
            strategy_state,
            page_uris,
            seen_uris,
            nominated_uris,
            accounting,
        ) = service._restore(snapshot)
        partial_accounting = accounting
        claim = service.store.get(request.claim_uri)
        manifest = service.plugins.get(request.plugin_id)
        semantics = service.store.get(manifest.semantics_uri)

        while True:
            total_wall_ms = _used_wall_ms(accounting, started, service._clock)
            budget = snapshot.effective_budget
            if service._budget_exhausted(
                experiment_uri,
                accounting,
                budget,
                wall_time_ms=total_wall_ms,
            ):
                return

            remaining_candidates = (
                budget.candidates_max - accounting.proposed_candidates
            )
            batch_size = min(budget.batch_size, remaining_candidates)
            remaining_seconds = max(
                0.001,
                budget.wall_seconds - total_wall_ms / 1000,
            )
            proposer_request = {
                "request_version": "1",
                "claim": claim.payload,
                "state": strategy_state,
                "batch_size": batch_size,
                "seed": request.seed,
                "remaining_budget": {
                    "candidates": remaining_candidates,
                    "iterations": (budget.iterations_max - accounting.iterations),
                    "wall_ms": max(1, int(remaining_seconds * 1000)),
                },
                "bindings": {
                    "claim_digest": claim.manifest.object_digest,
                    "semantics_digest": semantics.manifest.object_digest,
                    "plugin_id": request.plugin_id,
                    "request_digest": snapshot.request_digest,
                },
            }
            proposal_execution = service.executor.run(
                entrypoint=proposer.descriptor.entrypoint,
                implementation_digest=proposer.implementation_digest,
                request=proposer_request,
                timeout_seconds=remaining_seconds,
            )
            service._record_operation(
                experiment_uri,
                event_type="PROPOSER_COMPLETED",
                payload={
                    "iteration": accounting.iterations + 1,
                    "status": proposal_execution.status.value,
                    "implementation_digest": proposer.implementation_digest,
                    "request_digest": _digest(proposer_request),
                    "output_digest": (
                        _digest(proposal_execution.output)
                        if proposal_execution.output is not None
                        else None
                    ),
                    "runtime_ms": proposal_execution.runtime_ms,
                    "detail": proposal_execution.detail,
                },
            )
            if proposal_execution.status != ExecutionStatus.COMPLETED:
                service._finish_execution_failure(
                    experiment_uri,
                    proposal_execution.status,
                    proposal_execution.detail or "proposer execution failed",
                    wall_time_ms=_used_wall_ms(accounting, started, service._clock),
                )
                return
            proposal = PluginProposalResponse.model_validate(proposal_execution.output)
            if len(proposal.candidates) > batch_size:
                raise SearchError("proposer returned more candidates than authorized")

            selected_uris: list[str] = []
            proposed = accounting.proposed_candidates + len(proposal.candidates)
            duplicates = accounting.duplicate_candidates
            unique = accounting.unique_candidates
            for payload in proposal.candidates:
                normalized = service.schemas.validate(
                    manifest.candidate_schema_uri,
                    payload,
                )
                candidate = service.store.put(
                    schema_uri=manifest.candidate_schema_uri,
                    semantics_uri=manifest.semantics_uri,
                    payload=normalized,
                    parents=(request.claim_uri, request.plugin_id),
                    summary="search candidate proposed by untrusted strategy",
                )
                if candidate.artifact_uri in seen_uris:
                    duplicates += 1
                    partial_accounting = _updated_accounting(
                        accounting,
                        proposed_candidates=unique + duplicates,
                        unique_candidates=unique,
                        duplicate_candidates=duplicates,
                    )
                    continue
                seen_uris.add(candidate.artifact_uri)
                selected_uris.append(candidate.artifact_uri)
                unique += 1
                partial_accounting = _updated_accounting(
                    accounting,
                    proposed_candidates=unique + duplicates,
                    unique_candidates=unique,
                    duplicate_candidates=duplicates,
                )

            records: list[SearchCandidateRecord] = []
            evaluated = accounting.evaluated_candidates
            attacked = accounting.attacked_candidates
            verified_counterexamples = accounting.verified_counterexamples
            if selected_uris:
                remaining_seconds = _require_remaining_seconds(
                    budget,
                    accounting,
                    started,
                    service._clock,
                )
                evaluation = service.evaluation.evaluate_batch(
                    claim_uri=request.claim_uri,
                    candidate_uris=tuple(selected_uris),
                    plugin_id=request.plugin_id,
                    profile=request.profile,
                    seed=request.seed,
                    wall_seconds=remaining_seconds,
                )
                require_complete_evaluation_batch(evaluation, selected_uris)
                evaluated += len(selected_uris)
                partial_accounting = _updated_accounting(
                    partial_accounting,
                    evaluated_candidates=evaluated,
                )
                evaluation_artifact = service._put_internal_artifact(
                    schema_uri=service.evaluation_schema_uri,
                    payload=evaluation.model_dump(mode="json"),
                    parents=(request.claim_uri, *selected_uris),
                    summary="untrusted search evaluation batch",
                )
                service._record_operation(
                    experiment_uri,
                    event_type="EVALUATION_COMMITTED",
                    payload={
                        "iteration": accounting.iterations + 1,
                        "candidate_uris": selected_uris,
                        "evaluation_uri": evaluation_artifact.artifact_uri,
                        "evaluator_digest": evaluator_digest,
                        "status": evaluation.execution.status.value,
                        "runtime_ms": evaluation.execution.runtime_ms,
                    },
                )
                for candidate_uri in selected_uris:
                    witness_uri: str | None = None
                    verification_record_uri: str | None = None
                    counterexample_verified = False
                    detail = ""
                    if request.witness_role is not None:
                        remaining_seconds = _require_remaining_seconds(
                            budget,
                            accounting,
                            started,
                            service._clock,
                        )
                        attacked += 1
                        partial_accounting = _updated_accounting(
                            partial_accounting,
                            attacked_candidates=attacked,
                        )
                        witness_result = service.witnesses.find(
                            claim_uri=request.claim_uri,
                            candidate_uri=candidate_uri,
                            plugin_id=request.plugin_id,
                            witness_role=request.witness_role,
                            wall_seconds=remaining_seconds,
                        )
                        witness_uri = witness_result.witness_uri
                        detail = witness_result.detail
                        if (
                            witness_result.status == WitnessSearchStatus.FOUND
                            and witness_uri is not None
                        ):
                            checker_id = request.counterexample_checker_id
                            if checker_id is None:
                                raise SearchError(
                                    "A counterexample witness was found, but no "
                                    "checker was supplied. Set "
                                    "counterexample_checker_id from the reference "
                                    "contract and retry."
                                )
                            checker_remaining = _require_remaining_seconds(
                                budget,
                                accounting,
                                started,
                                service._clock,
                            )
                            verified = service.verification.verify_witness(
                                claim_uri=request.claim_uri,
                                candidate_uri=candidate_uri,
                                witness_uri=witness_uri,
                                checker_id=checker_id,
                                timeout_seconds=checker_remaining,
                            )
                            if _is_verified_counterexample(verified):
                                counterexample_verified = True
                                verification_record_uri = (
                                    verified.verification_record_uri
                                )
                                verified_counterexamples += 1
                                partial_accounting = _updated_accounting(
                                    partial_accounting,
                                    verified_counterexamples=(verified_counterexamples),
                                )
                        service._record_operation(
                            experiment_uri,
                            event_type="COUNTEREXAMPLE_ATTEMPTED",
                            payload={
                                "iteration": accounting.iterations + 1,
                                "candidate_uri": candidate_uri,
                                "status": witness_result.status.value,
                                "witness_uri": witness_uri,
                                "verification_record_uri": (verification_record_uri),
                                "verified": counterexample_verified,
                            },
                        )
                    records.append(
                        SearchCandidateRecord(
                            candidate_uri=candidate_uri,
                            evaluation_uri=evaluation_artifact.artifact_uri,
                            witness_uri=witness_uri,
                            verification_record_uri=verification_record_uri,
                            counterexample_verified=counterexample_verified,
                            detail=detail,
                        )
                    )

            refiner_request = {
                "request_version": "1",
                "claim": claim.payload,
                "state": proposal.state,
                "feedback": [record.model_dump(mode="json") for record in records],
                "strategy_reported_complete": proposal.complete,
                "seed": request.seed,
                "bindings": {
                    "claim_digest": claim.manifest.object_digest,
                    "semantics_digest": semantics.manifest.object_digest,
                    "plugin_id": request.plugin_id,
                    "request_digest": snapshot.request_digest,
                },
            }
            remaining_seconds = _require_remaining_seconds(
                budget,
                accounting,
                started,
                service._clock,
            )
            refinement_execution = service.executor.run(
                entrypoint=refiner.descriptor.entrypoint,
                implementation_digest=refiner.implementation_digest,
                request=refiner_request,
                timeout_seconds=remaining_seconds,
            )
            service._record_operation(
                experiment_uri,
                event_type="REFINER_COMPLETED",
                payload={
                    "iteration": accounting.iterations + 1,
                    "status": refinement_execution.status.value,
                    "implementation_digest": refiner.implementation_digest,
                    "request_digest": _digest(refiner_request),
                    "output_digest": (
                        _digest(refinement_execution.output)
                        if refinement_execution.output is not None
                        else None
                    ),
                    "runtime_ms": refinement_execution.runtime_ms,
                    "detail": refinement_execution.detail,
                    "feedback_records": [
                        record.model_dump(mode="json") for record in records
                    ],
                },
            )
            if refinement_execution.status != ExecutionStatus.COMPLETED:
                service._finish_execution_failure(
                    experiment_uri,
                    refinement_execution.status,
                    refinement_execution.detail or "refiner execution failed",
                    wall_time_ms=_used_wall_ms(accounting, started, service._clock),
                    accounting_override=partial_accounting,
                )
                return
            refinement = PluginRefinementResponse.model_validate(
                refinement_execution.output
            )
            for nomination in refinement.nominations:
                if nomination.candidate_uri not in seen_uris:
                    raise SearchError(
                        "refiner nominated a candidate outside this search"
                    )
            nominations = tuple(
                nomination
                for nomination in _deduplicate_nominations(refinement.nominations)
                if nomination.candidate_uri not in nominated_uris
            )
            nominated_uris.update(
                nomination.candidate_uri for nomination in nominations
            )
            completed_wall_ms = _used_wall_ms(accounting, started, service._clock)
            next_accounting = SearchAccounting(
                proposed_candidates=proposed,
                unique_candidates=unique,
                duplicate_candidates=duplicates,
                evaluated_candidates=evaluated,
                attacked_candidates=attacked,
                verified_counterexamples=verified_counterexamples,
                iterations=accounting.iterations + 1,
                checkpoints=accounting.checkpoints + 1,
                nominations=accounting.nominations + len(nominations),
                wall_time_ms=completed_wall_ms,
            )
            partial_accounting = next_accounting
            page = SearchArchivePage(
                experiment_uri=experiment_uri,
                request_digest=snapshot.request_digest,
                claim_uri=request.claim_uri,
                plugin_id=request.plugin_id,
                registry_snapshot_uri=snapshot.registry_snapshot_uri,
                iteration=next_accounting.iterations,
                proposer_digest=proposer.implementation_digest,
                refiner_digest=refiner.implementation_digest,
                evaluator_digest=evaluator_digest,
                records=tuple(records),
                nominations=nominations,
            )
            page_parents = _record_parents(records, nominations)
            stored_page = service._put_internal_artifact(
                schema_uri=service.archive_page_schema_uri,
                payload=page.model_dump(mode="json"),
                parents=(request.claim_uri, request.plugin_id, *page_parents),
                summary="search archive page",
            )
            page_uris.append(stored_page.artifact_uri)
            checkpoint = SearchCheckpoint(
                experiment_uri=experiment_uri,
                request_digest=snapshot.request_digest,
                iteration=next_accounting.iterations,
                state=refinement.state,
                latest_records=tuple(records),
                nominations=nominations,
                accounting=next_accounting,
                effective_budget=budget,
                registry_snapshot_uri=snapshot.registry_snapshot_uri,
                proposer_digest=proposer.implementation_digest,
                refiner_digest=refiner.implementation_digest,
                evaluator_digest=evaluator_digest,
                environment_digest=snapshot.environment_digest,
                previous_checkpoint_uri=snapshot.checkpoint_uri,
            )
            checkpoint_parents = [stored_page.artifact_uri]
            if snapshot.checkpoint_uri is not None:
                checkpoint_parents.append(snapshot.checkpoint_uri)
            stored_checkpoint = service._put_internal_artifact(
                schema_uri=service.checkpoint_schema_uri,
                payload=checkpoint.model_dump(mode="json"),
                parents=tuple(checkpoint_parents),
                summary="immutable search checkpoint",
            )
            persisted_accounting = next_accounting.model_copy(
                update={
                    "wall_time_ms": _used_wall_ms(
                        accounting,
                        started,
                        service._clock,
                    )
                }
            )
            partial_accounting = persisted_accounting
            current = service.inspect(experiment_uri)
            progress = _updated_snapshot(
                current,
                state=ExperimentState.RUNNING,
                updated_at=_now(),
                checkpoint_uri=stored_checkpoint.artifact_uri,
                archive_page_uris=tuple(page_uris),
                accounting=persisted_accounting,
                detail=proposal.detail or refinement.detail,
            )
            control_state = service._commit_progress(progress)
            snapshot = service.inspect(experiment_uri)
            strategy_state = refinement.state
            accounting = persisted_accounting
            started = service._clock()
            if control_state == ExperimentState.PAUSED:
                return
            if control_state == ExperimentState.CANCEL_REQUESTED:
                service._finish(
                    experiment_uri,
                    state=ExperimentState.CANCELLED,
                    stop_reason=SearchStopReason.CANCELLED,
                    strategy_complete=False,
                    detail="search cancelled",
                    wall_time_ms=accounting.wall_time_ms,
                )
                return
            if accounting.wall_time_ms >= budget.wall_seconds * 1000:
                service._finish(
                    experiment_uri,
                    state=ExperimentState.TIMEOUT,
                    stop_reason=SearchStopReason.WALL_TIME_LIMIT,
                    strategy_complete=False,
                    detail="search wall-clock budget exhausted",
                    wall_time_ms=accounting.wall_time_ms,
                )
                return
            if proposal.complete:
                service._finish(
                    experiment_uri,
                    state=ExperimentState.COMPLETED,
                    stop_reason=SearchStopReason.STRATEGY_COMPLETE,
                    strategy_complete=True,
                    detail="strategy reported completion",
                    wall_time_ms=accounting.wall_time_ms,
                )
                return
    except _SearchBudgetExhaustedError as exc:
        service._finish_if_possible(
            experiment_uri,
            state=ExperimentState.TIMEOUT,
            stop_reason=SearchStopReason.WALL_TIME_LIMIT,
            detail=str(exc),
            wall_time_ms=_used_wall_ms(accounting, started, service._clock),
            accounting_override=partial_accounting,
        )
    except (
        SearchError,
        PluginRegistryError,
        SchemaRegistryError,
        StoreError,
        ValidationError,
        ValueError,
    ) as exc:
        detail = _search_failure_detail(exc, experiment_uri)
        service._finish_if_possible(
            experiment_uri,
            state=ExperimentState.ERROR,
            stop_reason=SearchStopReason.ERROR,
            detail=detail,
            wall_time_ms=_used_wall_ms(accounting, started, service._clock),
            accounting_override=partial_accounting,
        )
    finally:
        with service._thread_lock:
            service._threads.pop(experiment_uri, None)
