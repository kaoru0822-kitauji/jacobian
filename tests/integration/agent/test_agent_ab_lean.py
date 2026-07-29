from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from benchmarks import agent_ab as benchmark
from tests.helpers.provider_runtime import (
    PINNED_MATHLIB_RUNTIME_UNAVAILABLE_REASON,
    pinned_mathlib_runtime_available,
)
from tests.integration.agent._agent_ab_support import (
    _lean_proof_case,
    _runtime_from_template,
)

from jacobian.contracts.capabilities import CapabilityMode, CapabilityRequest


@pytest.mark.lean_runtime
@pytest.mark.skipif(
    not pinned_mathlib_runtime_available(),
    reason=PINNED_MATHLIB_RUNTIME_UNAVAILABLE_REASON,
)
def test_lean_ab_scorer_accepts_any_exact_replayable_proof(
    tmp_path: Path,
    runtime_store_template_with_references: Path,
    monkeypatch: Any,
) -> None:
    score_report = benchmark.score_report
    case = _lean_proof_case()
    state_dir, runtime = _runtime_from_template(
        tmp_path,
        runtime_store_template_with_references,
        name="state",
    )
    proof = "intro n\nsimp"
    checked = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="lean.check",
            mode=CapabilityMode.VERIFY,
            input={
                "statement": case["statement"],
                "proof": proof,
                "environment": case["environment"],
            },
        )
    )
    record_uri = checked.assurance.verification_record_uri
    assert record_uri is not None
    report = {
        "case_id": case["case_id"],
        "conclusion": "TRUE",
        "proof": proof,
        "assurance": "VERIFIED",
        "replay_success": True,
        "verification_record_uri": record_uri,
        "false_certification": False,
        "feedback": {
            "reasoning_focus": [],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }
    trace = {
        "capability_id": "lean.check",
        "input": {
            "statement": case["statement"],
            "proof": proof,
            "environment": case["environment"],
        },
        "output": checked.output,
        "assurance": checked.assurance.model_dump(mode="json"),
        "artifact_uris": list(checked.artifact_uris),
    }

    score = score_report(
        case,
        report,
        condition="combined",
        state_dir=state_dir,
        mcp_calls=["capability.invoke"],
        capability_invocations=[trace],
    )

    assert score["passed"] is True
    assert score["exact_proof_completion"] is True
    assert score["replay_success"] is True
    assert score["false_certification"] is False

    def unavailable_replay(**_kwargs: object) -> None:
        raise benchmark.BenchmarkError("replay runtime unavailable")

    monkeypatch.setitem(
        score_report.__globals__,
        "_replay_lean_certificate",
        unavailable_replay,
    )
    replay_failure = score_report(
        case,
        report,
        condition="combined",
        state_dir=state_dir,
        mcp_calls=["capability.invoke"],
        capability_invocations=[trace],
    )
    assert replay_failure["passed"] is False
    assert replay_failure["exact_proof_completion"] is True
    assert replay_failure["replay_success"] is False
    assert replay_failure["false_certification"] is False


def test_lean_ab_scorer_marks_unbound_verified_claim_as_false_certification(
    tmp_path: Path,
) -> None:
    score_report = benchmark.score_report
    case = _lean_proof_case()
    report = {
        "case_id": case["case_id"],
        "conclusion": "TRUE",
        "proof": "exact bogus",
        "assurance": "VERIFIED",
        "replay_success": True,
        "verification_record_uri": "artifact://sha256/" + "0" * 64,
        "false_certification": False,
        "feedback": {
            "reasoning_focus": [],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }

    score = score_report(
        case,
        report,
        condition="baseline",
        state_dir=tmp_path,
        mcp_calls=["capability.invoke"],
        capability_invocations=[],
    )

    assert score["passed"] is False
    assert score["false_certification"] is True


def test_lean_ab_summary_compares_each_ablation_to_baseline() -> None:
    summarize_pairs = benchmark.summarize_pairs
    results = []
    for index, condition in enumerate(("baseline", "tactic", "retrieval", "combined")):
        results.append(
            {
                "case_id": "LEAN-C",
                "repetition": 1,
                "condition": condition,
                "score": {
                    "passed": condition != "baseline",
                    "exact_proof_completion": condition != "baseline",
                    "replay_success": condition != "baseline",
                },
                "elapsed_seconds": 10 + index,
                "usage": {"input_tokens": 100 + index, "output_tokens": 20},
                "shell_call_count": 0,
                "mcp_call_count": 1 + index,
                "tool_error_count": 0,
                "parameter_error_count": index,
                "false_certification": False,
            }
        )

    summary = summarize_pairs(results)

    assert set(summary["conditions"]) == {
        "baseline",
        "tactic",
        "retrieval",
        "combined",
    }
    assert len(summary["lean_comparisons"]) == 3
    assert summary["conditions"]["combined"]["exact_proof_completion_rate"] == 1
    assert summary["lean_comparisons"][2]["parameter_error_delta"] == 3


@pytest.mark.lean_runtime
@pytest.mark.skipif(
    not pinned_mathlib_runtime_available(),
    reason=PINNED_MATHLIB_RUNTIME_UNAVAILABLE_REASON,
)
def test_ab_lean_scorer_requires_exact_checker_bound_trace(
    tmp_path: Path,
    runtime_store_template_with_references: Path,
) -> None:
    load_cases = benchmark.load_cases
    score_report = benchmark.score_report
    case = load_cases(["LEAN-DECLARATION-AB-001"])[0]
    expected = cast(dict[str, Any], case["expected"])
    statement = cast(str, expected["statement"])
    proof = cast(str, expected["oracle_proof"])
    state_dir, runtime = _runtime_from_template(
        tmp_path,
        runtime_store_template_with_references,
        name="state",
    )
    checked = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="lean.check",
            mode=CapabilityMode.VERIFY,
            input={
                "environment": "MATHLIB",
                "statement": statement,
                "proof": proof,
            },
        )
    )
    record_uri = checked.assurance.verification_record_uri
    assert record_uri is not None
    report = {
        "case_id": case["case_id"],
        "statement": statement,
        "proof": proof,
        "declarations": ["List.revzip_map_snd"],
        "conclusion": "TRUE",
        "assurance": "VERIFIED",
        "verification_record_uri": record_uri,
        "limitations": [],
        "feedback": {
            "reasoning_focus": ["matched the exact declaration type"],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }
    invocations = [
        {
            "capability_id": "lean.declaration.search",
            "input": {
                "environment": "MATHLIB",
                "name_contains": "revzip",
                "result_limit": 10,
            },
            "output": {
                "declarations": [{"name": "List.revzip_map_snd"}],
                "environment_digest": "sha256:" + "a" * 64,
            },
            "assurance": {"level": "COMPUTED"},
        },
        {
            "capability_id": "lean.check",
            "input": {
                "environment": "MATHLIB",
                "statement": statement,
                "proof": proof,
            },
            "output": checked.output,
            "artifact_uris": list(checked.artifact_uris),
            "assurance": checked.assurance.model_dump(mode="json"),
        },
    ]

    score = score_report(
        case,
        report,
        condition="treatment",
        state_dir=state_dir,
        mcp_calls=["capability.invoke", "capability.invoke"],
        shell_calls=[],
        capability_attempt_ids=[
            "lean.declaration.search",
            "lean.check",
        ],
        capability_invocations=invocations,
    )

    assert score["passed"] is True
    assert score["intervention_attempted"] is True
    assert score["intervention_used"] is True

    report["proof"] = "exact List.revzip_map_snd []"
    with pytest.raises(
        benchmark.BenchmarkError,
        match="exact statement and proof",
    ):
        score_report(
            case,
            report,
            condition="treatment",
            state_dir=state_dir,
            mcp_calls=["capability.invoke", "capability.invoke"],
            shell_calls=[],
            capability_attempt_ids=[
                "lean.declaration.search",
                "lean.check",
            ],
            capability_invocations=invocations,
        )

    report["proof"] = proof
    report["declarations"] = ["List.not_cited"]
    with pytest.raises(benchmark.BenchmarkError, match="not cited"):
        score_report(
            case,
            report,
            condition="treatment",
            state_dir=state_dir,
            mcp_calls=["capability.invoke", "capability.invoke"],
            shell_calls=[],
            capability_attempt_ids=[
                "lean.declaration.search",
                "lean.check",
            ],
            capability_invocations=invocations,
        )


def test_ab_lean_scorer_rejects_false_certification(tmp_path: Path) -> None:
    load_cases = benchmark.load_cases
    score_report = benchmark.score_report
    case = load_cases(["LEAN-DECLARATION-AB-001"])[0]
    expected = cast(dict[str, Any], case["expected"])
    report = {
        "case_id": case["case_id"],
        "statement": expected["statement"],
        "proof": expected["oracle_proof"],
        "declarations": [],
        "conclusion": "TRUE",
        "assurance": "VERIFIED",
        "verification_record_uri": None,
        "limitations": [],
        "feedback": {
            "reasoning_focus": [],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }

    with pytest.raises(benchmark.BenchmarkError, match="verification record"):
        score_report(
            case,
            report,
            condition="control",
            state_dir=tmp_path,
            mcp_calls=["capability.invoke"],
            shell_calls=[],
            capability_attempt_ids=["lean.check"],
            capability_invocations=[],
        )


def test_ab_lean_scorer_separates_checker_runtime_failure(tmp_path: Path) -> None:
    load_cases = benchmark.load_cases
    score_report = benchmark.score_report
    case = load_cases(["LEAN-DECLARATION-AB-002"])[0]
    expected = cast(dict[str, Any], case["expected"])
    proof = cast(str, expected["oracle_proof"])
    diagnostic = (
        "The pinned Lean 4.31.0 toolchain is unavailable. Install it, then retry."
    )
    report = {
        "case_id": case["case_id"],
        "statement": expected["statement"],
        "proof": proof,
        "declarations": ["Set.image_preimage_eq_range_inter"],
        "conclusion": "UNKNOWN",
        "assurance": "HEURISTIC",
        "verification_record_uri": None,
        "limitations": [diagnostic],
        "feedback": {
            "reasoning_focus": [],
            "infrastructure_work": [],
            "tooling_gaps": [diagnostic],
        },
    }

    score = score_report(
        case,
        report,
        condition="control",
        state_dir=tmp_path,
        mcp_calls=["capability.invoke"],
        shell_calls=[],
        capability_attempt_ids=["lean.check"],
        capability_invocations=[
            {
                "capability_id": "lean.check",
                "input": {
                    "environment": "MATHLIB",
                    "statement": expected["statement"],
                    "proof": proof,
                },
                "output": {
                    "conclusion": "UNKNOWN",
                    "diagnostics": [diagnostic],
                    "verification_record_uri": None,
                },
                "assurance": {"level": "HEURISTIC"},
            }
        ],
    )

    assert score["passed"] is False
    assert score["operational_failure"] is True
    assert "toolchain is unavailable" in score["error"]
