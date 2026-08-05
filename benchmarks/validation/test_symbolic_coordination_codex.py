"""Focused fail-closed tests for the host-local Codex observation runner."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any

import pytest
from benchmarks.tooling import symbolic_coordination_codex as sc
from benchmarks.tooling.command_runner import ToolCommandResult, ToolCommandStatus


def _task_contract() -> sc.TaskContract:
    task_id = "symbolic-coordination-near-miss-01"
    task = sc.DATASET / task_id
    paths = {
        "input.json": task / "environment/input.json",
        "instruction.md": task / "instruction.md",
        "submission_schema.json": task / "environment/submission_schema.json",
    }
    return sc.TaskContract(
        task_id=task_id,
        path=task,
        harbor_digest="sha256:" + "a" * 64,
        public_hashes={name: sc._digest_file(path) for name, path in paths.items()},
        verifier_hashes={
            "public_contract.json": "sha256:" + "b" * 64,
            "verifier.py": "sha256:" + "c" * 64,
            "verifier_support.py": "sha256:" + "d" * 64,
        },
    )


def _preflight(tmp_path: Path) -> sc.Preflight:
    codex = tmp_path / "codex"
    mcp = tmp_path / "jacobian-mcp"
    auth = tmp_path / "auth.json"
    for path in (codex, mcp, auth):
        path.write_text(path.name, encoding="utf-8")
    codex.chmod(0o700)
    mcp.chmod(0o700)
    model = {
        "slug": sc.DEFAULT_MODEL,
        "display_name": "GPT-5.3-Codex-Spark",
        "description": "Ultra-fast coding model.",
        "priority": 26,
        "visibility": "list",
        "supported_in_api": False,
        "shell_type": "shell_command",
        "context_window": 128_000,
        "max_context_window": 128_000,
        "supports_parallel_tool_calls": True,
        "supported_reasoning_levels": ["low", "medium"],
        "tool_mode": None,
        "selection_basis": (
            "minimum_context_window_among_listed_shell_models_supporting_"
            "medium_reasoning"
        ),
    }
    return sc.Preflight(
        codex=codex,
        mcp=mcp,
        auth_file=auth,
        codex_version="0.146.0",
        source_revision="1" * 40,
        branch="bench/test",
        selected_model=model,
        selected_model_digest=sc._digest_json(model),
        report={"status": "READY"},
    )


def _snapshot(tmp_path: Path) -> tuple[dict[str, Any], str]:
    snapshot = {"snapshot_id": "sha256:" + "f" * 64}
    path = tmp_path / "runtime-snapshot.json"
    sc._write_json(path, snapshot)
    return snapshot, sc._digest_file(path)


def _success_result() -> ToolCommandResult:
    return ToolCommandResult(
        status=ToolCommandStatus.EXITED,
        exit_code=0,
        stdout=b'{"type":"turn.completed","usage":{"total_tokens":10}}\n',
        stderr=b"",
    )


def _telemetry() -> dict[str, Any]:
    return {
        "usage": {"total_tokens": 10},
        "mcp_calls": [],
        "shell_calls": [],
        "capability_ids": [],
        "observed_models": [],
        "terminal_failures": [],
        "web_search_count": 0,
    }


def test_workspace_starts_with_only_public_contract_files(tmp_path: Path) -> None:
    workspace = sc.prepare_workspace(tmp_path / "A", _task_contract())

    assert {path.name for path in workspace.iterdir()} == {
        "evidence",
        "input.json",
        "instruction.md",
        "submission_schema.json",
    }
    assert not any(
        forbidden in {part.lower() for part in path.relative_to(workspace).parts}
        for path in workspace.rglob("*")
        for forbidden in sc.FORBIDDEN_WORKSPACE_NAMES
    )


def test_workspace_rejects_hidden_material_and_symlinks(tmp_path: Path) -> None:
    workspace = sc.prepare_workspace(tmp_path / "A", _task_contract())
    (workspace / "solution").mkdir()

    with pytest.raises(sc.HarnessError, match="forbidden solution"):
        sc.assert_workspace_safe(
            workspace, expected_hashes=_task_contract().public_hashes
        )

    (workspace / "solution").rmdir()
    outside = tmp_path / "outside"
    outside.write_text("secret", encoding="utf-8")
    (workspace / "leak").symlink_to(outside)
    with pytest.raises(sc.HarnessError, match="symlink"):
        sc.assert_workspace_safe(
            workspace, expected_hashes=_task_contract().public_hashes
        )


def test_workspace_rejects_runtime_input_drift(tmp_path: Path) -> None:
    task = _task_contract()
    workspace = sc.prepare_workspace(tmp_path / "A", task)
    (workspace / "input.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(sc.HarnessError, match="task file drifted"):
        sc.assert_workspace_safe(workspace, expected_hashes=task.public_hashes)


def test_codex_arguments_bind_isolation_and_condition_mcp(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    state = tmp_path / "state"
    workspace.mkdir()
    state.mkdir()

    control = sc.codex_arguments(workspace=workspace, mcp=None, state=None)
    treatment = sc.codex_arguments(
        workspace=workspace, mcp=tmp_path / "jacobian-mcp", state=state
    )

    assert "--json" in control
    assert "--ephemeral" in control
    assert "--ignore-user-config" in control
    assert 'web_search="disabled"' in control
    assert "mcp_servers.jacobian.command" not in " ".join(control)
    joined = " ".join(treatment)
    assert "mcp_servers.jacobian.required=true" in joined
    assert "COMPUTE_VERIFY_NO_RETRIEVAL" in joined
    assert "--reasoning-log-mode" in joined
    assert "required" in joined
    assert "audit" not in joined.lower()


def test_preflight_rejects_api_or_model_environment_before_commands() -> None:
    for name in sc.FORBIDDEN_ENVIRONMENT:
        with pytest.raises(sc.HarnessError, match=name):
            sc.preflight({name: "present"})


def test_auth_contract_is_independent_of_unrelated_doctor_status(
    tmp_path: Path,
) -> None:
    auth_file = tmp_path / "auth.json"
    auth_file.write_text("{}\n", encoding="utf-8")
    doctor = {
        "overallStatus": "error",
        "checks": {
            "auth.credentials": {
                "status": "ok",
                "details": {
                    "stored auth mode": "chatgpt",
                    "stored ChatGPT tokens": "true",
                    "stored API key": "false",
                    "auth storage mode": "File",
                },
            }
        },
    }

    assert sc._resolve_auth_file({"CODEX_HOME": str(tmp_path)}, doctor) == auth_file

    doctor["checks"]["auth.credentials"]["status"] = "error"
    with pytest.raises(sc.HarnessError, match="file-backed ChatGPT auth"):
        sc._resolve_auth_file({"CODEX_HOME": str(tmp_path)}, doctor)


def test_model_selection_requires_listed_tool_model_and_reasoning() -> None:
    catalog = {
        "models": [
            {
                "slug": sc.DEFAULT_MODEL,
                "visibility": "list",
                "shell_type": "shell_command",
                "context_window": 128_000,
                "supported_reasoning_levels": [{"effort": "medium"}],
            },
            {
                "slug": "larger-model",
                "visibility": "list",
                "shell_type": "shell_command",
                "context_window": 272_000,
                "supported_reasoning_levels": [{"effort": "medium"}],
            },
        ]
    }
    assert sc._selected_model(catalog)["slug"] == sc.DEFAULT_MODEL

    catalog["models"][0]["shell_type"] = "none"
    with pytest.raises(sc.HarnessError, match="shell"):
        sc._selected_model(catalog)

    catalog["models"][0]["shell_type"] = "shell_command"
    catalog["models"][1]["context_window"] = 64_000
    with pytest.raises(sc.HarnessError, match="lowest-context"):
        sc._selected_model(catalog)


def test_harbor_digest_accepts_native_and_prefixed_forms() -> None:
    raw = "a" * 64
    assert sc._validate_harbor_digest(raw) == raw
    assert sc._validate_harbor_digest("sha256:" + raw) == "sha256:" + raw
    with pytest.raises(sc.HarnessError, match="malformed"):
        sc._validate_harbor_digest("not-a-digest")


def test_jsonl_runtime_facts_detect_model_web_and_terminal_drift() -> None:
    raw = b"\n".join(
        (
            b'{"type":"thread.started","thread_id":"thread-1","model":"other"}',
            b'{"type":"item.completed","item":{"type":"web_search_call"}}',
            b'{"type":"turn.failed"}',
        )
    )
    facts = sc._jsonl_runtime_facts(raw)
    telemetry = {"usage": {"total_tokens": 1}, **facts}

    assert facts["thread_ids"] == ["thread-1"]
    assert sc._stage_failures(_success_result(), telemetry, label="primary") == [
        "primary:MODEL_DRIFT",
        "primary:TERMINAL_FAILURE_EVENT",
        "primary:WEB_SEARCH_USED",
    ]


def test_runtime_snapshot_is_read_only_and_binds_all_conditions(
    tmp_path: Path,
) -> None:
    task = _task_contract()
    preflight = _preflight(tmp_path)
    output = tmp_path / "output"
    output.mkdir()

    snapshot, digest = sc.freeze_snapshot(output, task, preflight)

    mode = stat.S_IMODE((output / "runtime-snapshot.json").stat().st_mode)
    assert mode == 0o444
    assert digest.startswith("sha256:")
    assert set(snapshot["conditions"]) == {"A", "B", "C"}
    assert snapshot["conditions"]["C"]["reasoning_log_mode"] == "REQUIRED"
    assert snapshot["conditions"]["C"]["audit_passes"] == 1
    assert snapshot["budgets"]["max_total_tokens_per_stage"] == 800_000
    assert snapshot["sampling"]["deterministic"] is False


def test_missing_submission_is_infrastructure_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    snapshot, digest = _snapshot(output)
    monkeypatch.setattr(sc, "_assert_global_invariants", lambda *args: None)
    monkeypatch.setattr(
        sc,
        "_run_codex_stage",
        lambda **kwargs: (_success_result(), _telemetry(), {}),
    )

    result = sc.run_condition(
        condition="A",
        output=output,
        task=_task_contract(),
        snapshot=snapshot,
        snapshot_digest=digest,
        preflight_result=_preflight(tmp_path),
        source={},
    )

    assert result["infrastructure_status"] == "INCOMPLETE"
    assert "primary:MISSING_OUTPUT" in result["infrastructure_failures"]
    assert result["verifier"] is None


def test_rejected_math_is_observation_not_infrastructure_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    snapshot, digest = _snapshot(output)
    monkeypatch.setattr(sc, "_assert_global_invariants", lambda *args: None)

    def fake_stage(**kwargs: Any) -> tuple[ToolCommandResult, dict[str, Any], dict]:
        workspace = kwargs["workspace"]
        (workspace / "submission.json").write_text("{}\n", encoding="utf-8")
        return _success_result(), _telemetry(), {}

    monkeypatch.setattr(sc, "_run_codex_stage", fake_stage)
    monkeypatch.setattr(
        sc,
        "_run_verification",
        lambda *args: {
            "execution_status": "COMPLETED",
            "mathematical_observation": "REJECTED",
            "reward": {"reward": 0.0},
        },
    )

    result = sc.run_condition(
        condition="A",
        output=output,
        task=_task_contract(),
        snapshot=snapshot,
        snapshot_digest=digest,
        preflight_result=_preflight(tmp_path),
        source={},
    )

    assert result["infrastructure_status"] == "COMPLETE"
    assert result["verifier"]["mathematical_observation"] == "REJECTED"


def test_condition_c_runs_one_primary_mcp_stage_and_one_non_mcp_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    snapshot, digest = _snapshot(output)
    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(sc, "_assert_global_invariants", lambda *args: None)
    monkeypatch.setattr(sc, "_export_reasoning_logs", lambda *args: {"runs": []})
    monkeypatch.setattr(
        sc,
        "_run_verification",
        lambda *args: {"execution_status": "COMPLETED", "reward": {"reward": 1.0}},
    )

    def fake_stage(**kwargs: Any) -> tuple[ToolCommandResult, dict[str, Any], dict]:
        label = kwargs["label"]
        workspace = kwargs["workspace"]
        calls.append((label, kwargs["mcp_state"] is not None))
        if label == "primary":
            (workspace / "submission.json").write_text('{"version":1}\n')
        else:
            (workspace / "submission.json").write_text('{"version":2}\n')
            report = {
                "audit_schema_version": "1",
                "status": "REVISED",
                "revision_applied": True,
                "checks": {
                    "schema": True,
                    "input_binding": True,
                    "scope": True,
                    "completeness": True,
                    "assurance": True,
                    "evidence_binding": True,
                    "mathematics": True,
                },
                "notes": "fixed",
            }
            sc._write_json(workspace / "audit-report.json", report)
        return _success_result(), _telemetry(), {}

    monkeypatch.setattr(sc, "_run_codex_stage", fake_stage)

    result = sc.run_condition(
        condition="C",
        output=output,
        task=_task_contract(),
        snapshot=snapshot,
        snapshot_digest=digest,
        preflight_result=_preflight(tmp_path),
        source={},
    )

    assert calls == [("primary", True), ("audit", False)]
    assert result["infrastructure_status"] == "COMPLETE"
    assert result["revision_applied"] is True


def test_condition_c_binds_revision_to_evidence_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    snapshot, digest = _snapshot(output)
    monkeypatch.setattr(sc, "_assert_global_invariants", lambda *args: None)
    monkeypatch.setattr(sc, "_export_reasoning_logs", lambda *args: {"runs": []})
    monkeypatch.setattr(
        sc,
        "_run_verification",
        lambda *args: {"execution_status": "COMPLETED", "reward": {"reward": 1.0}},
    )

    def fake_stage(**kwargs: Any) -> tuple[ToolCommandResult, dict[str, Any], dict]:
        label = kwargs["label"]
        workspace = kwargs["workspace"]
        if label == "primary":
            (workspace / "submission.json").write_text('{"version":1}\n')
            (workspace / "evidence/certificate.json").write_text('{"version":1}\n')
        else:
            (workspace / "evidence/certificate.json").write_text('{"version":2}\n')
            sc._write_json(
                workspace / "audit-report.json",
                {
                    "audit_schema_version": "1",
                    "status": "REVISED",
                    "revision_applied": True,
                    "checks": {
                        "schema": True,
                        "input_binding": True,
                        "scope": True,
                        "completeness": True,
                        "assurance": True,
                        "evidence_binding": True,
                        "mathematics": True,
                    },
                    "notes": "repaired evidence only",
                },
            )
        return _success_result(), _telemetry(), {}

    monkeypatch.setattr(sc, "_run_codex_stage", fake_stage)

    result = sc.run_condition(
        condition="C",
        output=output,
        task=_task_contract(),
        snapshot=snapshot,
        snapshot_digest=digest,
        preflight_result=_preflight(tmp_path),
        source={},
    )

    assert result["infrastructure_status"] == "COMPLETE"
    assert result["revision_applied"] is True


def test_verifier_copy_is_outside_model_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "condition/workspace"
    (workspace / "evidence").mkdir(parents=True)
    (workspace / "submission.json").write_text("{}\n", encoding="utf-8")
    (workspace / "evidence/certificate.json").write_text("{}\n", encoding="utf-8")

    app, logs = sc._verification_copy(tmp_path / "condition", workspace)

    assert app != workspace
    assert not app.is_relative_to(workspace)
    assert json.loads((app / "submission.json").read_text()) == {}
    assert logs.is_dir()
