from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from jacobian.contracts.discovery import (
    EnumerationBudget,
    EnumerationStopReason,
    ExperimentState,
    SearchEnumerateRequest,
)
from jacobian.contracts.evaluation import EvaluationBatchResult, EvaluationProfile
from jacobian.contracts.plugins import PluginManifest
from jacobian.contracts.results import (
    Execution,
    ExecutionStatus,
    InputStatus,
    InputValidation,
)
from jacobian.experiments import ExperimentError, ExperimentNotFoundError
from jacobian.runtime import CheckerAuthorityMode, create_runtime
from jacobian.runtime.model import JacobianRuntime
from jacobian.store import StoreError


def _claim(
    runtime: JacobianRuntime,
    *,
    reference_name: str,
    predicate: str,
    parameters: dict[str, object],
) -> tuple[str, str]:
    reference = runtime.portfolio.references[reference_name]
    claim = runtime.core.artifacts.put(
        schema_uri=reference.claim_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={
            "claim_schema_version": "1",
            "domain_id": (
                "jacobian.graph-paths"
                if reference_name == "graph_paths"
                else "jacobian.integer-matrices"
            ),
            "domain_version": "1",
            "semantics_uri": reference.semantics_uri,
            "quantifiers": [],
            "predicate": {"name": predicate, "parameters": parameters},
            "bounds": {},
            "required_capabilities": ["CandidateEnumerator", "Evaluator"],
            "correspondence_status": "HUMAN_REVIEWED",
        },
    )
    return claim.artifact_uri, reference.plugin_id


def _install_matrix_enumerator_plugin(
    runtime: JacobianRuntime,
    *,
    entrypoint: str,
    evaluator_entrypoint: str = "jacobian.plugins.matrices:evaluate_capability",
) -> str:
    matrix = runtime.portfolio.references["matrices"]
    enumerator = runtime.core.plugins.register_implementation(entrypoint)
    evaluator = runtime.core.plugins.register_implementation(evaluator_entrypoint)
    manifest = runtime.core.artifacts.put(
        schema_uri=runtime.services.reference_installer.manifest_schema_uri,
        semantics_uri=runtime.services.reference_installer.manifest_semantics_uri,
        payload=PluginManifest(
            domain_id="jacobian.integer-matrices",
            domain_version="1",
            semantics_uri=matrix.semantics_uri,
            claim_schema_uri=matrix.claim_schema_uri,
            candidate_schema_uri=matrix.candidate_schema_uri,
            capabilities={
                "CandidateEnumerator": {
                    "implementation_uri": enumerator,
                    "entrypoint": entrypoint,
                    "version": "1",
                },
                "Evaluator": {
                    "implementation_uri": evaluator,
                    "entrypoint": evaluator_entrypoint,
                    "version": "1",
                },
            },
        ).model_dump(mode="json"),
    )
    runtime.core.plugins.install(manifest.artifact_uri)
    return manifest.artifact_uri


def _matrix_claim_for_plugin(
    runtime: JacobianRuntime,
    *,
    plugin_id: str,
) -> str:
    matrix = runtime.portfolio.references["matrices"]
    claim = runtime.core.artifacts.put(
        schema_uri=matrix.claim_schema_uri,
        semantics_uri=matrix.semantics_uri,
        payload={
            "claim_schema_version": "1",
            "domain_id": "jacobian.integer-matrices",
            "domain_version": "1",
            "semantics_uri": matrix.semantics_uri,
            "quantifiers": [],
            "predicate": {"name": "is_nonsingular", "parameters": {}},
            "bounds": {},
            "required_capabilities": ["CandidateEnumerator", "Evaluator"],
            "correspondence_status": "HUMAN_REVIEWED",
        },
    )
    validation = runtime.services.claims.validate(
        claim_uri=claim.artifact_uri,
        plugin_id=plugin_id,
    )
    assert validation.valid
    return claim.artifact_uri


def test_unknown_experiment_error_explains_recovery(
    runtime,
    caplog: pytest.LogCaptureFixture,
) -> None:
    missing_uri = "experiment://missing"

    with pytest.raises(
        ExperimentNotFoundError,
        match=r"Check the URI returned by search\.run or search\.enumerate",
    ) as raised:
        runtime.services.experiments.inspect(missing_uri)

    assert missing_uri not in str(raised.value)
    assert missing_uri in caplog.text


def test_graph_enumeration_deduplicates_isomorphic_candidates(
    runtime_with_references,
) -> None:
    claim_uri, plugin_id = _claim(
        runtime_with_references,
        reference_name="graph_paths",
        predicate="is_bipartite",
        parameters={},
    )

    handle = runtime_with_references.services.experiments.start_enumeration(
        SearchEnumerateRequest(
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            bounds={"vertices": 3},
            quotient_by_isomorphism=True,
            budget=EnumerationBudget(
                candidates_max=8,
                wall_seconds=60,
                page_size=8,
            ),
        )
    )
    snapshot = runtime_with_references.services.experiments.wait(
        handle.experiment_uri,
        timeout_seconds=90,
    )

    assert snapshot.state == ExperimentState.COMPLETED
    assert snapshot.stop_reason == EnumerationStopReason.COMPLETE
    assert snapshot.enumerator_reported_complete is True
    assert snapshot.coverage.value == "EXHAUSTIVE"
    assert snapshot.verification.value == "UNVERIFIED"
    assert snapshot.accounting.raw_candidates == 8
    # Candidate identity is directed-graph identity. The upper-triangular
    # generator therefore has six directed isomorphism classes, even though
    # the same edge subsets have four underlying-undirected classes.
    assert snapshot.accounting.unique_candidates == 6
    assert snapshot.accounting.duplicate_candidates == 2
    assert snapshot.accounting.evaluated_candidates == 6
    assert snapshot.scope_uri is not None
    assert snapshot.archive_uri is not None
    scope = runtime_with_references.core.store.get(snapshot.scope_uri)
    assert scope.payload["enumerator_scope"]["arc_rule"] == (
        "v_i_to_v_j_only_when_i_less_than_j"
    )
    archive = runtime_with_references.core.store.get(snapshot.archive_uri)
    assert set(archive.manifest.parents) == {
        snapshot.scope_uri,
        *snapshot.archive_page_uris,
    }
    for page_uri in snapshot.archive_page_uris:
        page = runtime_with_references.core.store.get(page_uri)
        assert set(page.manifest.parents) == {
            *page.payload["candidate_uris"],
            *page.payload["evaluation_uris"],
        }


def test_experiment_metadata_uses_registered_schema_validation(
    runtime_with_references,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim_uri, plugin_id = _claim(
        runtime_with_references,
        reference_name="matrices",
        predicate="is_nonsingular",
        parameters={},
    )
    validated_schema_uris: list[str] = []
    validated_semantics_uris: list[str] = []
    original_validate = runtime_with_references.core.schemas.validate
    original_get_descriptor = runtime_with_references.core.store.get_descriptor

    def record_validation(schema_uri: str, payload: object) -> object:
        validated_schema_uris.append(schema_uri)
        return original_validate(schema_uri, payload)

    def record_descriptor_validation(
        artifact_uri: str,
        *,
        expected_kind: str | None = None,
    ) -> dict[str, object]:
        if expected_kind == "semantics":
            validated_semantics_uris.append(artifact_uri)
        return original_get_descriptor(
            artifact_uri,
            expected_kind=expected_kind,
        )

    monkeypatch.setattr(
        runtime_with_references.core.schemas, "validate", record_validation
    )
    monkeypatch.setattr(
        runtime_with_references.core.store,
        "get_descriptor",
        record_descriptor_validation,
    )
    handle = runtime_with_references.services.experiments.start_enumeration(
        SearchEnumerateRequest(
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            bounds={"rows": 1, "cols": 1, "entries": [0]},
            budget=EnumerationBudget(
                candidates_max=1,
                wall_seconds=30,
                page_size=1,
            ),
        )
    )
    snapshot = runtime_with_references.services.experiments.wait(
        handle.experiment_uri, timeout_seconds=30
    )

    assert snapshot.state == ExperimentState.COMPLETED
    assert (
        runtime_with_references.services.experiments.scope_schema_uri
        in validated_schema_uris
    )
    assert (
        runtime_with_references.services.experiments.evaluation_schema_uri
        in validated_schema_uris
    )
    assert (
        runtime_with_references.services.experiments.archive_page_schema_uri
        in validated_schema_uris
    )
    assert (
        runtime_with_references.services.experiments.archive_manifest_schema_uri
        in validated_schema_uris
    )
    assert (
        runtime_with_references.portfolio.references["matrices"].semantics_uri
        in validated_semantics_uris
    )


def test_matrix_enumeration_uses_the_same_experiment_contract(
    runtime_with_references,
) -> None:
    claim_uri, plugin_id = _claim(
        runtime_with_references,
        reference_name="matrices",
        predicate="is_nonsingular",
        parameters={},
    )
    handle = runtime_with_references.services.experiments.start_enumeration(
        SearchEnumerateRequest(
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            bounds={"rows": 1, "cols": 1, "entries": [0, 1]},
            budget=EnumerationBudget(
                candidates_max=2,
                wall_seconds=30,
                page_size=2,
            ),
        )
    )

    snapshot = runtime_with_references.services.experiments.wait(
        handle.experiment_uri,
        timeout_seconds=45,
    )

    assert snapshot.state == ExperimentState.COMPLETED
    assert snapshot.stop_reason == EnumerationStopReason.COMPLETE
    assert snapshot.accounting.raw_candidates == 2
    assert snapshot.accounting.unique_candidates == 2
    assert snapshot.accounting.evaluated_candidates == 2
    assert snapshot.verification.value == "UNVERIFIED"


def test_enumeration_pages_respect_evaluator_batch_limit(
    runtime_with_references,
) -> None:
    runtime_with_references.services.evaluation.max_batch_size = 2
    claim_uri, plugin_id = _claim(
        runtime_with_references,
        reference_name="matrices",
        predicate="is_nonsingular",
        parameters={},
    )
    handle = runtime_with_references.services.experiments.start_enumeration(
        SearchEnumerateRequest(
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            bounds={"rows": 1, "cols": 1, "entries": [0, 1, 2]},
            budget=EnumerationBudget(
                candidates_max=3,
                wall_seconds=30,
                page_size=3,
            ),
        )
    )

    snapshot = runtime_with_references.services.experiments.wait(
        handle.experiment_uri, timeout_seconds=30
    )

    assert snapshot.state is ExperimentState.COMPLETED
    assert snapshot.stop_reason is EnumerationStopReason.COMPLETE
    assert snapshot.accounting.raw_candidates == 3
    assert snapshot.accounting.evaluated_candidates == 3
    assert snapshot.accounting.pages == 2
    assert snapshot.scope_uri is not None
    assert snapshot.archive_uri is not None
    archive = runtime_with_references.core.store.get(snapshot.archive_uri)
    assert set(archive.manifest.parents) == {
        snapshot.scope_uri,
        snapshot.archive_page_uris[-1],
    }
    second_page = runtime_with_references.core.store.get(snapshot.archive_page_uris[-1])
    assert snapshot.archive_page_uris[0] in second_page.manifest.parents


def test_cancellation_never_becomes_an_exhaustive_conclusion(
    runtime_with_references,
) -> None:
    claim_uri, plugin_id = _claim(
        runtime_with_references,
        reference_name="matrices",
        predicate="is_nonsingular",
        parameters={},
    )
    handle = runtime_with_references.services.experiments.start_enumeration(
        SearchEnumerateRequest(
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            bounds={"rows": 3, "cols": 3, "entries": [-1, 1]},
            budget=EnumerationBudget(
                candidates_max=512,
                wall_seconds=120,
                page_size=128,
            ),
        )
    )

    cancelled = runtime_with_references.services.experiments.cancel(
        handle.experiment_uri
    )
    snapshot = runtime_with_references.services.experiments.wait(
        handle.experiment_uri,
        timeout_seconds=30,
    )

    assert cancelled.accepted is True
    assert snapshot.state == ExperimentState.CANCELLED
    assert snapshot.stop_reason == EnumerationStopReason.CANCELLED
    assert snapshot.coverage.value == "BOUNDED"
    assert snapshot.verification.value == "UNVERIFIED"
    assert snapshot.archive_uri is not None


def test_candidate_limit_never_becomes_exhaustive_coverage(
    runtime_with_references,
) -> None:
    claim_uri, plugin_id = _claim(
        runtime_with_references,
        reference_name="matrices",
        predicate="is_nonsingular",
        parameters={},
    )
    handle = runtime_with_references.services.experiments.start_enumeration(
        SearchEnumerateRequest(
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            bounds={"rows": 1, "cols": 2, "entries": [0, 1]},
            budget=EnumerationBudget(
                candidates_max=2,
                wall_seconds=30,
                page_size=2,
            ),
        )
    )

    snapshot = runtime_with_references.services.experiments.wait(
        handle.experiment_uri,
        timeout_seconds=45,
    )

    assert snapshot.state == ExperimentState.COMPLETED
    assert snapshot.stop_reason == EnumerationStopReason.CANDIDATE_LIMIT
    assert snapshot.enumerator_reported_complete is False
    assert snapshot.coverage.value == "BOUNDED"
    assert snapshot.verification.value == "UNVERIFIED"
    assert snapshot.accounting.raw_candidates == 2


def test_quotient_search_requires_a_domain_canonicalizer(
    runtime_with_references,
) -> None:
    claim_uri, plugin_id = _claim(
        runtime_with_references,
        reference_name="matrices",
        predicate="is_nonsingular",
        parameters={},
    )

    with pytest.raises(ExperimentError, match="Canonicalizer"):
        runtime_with_references.services.experiments.start_enumeration(
            SearchEnumerateRequest(
                claim_uri=claim_uri,
                plugin_id=plugin_id,
                bounds={"rows": 1, "cols": 1, "entries": [0, 1]},
                quotient_by_isomorphism=True,
                budget=EnumerationBudget(
                    candidates_max=2,
                    wall_seconds=30,
                    page_size=2,
                ),
            )
        )


def test_cancelling_a_terminal_experiment_does_not_change_it(
    runtime_with_references,
) -> None:
    claim_uri, plugin_id = _claim(
        runtime_with_references,
        reference_name="matrices",
        predicate="is_nonsingular",
        parameters={},
    )
    handle = runtime_with_references.services.experiments.start_enumeration(
        SearchEnumerateRequest(
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            bounds={"rows": 1, "cols": 1, "entries": [0]},
            budget=EnumerationBudget(
                candidates_max=1,
                wall_seconds=30,
                page_size=1,
            ),
        )
    )
    completed = runtime_with_references.services.experiments.wait(
        handle.experiment_uri,
        timeout_seconds=45,
    )

    cancelled = runtime_with_references.services.experiments.cancel(
        handle.experiment_uri
    )
    after = runtime_with_references.services.experiments.inspect(handle.experiment_uri)

    assert completed.state == ExperimentState.COMPLETED
    assert cancelled.accepted is False
    assert after == completed


def test_enumerator_candidate_is_validated_before_archival(
    runtime_with_references,
) -> None:
    plugin_id = _install_matrix_enumerator_plugin(
        runtime_with_references,
        entrypoint="tests.fixtures.plugin_functions:enumerate_invalid_candidate",
    )
    claim_uri = _matrix_claim_for_plugin(
        runtime_with_references,
        plugin_id=plugin_id,
    )

    handle = runtime_with_references.services.experiments.start_enumeration(
        SearchEnumerateRequest(
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            bounds={"fixture": True},
            budget=EnumerationBudget(
                candidates_max=1,
                wall_seconds=30,
                page_size=1,
            ),
        )
    )
    snapshot = runtime_with_references.services.experiments.wait(
        handle.experiment_uri,
        timeout_seconds=45,
    )

    assert snapshot.state == ExperimentState.ERROR
    assert snapshot.stop_reason == EnumerationStopReason.ERROR
    assert snapshot.coverage.value == "BOUNDED"
    assert snapshot.verification.value == "UNVERIFIED"
    assert snapshot.accounting.raw_candidates == 0
    assert snapshot.archive_page_uris == ()


@pytest.mark.subprocess
def test_enumerator_timeout_remains_a_bounded_nonconclusion(
    runtime_with_references,
) -> None:
    plugin_id = _install_matrix_enumerator_plugin(
        runtime_with_references,
        entrypoint="tests.fixtures.plugin_functions:wait_forever",
    )
    claim_uri = _matrix_claim_for_plugin(
        runtime_with_references,
        plugin_id=plugin_id,
    )
    handle = runtime_with_references.services.experiments.start_enumeration(
        SearchEnumerateRequest(
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            bounds={"fixture": "timeout"},
            budget=EnumerationBudget(
                candidates_max=1,
                wall_seconds=1,
                page_size=1,
            ),
        )
    )

    with pytest.raises(
        TimeoutError,
        match="Inspect it or wait again with a larger timeout",
    ):
        runtime_with_references.services.experiments.wait(
            handle.experiment_uri, timeout_seconds=0
        )

    snapshot = runtime_with_references.services.experiments.wait(
        handle.experiment_uri,
        timeout_seconds=15,
    )

    assert snapshot.state == ExperimentState.TIMEOUT
    assert snapshot.stop_reason == EnumerationStopReason.WALL_TIME_LIMIT
    assert snapshot.coverage.value == "BOUNDED"
    assert snapshot.verification.value == "UNVERIFIED"
    assert snapshot.accounting.raw_candidates == 0


@pytest.mark.subprocess
def test_evaluator_timeout_prevents_complete_enumeration_result(
    runtime_with_references,
) -> None:
    plugin_id = _install_matrix_enumerator_plugin(
        runtime_with_references,
        entrypoint="jacobian.plugins.matrices:enumerate_candidates_capability",
        evaluator_entrypoint="tests.fixtures.plugin_functions:wait_forever",
    )
    claim_uri = _matrix_claim_for_plugin(
        runtime_with_references,
        plugin_id=plugin_id,
    )
    handle = runtime_with_references.services.experiments.start_enumeration(
        SearchEnumerateRequest(
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            bounds={"rows": 1, "cols": 1, "entries": [0]},
            budget=EnumerationBudget(
                candidates_max=1,
                wall_seconds=1,
                page_size=1,
            ),
        )
    )

    snapshot = runtime_with_references.services.experiments.wait(
        handle.experiment_uri,
        timeout_seconds=15,
    )

    assert snapshot.state == ExperimentState.TIMEOUT
    assert snapshot.stop_reason == EnumerationStopReason.WALL_TIME_LIMIT
    assert snapshot.enumerator_reported_complete is False
    assert snapshot.coverage.value == "BOUNDED"
    assert snapshot.verification.value == "UNVERIFIED"


def test_rejected_evaluation_batch_fails_enumeration(
    runtime_with_references,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim_uri, plugin_id = _claim(
        runtime_with_references,
        reference_name="matrices",
        predicate="is_nonsingular",
        parameters={},
    )

    def reject_batch(**_kwargs: object) -> EvaluationBatchResult:
        return EvaluationBatchResult(
            execution=Execution(status=ExecutionStatus.COMPLETED),
            input=InputValidation(
                status=InputStatus.REJECTED,
                errors=("simulated incomplete evaluation",),
            ),
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            profile=EvaluationProfile.EXACT_CANDIDATE,
            seed=0,
        )

    monkeypatch.setattr(
        runtime_with_references.services.evaluation, "evaluate_batch", reject_batch
    )
    handle = runtime_with_references.services.experiments.start_enumeration(
        SearchEnumerateRequest(
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            bounds={"rows": 1, "cols": 1, "entries": [0]},
            budget=EnumerationBudget(
                candidates_max=1,
                wall_seconds=30,
                page_size=1,
            ),
        )
    )

    snapshot = runtime_with_references.services.experiments.wait(
        handle.experiment_uri, timeout_seconds=15
    )

    assert snapshot.state == ExperimentState.ERROR
    assert snapshot.stop_reason == EnumerationStopReason.ERROR
    assert snapshot.accounting.evaluated_candidates == 0
    assert snapshot.archive_page_uris == ()
    assert "artifact or plugin response was invalid" in snapshot.detail
    assert "reference contract" in snapshot.detail
    assert "simulated incomplete evaluation" not in snapshot.detail


def test_terminal_archive_failure_marks_enumeration_error(
    runtime_with_references,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    claim_uri, plugin_id = _claim(
        runtime_with_references,
        reference_name="matrices",
        predicate="is_nonsingular",
        parameters={},
    )
    original_put = runtime_with_references.services.experiments._put_internal_artifact

    def fail_terminal_archive(**kwargs: object) -> object:
        if kwargs.get("summary") == "enumeration archive manifest":
            raise StoreError("fixture archive failure")
        return original_put(**kwargs)

    monkeypatch.setattr(
        runtime_with_references.services.experiments,
        "_put_internal_artifact",
        fail_terminal_archive,
    )
    handle = runtime_with_references.services.experiments.start_enumeration(
        SearchEnumerateRequest(
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            bounds={"rows": 1, "cols": 1, "entries": [0]},
            budget=EnumerationBudget(
                candidates_max=1,
                wall_seconds=30,
                page_size=1,
            ),
        )
    )

    snapshot = runtime_with_references.services.experiments.wait(
        handle.experiment_uri,
        timeout_seconds=15,
    )

    assert snapshot.state == ExperimentState.ERROR
    assert snapshot.stop_reason == EnumerationStopReason.ERROR
    assert snapshot.archive_uri is None
    assert "could not save the final experiment archive" in snapshot.detail
    assert "experiment remains unverified" in snapshot.detail
    assert "StoreError" not in snapshot.detail
    assert "runtime_ms" not in snapshot.detail
    assert "fixture archive failure" not in snapshot.detail
    assert "fixture archive failure" in caplog.text


@pytest.mark.subprocess
def test_interrupted_experiment_is_recovered_as_an_error(tmp_path: Path) -> None:
    script = """
import os
import sys
from jacobian.contracts.discovery import EnumerationBudget, SearchEnumerateRequest
from jacobian.runtime import CheckerAuthorityMode, create_runtime
from jacobian.runtime.model import JacobianRuntime

root = sys.argv[1]
runtime = create_runtime(root, checker_authority=CheckerAuthorityMode.INSTALL_BUNDLED)
reference = runtime.portfolio.references["matrices"]
claim = runtime.core.artifacts.put(
    schema_uri=reference.claim_schema_uri,
    semantics_uri=reference.semantics_uri,
    payload={
        "claim_schema_version": "1",
        "domain_id": "jacobian.integer-matrices",
        "domain_version": "1",
        "semantics_uri": reference.semantics_uri,
        "quantifiers": [],
        "predicate": {"name": "is_nonsingular", "parameters": {}},
        "bounds": {},
        "required_capabilities": ["CandidateEnumerator", "Evaluator"],
        "correspondence_status": "HUMAN_REVIEWED",
    },
)
handle = runtime.services.experiments.start_enumeration(
    SearchEnumerateRequest(
        claim_uri=claim.artifact_uri,
        plugin_id=reference.plugin_id,
        bounds={"rows": 3, "cols": 3, "entries": [-1, 1]},
        budget=EnumerationBudget(
            candidates_max=512,
            wall_seconds=120,
            page_size=1,
        ),
    )
)
print(handle.experiment_uri, flush=True)
os._exit(0)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    experiment_uri = completed.stdout.strip().splitlines()[-1]

    recovered_runtime = create_runtime(
        tmp_path, checker_authority=CheckerAuthorityMode.INSTALL_BUNDLED
    )
    recovered = recovered_runtime.services.experiments.inspect(experiment_uri)

    assert recovered.state == ExperimentState.ERROR
    assert recovered.stop_reason == EnumerationStopReason.ERROR
    assert recovered.coverage.value == "BOUNDED"
    assert recovered.verification.value == "UNVERIFIED"
    assert "ended before completion" in recovered.detail


def test_corrupt_enumeration_snapshot_does_not_block_other_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = create_runtime(
        tmp_path, checker_authority=CheckerAuthorityMode.INSTALL_BUNDLED
    )
    claim_uri, plugin_id = _claim(
        runtime,
        reference_name="matrices",
        predicate="is_nonsingular",
        parameters={},
    )
    monkeypatch.setattr(
        runtime.services.experiments,
        "_run_enumeration",
        lambda _experiment_uri: None,
    )
    valid = runtime.services.experiments.start_enumeration(
        SearchEnumerateRequest(
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            bounds={"rows": 1, "cols": 1, "entries": [0]},
            budget=EnumerationBudget(
                candidates_max=1,
                wall_seconds=30,
                page_size=1,
            ),
        )
    )
    valid_snapshot = runtime.services.experiments.inspect(valid.experiment_uri)
    corrupt_uri = "experiment://ffffffffffffffffffffffffffffffff"
    mismatched_uri = "experiment://eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    invalid_state_uri = "experiment://dddddddddddddddddddddddddddddddd"
    with sqlite3.connect(runtime.core.store.db_path) as connection:
        connection.execute(
            """
            INSERT INTO experiments (
                experiment_uri, state, snapshot_json
            ) VALUES (?, 'RUNNING', ?)
            """,
            (corrupt_uri, b"{"),
        )
        connection.execute(
            """
            INSERT INTO experiments (
                experiment_uri, state, snapshot_json
            ) VALUES (?, 'PENDING', ?)
            """,
            (
                mismatched_uri,
                valid_snapshot.model_dump_json().encode(),
            ),
        )
        invalid_state_snapshot = valid_snapshot.model_copy(
            update={"experiment_uri": invalid_state_uri}
        )
        connection.execute(
            """
            INSERT INTO experiments (
                experiment_uri, state, snapshot_json
            ) VALUES (?, 'BROKEN', ?)
            """,
            (
                invalid_state_uri,
                invalid_state_snapshot.model_dump_json().encode(),
            ),
        )

    recovered = create_runtime(
        tmp_path, checker_authority=CheckerAuthorityMode.INSTALL_BUNDLED
    )

    assert recovered.services.experiments.inspect(valid.experiment_uri).state is (
        ExperimentState.ERROR
    )
    with sqlite3.connect(recovered.core.store.db_path) as connection:
        states = connection.execute(
            """
            SELECT experiment_uri, state
            FROM experiments
            WHERE experiment_uri IN (?, ?, ?)
            ORDER BY experiment_uri
            """,
            (corrupt_uri, mismatched_uri, invalid_state_uri),
        ).fetchall()
        failures = connection.execute(
            """
            SELECT experiment_uri, snapshot_digest, detail
            FROM experiment_recovery_failures
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
