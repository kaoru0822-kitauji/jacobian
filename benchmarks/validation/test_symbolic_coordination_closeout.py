from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from benchmarks.tooling import symbolic_coordination_closeout as closeout
from benchmarks.tooling import symbolic_coordination_codex as codex
from benchmarks.tooling import symbolic_coordination_feedback as feedback
from jsonschema import Draft202012Validator


def test_closeout_freezes_exact_six_by_four_matrix() -> None:
    runs = closeout.counterbalanced_runs(closeout.DEFAULT_TASKS)
    assert len(runs) == 24
    assert [item.sequence for item in runs] == list(range(24))
    assert len({item.run_id for item in runs}) == 24
    for task_id in closeout.DEFAULT_TASKS:
        block = [item for item in runs if item.task_id == task_id]
        assert {item.condition for item in block} == {"A", "B", "C", "D"}
        assert sorted(item.block_position for item in block) == [0, 1, 2, 3]
    assert (
        len(
            {
                tuple(item.condition for item in runs[offset : offset + 4])
                for offset in range(0, 24, 4)
            }
        )
        == 6
    )


def test_default_representatives_cover_each_public_family_once() -> None:
    families = []
    for task_id in closeout.DEFAULT_TASKS:
        value = json.loads(
            (codex.DATASET / task_id / "environment" / "input.json").read_text(
                encoding="utf-8"
            )
        )
        families.append(value["family"])
    assert frozenset(families) == closeout.EXPECTED_FAMILIES
    assert len(families) == len(set(families)) == 6


def test_pr5_does_not_change_frozen_a_b_c_prompt_bytes() -> None:
    assert codex._digest_bytes(codex.PRIMARY_PROMPT.encode()) == (
        "sha256:be92db467ac1c477f9b80ec65a02583952758a58a6ce9f55a22e6da133874e70"
    )
    assert codex._digest_bytes(codex.AUDIT_PROMPT.encode()) == (
        "sha256:0e66b7b2bf87ecc3e60c22027b2c9ae0349f57a3b7c8df8db21779e08f7d45a5"
    )
    assert feedback.FEEDBACK_PROMPT not in {codex.PRIMARY_PROMPT, codex.AUDIT_PROMPT}


def test_committed_closeout_schemas_match_models() -> None:
    schema_root = Path(__file__).parents[1] / "schemas"
    pairs = (
        (
            "symbolic-coordination-closeout-experiment-v1.schema.json",
            closeout.CloseoutManifest.model_json_schema(),
        ),
        (
            "symbolic-coordination-closeout-report-v1.schema.json",
            closeout.CloseoutReport.model_json_schema(),
        ),
        (
            "symbolic-coordination-verifier-feedback-v1.schema.json",
            feedback.VerifierFeedback.model_json_schema(),
        ),
    )
    for name, expected in pairs:
        actual = json.loads((schema_root / name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(actual)
        assert actual == expected


def test_feedback_schema_has_no_free_form_diagnostic_or_message() -> None:
    schema = feedback.VerifierFeedback.model_json_schema()
    diagnostic = schema["$defs"]["FeedbackDiagnostic"]
    assert diagnostic["additionalProperties"] is False
    assert set(diagnostic["properties"]) == {"code", "dimension"}
    assert "message" not in json.dumps(schema).lower()


def test_resume_never_reexecutes_an_existing_wrong_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unit = closeout.counterbalanced_runs(closeout.DEFAULT_TASKS)[0]
    run_root = tmp_path / unit.run_relpath
    run_root.mkdir(parents=True)
    manifest = SimpleNamespace(runs=[unit])
    record = SimpleNamespace(infrastructure_status="COMPLETE")
    monkeypatch.setattr(closeout, "load_manifest", lambda _root: manifest)
    monkeypatch.setattr(closeout, "_validate_current_contract", lambda _manifest: None)
    monkeypatch.setattr(
        closeout, "_record_matches_unit", lambda _root, _manifest, _unit: record
    )
    monkeypatch.setattr(
        codex,
        "execute",
        lambda **_kwargs: pytest.fail("existing mathematical result was rerun"),
    )
    result = closeout.run_experiment(tmp_path, source={}, max_model_executions=None)
    assert result == {
        "observed": 1,
        "executed": 0,
        "infrastructure_incomplete": 0,
    }


def test_explicit_retry_is_limited_to_infrastructure_incomplete_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unit = closeout.counterbalanced_runs(closeout.DEFAULT_TASKS)[0]
    run_root = tmp_path / unit.run_relpath
    run_root.mkdir(parents=True)
    manifest = SimpleNamespace(runs=[unit])
    records = iter(
        [
            SimpleNamespace(infrastructure_status="INCOMPLETE"),
            SimpleNamespace(infrastructure_status="COMPLETE"),
        ]
    )
    monkeypatch.setattr(closeout, "load_manifest", lambda _root: manifest)
    monkeypatch.setattr(closeout, "_validate_current_contract", lambda _manifest: None)
    monkeypatch.setattr(
        closeout, "_record_matches_unit", lambda _root, _manifest, _unit: next(records)
    )

    def _execute(**kwargs: object) -> None:
        Path(kwargs["output_path"]).mkdir(parents=True)  # type: ignore[arg-type]

    monkeypatch.setattr(codex, "execute", _execute)
    result = closeout.run_experiment(
        tmp_path,
        source={},
        max_model_executions=None,
        retry_infrastructure=True,
    )
    assert result["executed"] == result["observed"] == 1
    assert (tmp_path / "retry-history" / unit.run_id / "run-attempt-001").is_dir()


def test_exact_closeout_paired_tables_cover_required_contrasts() -> None:
    records = []
    for index, task_id in enumerate(closeout.DEFAULT_TASKS):
        for condition in closeout.CONDITIONS:
            accepted = condition == "D" and index % 2 == 0
            records.append(
                closeout.CloseoutRunObservation.model_construct(
                    task_id=task_id,
                    condition=condition,
                    accepted=accepted,
                )
            )
    expected = {
        ("A", "B"): "A_TO_B",
        ("B", "C"): "B_TO_C",
        ("B", "D"): "B_TO_D",
        ("C", "D"): "C_TO_D",
    }
    for pair, name in expected.items():
        result = closeout._paired(records, *pair)
        assert result.contrast == name
        assert result.planned_pairs == result.complete_binary_pairs == 6
        assert result.missing_pairs == 0
