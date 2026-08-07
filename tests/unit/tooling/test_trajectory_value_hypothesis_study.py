from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import cast

import pytest
from benchmarks.tooling.command_runner import ToolCommandStatus
from benchmarks.tooling.trajectory_value_calibration import (
    CalibrationCandidate,
    HarborTaskContract,
    _task_contract,
)
from benchmarks.tooling.trajectory_value_hypothesis_study import (
    TrajectoryValueHypothesisStudySpec,
    _codex_arguments,
    _verify_terminal,
    analyze_comparison,
    load_hypothesis_spec,
    run_study,
)
from benchmarks.tooling.trajectory_value_mixed_contract import FrozenMixedTask
from pydantic import ValidationError
from tests.unit.tooling.test_trajectory_value_abstraction import _controlled_corpus

from jacobian.eval.trajectory_state import TerminalAcceptance
from jacobian.eval.trajectory_value_abstraction import evaluate_semantic_trajectories

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT / "benchmarks/config/trajectory-value-hypothesis-study-v1.json"
SCHEMA = (
    ROOT
    / "docs/reference/evaluations/schemas/trajectory-value-hypothesis-study-v1.schema.json"
)


def _value() -> dict[str, object]:
    return cast(dict[str, object], json.loads(SPEC.read_text(encoding="utf-8")))


def test_preregistration_binds_frozen_24_rollout_mixed_study() -> None:
    spec, validated = load_hypothesis_spec(SPEC)
    assert spec.analysis_id == "trajectory-value-hypothesis-codex-v1"
    assert [task.task_id for task in validated.contract.tasks] == [
        "graph-artifact-composition",
        "apollonius-gap-repair",
        "rp2-homology-lattice",
    ]
    assert len(validated.contract.tasks) * validated.contract.repetitions_per_task == 24
    assert spec.h3.threshold_tuned_on_main_labels is False
    assert spec.scorer_intervention is False
    assert spec.learned_components is False


def test_preregistration_is_closed_and_estimator_order_is_fixed() -> None:
    value = _value()
    value["post_label_threshold"] = -0.1
    with pytest.raises(ValidationError):
        TrajectoryValueHypothesisStudySpec.model_validate(value)

    value = _value()
    h1 = cast(dict[str, object], value["h1"])
    estimators = cast(list[str], h1["typed_estimators"])
    estimators.reverse()
    with pytest.raises(ValidationError, match="preregistered order"):
        TrajectoryValueHypothesisStudySpec.model_validate(value)


def test_mixed_study_digest_substitution_fails_closed(tmp_path: Path) -> None:
    value = _value()
    reference = cast(dict[str, object], value["mixed_study"])
    reference["file_digest"] = "sha256:" + "0" * 64
    altered = TrajectoryValueHypothesisStudySpec.model_validate(value)
    temporary = tmp_path / "invalid-hypothesis-study.json"
    temporary.write_text(altered.model_dump_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="file digest drift"):
        load_hypothesis_spec(temporary)


def test_external_execution_requires_explicit_opt_in(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="without --execute"):
        run_study(SPEC, tmp_path / "result", execute=False)


def test_codex_command_freezes_model_isolation_and_no_web_or_retry() -> None:
    _spec, validated = load_hypothesis_spec(SPEC)
    arguments = _codex_arguments(
        workspace=ROOT,
        mixed=validated.contract,
        mcp_url="http://127.0.0.1:8123/mcp",
        prompt=validated.contract.agent_instructions,
    )
    joined = " ".join(arguments)
    assert "gpt-5.4-mini" in arguments
    assert 'model_reasoning_effort="medium"' in arguments
    assert "--ephemeral" in arguments
    assert "--ignore-user-config" in arguments
    assert "--ignore-rules" in arguments
    assert "OPENAI_API_KEY" not in joined
    assert "retry" not in joined.lower()


def _first_task() -> tuple[FrozenMixedTask, HarborTaskContract]:
    _spec, validated = load_hypothesis_spec(SPEC)
    task = validated.contract.tasks[0]
    contract = _task_contract(
        CalibrationCandidate(
            dataset_id=task.dataset_id,
            task_id=task.task_id,
            task_family=task.task_family,
            calibration_tags=task.calibration_tags,
        )
    )
    return task, contract


def _workspace(tmp_path: Path, contract: HarborTaskContract) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for name, relative in {
        "instruction.md": Path("instruction.md"),
        "input.json": Path("environment/input.json"),
        "submission_schema.json": Path("environment/submission_schema.json"),
    }.items():
        shutil.copyfile(contract.path / relative, workspace / name)
    (workspace / "submission.json").write_text("{}\n", encoding="utf-8")
    return workspace


def test_rejected_reward_remains_an_exact_bound_negative_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task, contract = _first_task()
    workspace = _workspace(tmp_path, contract)
    monkeypatch.setattr(
        "benchmarks.tooling.trajectory_value_hypothesis_study.run_verifier_in_child",
        lambda **_kwargs: {
            "reward": 0.0,
            "correctness": 1.0,
            "evidence_validity": 0.0,
            "false_certification": False,
        },
    )
    outcome, terminal = _verify_terminal(
        task=task,
        contract=contract,
        workspace=workspace,
        run_dir=tmp_path / "run",
        command_status=ToolCommandStatus.EXITED,
        exit_code=0,
    )
    assert outcome["acceptance"] == "REJECTED"
    assert outcome["submission_evidence_valid"] is False
    assert outcome["artifact_binding_valid"] is True
    assert terminal.acceptance is TerminalAcceptance.REJECTED
    assert terminal.input_binding_valid is True
    assert terminal.artifact_binding_valid is True


def test_public_input_drift_is_inconclusive_and_verifier_is_not_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task, contract = _first_task()
    workspace = _workspace(tmp_path, contract)
    (workspace / "input.json").write_text("{}\n", encoding="utf-8")

    def forbidden(**_kwargs: object) -> None:
        raise AssertionError("verifier must not run after public input drift")

    monkeypatch.setattr(
        "benchmarks.tooling.trajectory_value_hypothesis_study.run_verifier_in_child",
        forbidden,
    )
    outcome, terminal = _verify_terminal(
        task=task,
        contract=contract,
        workspace=workspace,
        run_dir=tmp_path / "run",
        command_status=ToolCommandStatus.EXITED,
        exit_code=0,
    )
    assert outcome["reason"] == "PUBLIC_INPUT_DRIFT"
    assert terminal.acceptance is TerminalAcceptance.INCONCLUSIVE
    assert terminal.verifier_execution_status == "ERROR"


def test_controlled_comparison_exercises_preregistered_hypothesis_analysis() -> None:
    source = evaluate_semantic_trajectories(_controlled_corpus())
    value = _value()
    value["analysis_id"] = source.corpus_id
    spec = TrajectoryValueHypothesisStudySpec.model_validate(value)
    result = analyze_comparison(
        spec, source, run_count=len(source.source_corpus.trajectories)
    )
    assert result["mixed_terminal_outcomes"] is True
    assert result["h1"]["h1_directionally_supported"] is True
    assert result["h2"]["mixed_outcome_compatible_pair_count"] > 0
    assert result["h2"]["h2_directionally_supported"] is True
    assert result["h3"]["threshold_tuned_on_main_labels"] is False
    assert result["scorer_intervention"] is False
    assert result["causal_claim_authorized"] is False


def test_schema_matches_authoritative_preregistration_contract() -> None:
    assert json.loads(SCHEMA.read_text(encoding="utf-8")) == (
        TrajectoryValueHypothesisStudySpec.model_json_schema()
    )
