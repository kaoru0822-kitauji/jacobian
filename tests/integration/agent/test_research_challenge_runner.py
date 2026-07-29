from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from benchmarks import research_challenge as runner


def test_research_challenge_is_plan_only_and_no_retrieval(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    def unexpected_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("plan mode started a model evaluation")

    monkeypatch.setitem(runner.main.__globals__, "_run_case", unexpected_run)

    assert runner.main(["--challenge", "jcb-postdoc-014"]) == 0

    plan = json.loads(capsys.readouterr().out)
    assert plan["mode"] == "plan"
    assert plan["evaluation_class"] == "PUBLIC_ANSWER_VISIBLE_DIAGNOSTIC"
    assert plan["scored"] is False
    assert plan["execution_requested"] is False
    assert plan["model_run_count"] == 1
    assert plan["cases"][0]["challenge_id"] == "jcb-postdoc-014"
    assert plan["capability_policy_profile"] == ("COMPUTE_VERIFY_NO_RETRIEVAL")
    assert plan["retrieval_capabilities_available"] is False


def test_research_challenge_codex_command_profiles_local_mcp(
    tmp_path: Path,
) -> None:
    command = runner._codex_command(
        codex_command="codex",
        workspace=tmp_path / "workspace",
        final_path=tmp_path / "final.md",
        state_dir=tmp_path / "state",
        model="gpt-5.6",
        reasoning_effort="xhigh",
    )

    rendered = " ".join(command)
    assert "--ignore-user-config" in rendered
    assert "jacobian-mcp" in rendered
    server_argument = next(
        item for item in command if item.startswith("mcp_servers.jacobian_local.args=")
    )
    server_args = json.loads(server_argument.split("=", 1)[1])
    assert server_args[-2:] == [
        "--capability-policy-profile",
        "COMPUTE_VERIFY_NO_RETRIEVAL",
    ]


def test_research_challenge_sampling_is_seeded() -> None:
    suite = runner.load_suite(runner.DEFAULT_SUITE)

    first = runner.select_cases(
        suite,
        challenge_ids=[],
        sample_size=3,
        seed=17,
    )
    second = runner.select_cases(
        suite,
        challenge_ids=[],
        sample_size=3,
        seed=17,
    )

    assert [case["challenge_id"] for case in first] == [
        case["challenge_id"] for case in second
    ]


def test_research_challenge_passes_published_prompt_unchanged(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    published_prompt = "Use Jacobian MCP exactly.\nKeep this newline.\n"
    observed: dict[str, object] = {}

    def fake_run(*_args: object, **kwargs: object) -> SimpleNamespace:
        observed["input"] = kwargs["input"]
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner._run_case(
        {
            "challenge_id": "jcb-postdoc-999",
            "prompt": published_prompt,
        },
        repetition=1,
        run_root=tmp_path,
        codex_command="codex",
        model="gpt-5.6",
        reasoning_effort="xhigh",
        timeout_seconds=30,
    )

    assert observed["input"] == published_prompt
    assert result["prompt_passed_unchanged"] is True
    assert result["termination_reason"] == "COMPLETED"


def test_research_challenge_requires_explicit_model_run_budget() -> None:
    with pytest.raises(SystemExit):
        runner.main(
            [
                "--challenge",
                "jcb-postdoc-014",
                "--execute",
            ]
        )
