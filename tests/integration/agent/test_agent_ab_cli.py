from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from benchmarks import agent_ab as benchmark
from tests.helpers.provider_runtime import (
    PINNED_MATHLIB_RUNTIME_UNAVAILABLE_REASON,
    pinned_mathlib_runtime_available,
)
from tests.integration.agent._agent_ab_support import _write_private_case

from jacobian.contracts.capabilities import (
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.runtime import CheckerAuthorityMode, create_runtime


def test_agent_eval_is_plan_only_without_explicit_execute(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    main = benchmark.main

    def unexpected_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("plan mode started a model evaluation")

    monkeypatch.setitem(main.__globals__, "_run_condition", unexpected_run)

    assert main(["--case", "ERDOS-STRAUS-AB-001"]) == 0

    plan = json.loads(capsys.readouterr().out)
    assert plan["mode"] == "plan"
    assert plan["execution_requested"] is False
    assert plan["model_run_count"] == 2
    assert plan["maximum_model_wall_seconds"] == 1200
    assert plan["cases"][0]["capability_policy_profiles"] == {
        "control": None,
        "treatment": "COMPUTE_VERIFY_NO_RETRIEVAL",
    }


def test_agent_eval_requires_explicit_case_selection() -> None:
    main = benchmark.main

    with pytest.raises(SystemExit):
        main([])


def test_agent_eval_plan_accepts_xhigh_reasoning(
    capsys: Any,
) -> None:
    main = benchmark.main

    assert (
        main(
            [
                "--case",
                "ERDOS-STRAUS-AB-001",
                "--reasoning-effort",
                "xhigh",
            ]
        )
        == 0
    )

    plan = json.loads(capsys.readouterr().out)
    assert plan["reasoning_effort"] == "xhigh"


def test_agent_eval_requires_sufficient_manual_run_budget(tmp_path: Path) -> None:
    main = benchmark.main
    case_path = _write_private_case(tmp_path)

    with pytest.raises(SystemExit):
        main(
            [
                "--case-file",
                str(case_path),
                "--execute",
                "--max-model-runs",
                "3",
            ]
        )


def test_agent_eval_plan_counts_each_lean_capability_condition(
    tmp_path: Path,
    capsys: Any,
) -> None:
    main = benchmark.main
    case_path = _write_private_case(tmp_path)

    assert (
        main(
            [
                "--case-file",
                str(case_path),
                "--repetitions",
                "2",
            ]
        )
        == 0
    )

    plan = json.loads(capsys.readouterr().out)
    assert plan["model_run_count"] == 8
    assert plan["cases"][0]["conditions"] == [
        "baseline",
        "tactic",
        "retrieval",
        "combined",
    ]


@pytest.mark.lean_runtime
@pytest.mark.skipif(
    not pinned_mathlib_runtime_available(),
    reason=PINNED_MATHLIB_RUNTIME_UNAVAILABLE_REASON,
)
@pytest.mark.usefixtures("initialized_runtime_store_with_references")
def test_ab_lean_control_ablation_removes_only_declaration_discovery(
    tmp_path: Path,
) -> None:
    runtime = create_runtime(
        tmp_path,
        checker_authority=CheckerAuthorityMode.INSTALL_BUNDLED,
        capability_exclusions=frozenset(
            {
                "lean.declaration.search",
                "lean.declaration.inspect",
            }
        ),
    )

    lean_ids = {
        descriptor.capability_id
        for descriptor in runtime.core.capabilities.catalog().capabilities
        if descriptor.capability_id.startswith("lean.")
    }

    assert lean_ids == {
        "lean.check",
        "lean.declaration.dependencies",
        "lean.proof_edit.validate",
        "lean.proof_state.apply_tactic",
        "lean.retrieve.premises",
        "lean.statement.compare",
        "lean.statement.propose",
    }
    excluded = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="lean.declaration.search",
            mode=CapabilityMode.EXPLORE,
            input={
                "environment": "MATHLIB",
                "name_contains": "revzip",
                "result_limit": 1,
            },
        )
    )
    assert excluded.execution.status.value == "ERROR"
    assert excluded.diagnostics[0].code == "UNKNOWN_CAPABILITY"


def test_ab_lean_codex_command_uses_same_mcp_with_control_ablation(
    tmp_path: Path,
) -> None:
    codex_command = benchmark._codex_command
    control = codex_command(
        codex_command="codex",
        condition="control",
        workspace=tmp_path / "workspace",
        report_path=tmp_path / "report.json",
        state_dir=tmp_path / "state",
        model="gpt-5.6",
        reasoning_effort="high",
        task_type="lean_declaration",
    )
    treatment = codex_command(
        codex_command="codex",
        condition="treatment",
        workspace=tmp_path / "workspace",
        report_path=tmp_path / "report.json",
        state_dir=tmp_path / "state",
        model="gpt-5.6",
        reasoning_effort="high",
        task_type="lean_declaration",
    )

    assert "agent_ab_mcp.py" in " ".join(control)
    assert "agent_ab_mcp.py" in " ".join(treatment)
    assert " ".join(control).count("--exclude-capability") == 2
    assert "--exclude-capability" not in " ".join(treatment)
    for command in (control, treatment):
        server_argument = next(
            item
            for item in command
            if item.startswith("mcp_servers.jacobian_local.args=")
        )
        server_args = json.loads(server_argument.split("=", 1)[1])
        assert server_args[-2:] == ["--capability-policy-profile", "DEFAULT"]


def test_ab_non_retrieval_treatment_starts_profiled_mcp(
    tmp_path: Path,
) -> None:
    command = benchmark._codex_command(
        codex_command="codex",
        condition="treatment",
        workspace=tmp_path / "workspace",
        report_path=tmp_path / "report.json",
        state_dir=tmp_path / "state",
        model="gpt-5.6",
        reasoning_effort="xhigh",
        task_type="graph",
    )

    assert "jacobian-mcp" in " ".join(command)
    server_argument = next(
        item for item in command if item.startswith("mcp_servers.jacobian_local.args=")
    )
    server_args = json.loads(server_argument.split("=", 1)[1])
    assert server_args[-2:] == [
        "--capability-policy-profile",
        "COMPUTE_VERIFY_NO_RETRIEVAL",
    ]


def test_ab_distance_composition_uses_same_mcp_with_targeted_ablation(
    tmp_path: Path,
    capsys: Any,
) -> None:
    assert (
        benchmark.main(
            [
                "--case",
                "GRAPH-DISTANCE-COMPOSITION-AB-001",
                "--repetitions",
                "3",
            ]
        )
        == 0
    )
    plan = json.loads(capsys.readouterr().out)
    case_plan = plan["cases"][0]
    assert plan["model_run_count"] == 6
    assert case_plan["capability_exclusions"] == {
        "control": sorted(benchmark.DISTANCE_COMPOSITION_CAPABILITY_IDS),
        "treatment": [],
    }
    assert case_plan["capability_policy_profiles"] == {
        "control": "COMPUTE_VERIFY_NO_RETRIEVAL",
        "treatment": "COMPUTE_VERIFY_NO_RETRIEVAL",
    }

    commands = {}
    for condition in ("control", "treatment"):
        commands[condition] = benchmark._codex_command(
            codex_command="codex",
            condition=condition,
            workspace=tmp_path / condition / "workspace",
            report_path=tmp_path / condition / "report.json",
            state_dir=tmp_path / condition / "state",
            model="gpt-5.6",
            reasoning_effort="high",
            task_type="graph_distance_composition",
            excluded_capability_ids=(
                tuple(benchmark.DISTANCE_COMPOSITION_CAPABILITY_IDS)
                if condition == "control"
                else ()
            ),
            capability_policy_profile="COMPUTE_VERIFY_NO_RETRIEVAL",
        )
    assert "agent_ab_mcp.py" in " ".join(commands["control"])
    assert "agent_ab_mcp.py" in " ".join(commands["treatment"])
    assert " ".join(commands["control"]).count("--exclude-capability") == 2
    assert "--exclude-capability" not in " ".join(commands["treatment"])
