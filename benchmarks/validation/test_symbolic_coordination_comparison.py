from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from benchmarks.tooling import symbolic_coordination_comparison as comparison
from jsonschema import Draft202012Validator
from pydantic import ValidationError


def _binding(task_id: str, family: str) -> comparison.TaskBinding:
    digest = "sha256:" + "1" * 64
    return comparison.TaskBinding(
        task_id=task_id,
        family=family,
        harbor_digest="1" * 64,
        public_file_hashes={"input.json": digest},
        verifier_hashes={"verifier.py": digest},
    )


def _manifest(root: Path, *, repetitions: int = 2) -> comparison.ExperimentManifest:
    tasks = [
        _binding("symbolic-coordination-near-miss-01", "perturbed-near-miss"),
        _binding("symbolic-coordination-grid-exhausted-01", "bounded-collision-scope"),
    ]
    preflight = {"schema_version": "1", "status": "READY"}
    planned_runs = len(tasks) * repetitions * 3
    body: dict[str, Any] = {
        "schema_version": "1",
        "contract_versions": {
            "experiment_manifest": "1",
            "comparison_report": "1",
            "trajectory_telemetry": "1",
            "runner": "1",
        },
        "created_at": "2026-08-05T00:00:00+00:00",
        "evidence_class": "host-local-workflow-observation",
        "causal_claim_authorized": False,
        "source_revision": "2" * 40,
        "source_branch": "bench/test",
        "stack_revisions": {"pr3": "3" * 40, "pr4": "2" * 40},
        "dataset_id": "symbolic-coordination-v1",
        "tasks": [item.model_dump(mode="json") for item in tasks],
        "repetitions": repetitions,
        "conditions": {
            "A": {
                "jacobian_enabled": False,
                "post_solution_audit": False,
                "reasoning_log_mode": "OFF",
            },
            "B": {
                "jacobian_enabled": True,
                "post_solution_audit": False,
                "reasoning_log_mode": "REQUIRED",
            },
            "C": {
                "jacobian_enabled": True,
                "post_solution_audit": True,
                "audit_passes": 1,
                "allowed_revisions": 1,
                "reasoning_log_mode": "REQUIRED",
                "audit_stage_jacobian_enabled": False,
            },
        },
        "model": {
            "slug": "gpt-5.3-codex-spark",
            "display_name": "GPT-5.3-Codex-Spark",
            "description": "test model",
            "priority": 26,
            "visibility": "list",
            "supported_in_api": False,
            "shell_type": "shell_command",
            "context_window": 128000,
            "max_context_window": 128000,
            "supports_parallel_tool_calls": True,
            "supported_reasoning_levels": ["low", "medium"],
            "tool_mode": None,
            "selection_basis": "test-selection",
        },
        "model_contract_digest": "sha256:" + "4" * 64,
        "reasoning_effort": "medium",
        "codex": {
            "version": "0.146.0",
            "executable_digest": "sha256:" + "7" * 64,
            "ignore_user_config": True,
            "ignore_rules": True,
        },
        "auth": {
            "mode": "chatgpt",
            "api_key": False,
            "ephemeral_session": True,
            "credential_material_recorded": False,
        },
        "prompt_digests": {
            "primary": "sha256:" + "5" * 64,
            "audit": "sha256:" + "6" * 64,
        },
        "budgets": {
            "primary_wall_seconds": {
                "availability": "EXACT",
                "value": 900.0,
                "unit": "seconds",
            },
            "audit_wall_seconds": {
                "availability": "EXACT",
                "value": 600.0,
                "unit": "seconds",
            },
            "tokens_per_stage": {
                "availability": "EXACT",
                "value": 800000,
                "unit": "tokens",
            },
            "tool_calls_per_stage": {
                "availability": "UNBOUNDED",
                "value": None,
                "unit": "calls",
            },
            "cost": {"availability": "UNAVAILABLE", "value": None, "unit": "USD"},
            "condition_runs": {
                "availability": "EXACT",
                "value": planned_runs,
                "unit": "condition-runs",
            },
        },
        "mcp": {
            "executable_digest": "sha256:" + "8" * 64,
            "policy_profile": "COMPUTE_VERIFY_NO_RETRIEVAL",
            "conditions": ["B", "C"],
            "audit_stage_enabled": False,
        },
        "runtime": {
            "python": "3.12",
            "platform": "test-platform",
            "harbor_version": "0.20.0",
            "uv_lock_digest": "sha256:" + "9" * 64,
            "pilot_manifest_digest": "sha256:" + "a" * 64,
            "preflight_report_digest": comparison._digest(preflight),
            "sampling_seed": None,
            "sampling_temperature": None,
            "sampling_source": "codex-cli-chatgpt-defaults-no-cli-overrides",
        },
        "order_method": "balanced-permutation-v1",
        "runs": [
            item.model_dump(mode="json")
            for item in comparison.counterbalanced_runs(
                [task.task_id for task in tasks], repetitions
            )
        ],
    }
    manifest = comparison.ExperimentManifest.model_validate(
        {**body, "experiment_id": comparison._digest(body)}
    )
    root.mkdir()
    (root / "experiment-manifest.json").write_bytes(
        comparison._canonical_bytes(manifest.model_dump(mode="json"))
    )
    (root / "preflight.json").write_bytes(comparison._canonical_bytes(preflight))
    return manifest


def _record(
    unit: comparison.RunUnit,
    *,
    accepted: bool | None = True,
    infrastructure: str = "COMPLETE",
    audit: str | None = None,
    tokens: int | None = 100,
) -> Any:
    verifier = None
    if accepted is not None:
        score = 1.0 if accepted else 0.0
        verifier = SimpleNamespace(
            reward=score,
            correctness=score,
            evidence_validity=score,
            scope_accuracy=score,
            assurance_calibration=score,
            input_binding=score,
            artifact_binding=score,
            protocol_compliance=score,
            false_certification=False,
        )
    usage = SimpleNamespace(
        primary=SimpleNamespace(
            availability="EXACT" if tokens is not None else "UNAVAILABLE",
            total_tokens=tokens,
        ),
        audit=(
            SimpleNamespace(availability="EXACT", total_tokens=10)
            if unit.condition == "C" and tokens is not None
            else None
        ),
    )
    return SimpleNamespace(
        task_id=unit.task_id,
        task_family=(
            "perturbed-near-miss"
            if "near-miss" in unit.task_id
            else "bounded-collision-scope"
        ),
        condition=unit.condition,
        source_revision="2" * 40,
        model="gpt-5.3-codex-spark",
        reasoning_effort="medium",
        infrastructure_status=infrastructure,
        infrastructure_failures=[]
        if infrastructure == "COMPLETE"
        else ["primary:TIMEOUT"],
        usage=usage,
        wall_time=SimpleNamespace(total_seconds=1.5 if tokens is not None else None),
        calls=SimpleNamespace(
            mcp_calls=1 if unit.condition != "A" else 0,
            shell_calls=1,
            discovery_calls=1 if unit.condition != "A" else 0,
            invocation_calls=1 if unit.condition != "A" else 0,
            schema_valid_calls=1 if unit.condition != "A" else 0,
            executable_calls=1 if unit.condition != "A" else 0,
            failed_calls=0,
            repeated_calls=0,
            task_irrelevant_calls=0,
            producer_calls=1 if unit.condition != "A" else 0,
            checker_calls=0,
            candidate_or_witness_productions=0,
            missing_applicable_checker=0,
            recovered_calls=0,
        ),
        audit=SimpleNamespace(
            final_verifier=verifier,
            classification=audit
            or ("ALREADY_CORRECT" if unit.condition == "C" else "NOT_APPLICABLE"),
            revision_applied=(audit in {"REPAIR", "REGRESSION"})
            if unit.condition == "C"
            else None,
        ),
        reasoning_protocol=SimpleNamespace(
            compliance="NOT_APPLICABLE" if unit.condition == "A" else "COMPLETE",
            log_entries=0 if unit.condition == "A" else 4,
            log_bytes=0 if unit.condition == "A" else 256,
            token_overhead_availability="UNAVAILABLE",
            token_overhead_tokens=None,
        ),
        classification=SimpleNamespace(protocol_violations=[]),
        source_artifact_index_digest="sha256:" + "7" * 64,
    )


def _patch_records(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
    manifest: comparison.ExperimentManifest,
    overrides: dict[tuple[str, int, str], dict[str, Any]] | None = None,
) -> None:
    values = overrides or {}
    for unit in manifest.runs:
        (root / unit.run_relpath).mkdir(parents=True)

    def load(_root: Path, _manifest: Any, unit: comparison.RunUnit) -> Any:
        return _record(
            unit,
            **values.get((unit.task_id, unit.repetition, unit.condition), {}),
        )

    monkeypatch.setattr(comparison, "_record_matches_unit", load)


def test_counterbalance_and_unique_ids(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "experiment")
    assert len(manifest.runs) == 12
    assert len({item.run_id for item in manifest.runs}) == 12
    orders = []
    for repetition in range(2):
        for task in manifest.tasks:
            block = sorted(
                (
                    item
                    for item in manifest.runs
                    if item.task_id == task.task_id and item.repetition == repetition
                ),
                key=lambda item: item.block_position,
            )
            orders.append(tuple(item.condition for item in block))
    assert len(set(orders)) == 4
    assert any(order != ("A", "B", "C") for order in orders)


def test_manifest_drift_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "experiment"
    _manifest(root)
    payload = json.loads((root / "experiment-manifest.json").read_text())
    payload["reasoning_effort"] = "high"
    (root / "experiment-manifest.json").write_text(json.dumps(payload))
    with pytest.raises(comparison.ComparisonError, match="digest drift"):
        comparison.load_manifest(root)


def test_manifest_rejects_source_stack_substitution(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "experiment")
    payload = manifest.model_dump(mode="json")
    payload["stack_revisions"]["pr4"] = "9" * 40
    with pytest.raises(ValidationError, match="must equal the clean source"):
        comparison.ExperimentManifest.model_validate(payload)


def test_duplicate_run_id_is_rejected(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "experiment")
    payload = manifest.model_dump(mode="json")
    payload["runs"][1]["run_id"] = payload["runs"][0]["run_id"]
    with pytest.raises(ValidationError, match="duplicate run identity"):
        comparison.ExperimentManifest.model_validate(payload)


def test_resume_is_idempotent_and_does_not_retry_wrong_answer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "experiment"
    manifest = _manifest(root, repetitions=1)
    _patch_records(
        monkeypatch,
        root,
        manifest,
        {(manifest.tasks[0].task_id, 0, "A"): {"accepted": False}},
    )
    monkeypatch.setattr(
        comparison, "_validate_current_contract", lambda _manifest: None
    )
    calls: list[str] = []
    monkeypatch.setattr(
        comparison.codex, "execute", lambda **kwargs: calls.append(str(kwargs))
    )
    result = comparison.run_experiment(root, source={}, max_model_executions=6)
    assert result == {"observed": 6, "executed": 0, "infrastructure_incomplete": 0}
    assert calls == []


def test_explicit_retry_only_archives_infrastructure_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "experiment"
    manifest = _manifest(root, repetitions=1)
    first = manifest.runs[0]
    first_root = root / first.run_relpath
    first_root.mkdir(parents=True)
    (first_root / "raw.txt").write_text("preserve me")
    states = {first.run_id: "INCOMPLETE"}

    def load(run_root: Path, _manifest: Any, unit: comparison.RunUnit) -> Any:
        status = states.get(unit.run_id, "COMPLETE")
        return _record(unit, infrastructure=status)

    def execute(**kwargs: Any) -> None:
        output = Path(kwargs["output_path"])
        output.mkdir(parents=True)
        states[first.run_id] = "COMPLETE"

    monkeypatch.setattr(comparison, "_record_matches_unit", load)
    monkeypatch.setattr(
        comparison, "_validate_current_contract", lambda _manifest: None
    )
    monkeypatch.setattr(comparison.codex, "execute", execute)
    result = comparison.run_experiment(
        root,
        source={},
        max_model_executions=1,
        retry_infrastructure=True,
    )
    archived = root / "retry-history" / first.run_id / "run-attempt-001" / "raw.txt"
    assert archived.read_text() == "preserve me"
    assert result["executed"] == 1


def test_partial_and_pre_model_failures_are_separate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "experiment"
    manifest = _manifest(root, repetitions=1)
    present = manifest.runs[:-2]
    for unit in present:
        (root / unit.run_relpath).mkdir(parents=True)
    failure = root / "pre-model-failures" / f"{manifest.runs[-2].run_id}.json"
    failure.parent.mkdir()
    failure_body = {
        "schema_version": "1",
        "run_id": manifest.runs[-2].run_id,
        "classification": "PRE_MODEL_FAILURE",
        "exception_type": "HarnessError",
        "message": "auth unavailable",
    }
    failure.write_bytes(
        comparison._canonical_bytes(
            {**failure_body, "failure_id": comparison._digest(failure_body)}
        )
    )
    monkeypatch.setattr(
        comparison,
        "_record_matches_unit",
        lambda _root, _manifest, unit: _record(unit),
    )
    report = comparison.build_report(root)
    assert report.collection_status == "PARTIAL"
    assert report.observed_runs == 4
    assert report.pre_model_failures == 1
    assert report.missing_runs == 1
    missing = next(
        item for item in report.records if item.acquisition_status == "MISSING"
    )
    assert missing.call_metrics_available is False
    assert missing.mcp_calls is None
    assert missing.reasoning_log_bytes is None


@pytest.mark.parametrize("accepted", [False, True])
def test_zero_and_all_success_rates(
    accepted: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "experiment"
    manifest = _manifest(root, repetitions=1)
    overrides = {
        (unit.task_id, unit.repetition, unit.condition): {"accepted": accepted}
        for unit in manifest.runs
    }
    _patch_records(monkeypatch, root, manifest, overrides)
    report = comparison.build_report(root)
    assert all(row.acceptance.value == float(accepted) for row in report.conditions)
    assert all(row.acceptance.wilson_low is not None for row in report.conditions)


def test_infrastructure_and_mathematical_failure_are_separate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "experiment"
    manifest = _manifest(root, repetitions=1)
    first, second = manifest.runs[:2]
    overrides = {
        (first.task_id, first.repetition, first.condition): {
            "accepted": None,
            "infrastructure": "INCOMPLETE",
        },
        (second.task_id, second.repetition, second.condition): {"accepted": False},
    }
    _patch_records(monkeypatch, root, manifest, overrides)
    report = comparison.build_report(root)
    by_id = {item.run_id: item for item in report.records}
    assert by_id[first.run_id].mathematical_failure is None
    assert by_id[second.run_id].mathematical_failure is True


def test_audit_repair_and_regression_are_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "experiment"
    manifest = _manifest(root)
    c_units = [item for item in manifest.runs if item.condition == "C"]
    overrides = {
        (c_units[0].task_id, c_units[0].repetition, "C"): {"audit": "REPAIR"},
        (c_units[1].task_id, c_units[1].repetition, "C"): {
            "audit": "REGRESSION",
            "accepted": False,
        },
    }
    _patch_records(monkeypatch, root, manifest, overrides)
    report = comparison.build_report(root)
    c_summary = next(item for item in report.conditions if item.condition == "C")
    assert c_summary.audit_classifications.repair == 1
    assert c_summary.audit_classifications.regression == 1


def test_exact_paired_counts_and_missing_pair() -> None:
    records = []
    outcomes = [(False, True), (False, True), (True, False), (True, True)]
    for repetition, (left, right) in enumerate(outcomes):
        for condition, accepted in (("A", left), ("B", right), ("C", True)):
            records.append(
                SimpleNamespace(
                    task_id="task",
                    repetition=repetition,
                    condition=condition,
                    accepted=accepted,
                )
            )
    pair = comparison._paired(records, "A", "B")
    assert pair.left_only_accepted == 1
    assert pair.right_only_accepted == 2
    assert pair.discordant_pairs == 3
    assert pair.exact_p_value == 1.0
    records[0].accepted = None
    missing = comparison._paired(records, "A", "B")
    assert missing.missing_pairs == 1
    assert missing.complete_binary_pairs == 3


def test_unavailable_tokens_and_cost_are_not_imputed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "experiment"
    manifest = _manifest(root, repetitions=1)
    unit = manifest.runs[0]
    _patch_records(
        monkeypatch,
        root,
        manifest,
        {(unit.task_id, unit.repetition, unit.condition): {"tokens": None}},
    )
    report = comparison.build_report(root)
    row = next(item for item in report.conditions if item.condition == unit.condition)
    assert row.tokens.availability == "UNAVAILABLE"
    assert row.tokens.total is None
    assert row.cost.availability == "UNAVAILABLE"
    assert row.cost.per_accepted is None
    assert row.reasoning_logs.token_overhead.availability == "UNAVAILABLE"
    assert row.reasoning_logs.token_overhead.total is None


def test_artifact_corruption_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "run"
    root.mkdir()
    manifest = _manifest(tmp_path / "experiment", repetitions=1)
    unit = manifest.runs[0]
    monkeypatch.setattr(
        comparison.trajectory,
        "analyze_run",
        lambda _root: (_ for _ in ()).throw(
            comparison.trajectory.TrajectoryTelemetryError("digest mismatch")
        ),
    )
    with pytest.raises(comparison.ComparisonError, match="corrupt run artifacts"):
        comparison._record_matches_unit(root, manifest, unit)


@pytest.mark.parametrize("field", ["model", "task_id", "source_revision"])
def test_mixed_run_identity_is_rejected(
    field: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "run"
    root.mkdir()
    manifest = _manifest(tmp_path / "experiment", repetitions=1)
    unit = manifest.runs[0]
    record = _record(unit)
    setattr(record, field, "wrong")
    monkeypatch.setattr(comparison.trajectory, "analyze_run", lambda _root: [record])
    with pytest.raises(comparison.ComparisonError, match="run identity drift"):
        comparison._record_matches_unit(root, manifest, unit)


@pytest.mark.parametrize("drift", ["prompt", "task_digest"])
def test_prompt_or_task_digest_substitution_is_rejected(
    drift: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "run"
    root.mkdir()
    manifest = _manifest(tmp_path / "experiment", repetitions=1)
    unit = manifest.runs[0]
    monkeypatch.setattr(
        comparison.trajectory, "analyze_run", lambda _root: [_record(unit)]
    )
    task = next(item for item in manifest.tasks if item.task_id == unit.task_id)
    snapshot = {
        "prompts": {
            "primary_digest": manifest.prompt_digests.primary,
            "audit_digest": manifest.prompt_digests.audit,
        },
        "task": {"harbor_digest": task.harbor_digest},
    }
    if drift == "prompt":
        snapshot["prompts"]["primary_digest"] = "sha256:" + "9" * 64
    else:
        snapshot["task"]["harbor_digest"] = "sha256:" + "9" * 64
    (root / "runtime-snapshot.json").write_text(json.dumps(snapshot))
    with pytest.raises(comparison.ComparisonError, match=r"binding drift|digest drift"):
        comparison._record_matches_unit(root, manifest, unit)


def test_schemas_accept_model_examples() -> None:
    Draft202012Validator.check_schema(comparison.ExperimentManifest.model_json_schema())
    Draft202012Validator.check_schema(comparison.ComparisonReport.model_json_schema())


def test_manifest_schema_closes_typed_runtime_bindings() -> None:
    schema = comparison.ExperimentManifest.model_json_schema()
    required = set(schema["required"])
    assert "contract_versions" in required
    for name in (
        "ConditionBindings",
        "ModelBinding",
        "CodexBinding",
        "AuthBinding",
        "BudgetBindings",
        "McpBinding",
        "RuntimeBinding",
    ):
        assert schema["$defs"][name]["additionalProperties"] is False


def test_legacy_pilot_manifest_versions_are_inferred_after_digest_replay(
    tmp_path: Path,
) -> None:
    root = tmp_path / "experiment"
    manifest = _manifest(root, repetitions=1)
    payload = manifest.model_dump(mode="json")
    payload.pop("contract_versions")
    payload["budgets"].pop("condition_runs")
    payload.pop("experiment_id")
    payload["experiment_id"] = comparison._digest(payload)
    (root / "experiment-manifest.json").write_bytes(
        comparison._canonical_bytes(payload)
    )
    loaded = comparison.load_manifest(root)
    assert loaded.contract_versions.comparison_report == "1"
    assert loaded.budgets.condition_runs.value == 6


def test_condition_run_budget_drift_is_rejected(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "experiment", repetitions=1)
    payload = manifest.model_dump(mode="json")
    payload["budgets"]["condition_runs"]["value"] = 7
    with pytest.raises(ValidationError, match="budget disagrees"):
        comparison.ExperimentManifest.model_validate(payload)


def test_report_exposes_exact_calls_logs_and_complete_markdown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "experiment"
    manifest = _manifest(root, repetitions=1)
    _patch_records(monkeypatch, root, manifest)
    report = comparison.build_report(root)
    treatment = next(item for item in report.conditions if item.condition == "B")
    assert treatment.capability_use.exact_run_count == 2
    assert treatment.capability_use.shell_calls == 2
    assert treatment.capability_use.invocation_calls == 2
    assert treatment.reasoning_logs.total_entries == 8
    assert treatment.reasoning_logs.total_bytes == 512
    markdown = comparison.render_report(report)
    for marker in (
        "95% Wilson",
        "## Clean-room score means",
        "## Workflow telemetry",
        "Audit classifications and reasoning compliance",
        "Discordant",
        "## Repeated-run reliability",
        "exact McNemar",
    ):
        assert marker in markdown


def test_report_digest_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "experiment"
    manifest = _manifest(root, repetitions=1)
    _patch_records(monkeypatch, root, manifest)
    payload = comparison.build_report(root).model_dump(mode="json")
    payload["records"][0]["reward"] = 0.5
    with pytest.raises(ValidationError, match="report digest drift"):
        comparison.ComparisonReport.model_validate(payload)


def test_emit_refuses_existing_markdown_without_partial_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = tmp_path / "report.json"
    markdown = tmp_path / "report.md"
    markdown.write_text("existing")
    monkeypatch.setattr(
        comparison,
        "build_report",
        lambda _root: (_ for _ in ()).throw(AssertionError("must not build")),
    )
    with pytest.raises(comparison.ComparisonError, match="refusing to overwrite"):
        comparison.emit_report(tmp_path, output, markdown)
    assert not output.exists()
