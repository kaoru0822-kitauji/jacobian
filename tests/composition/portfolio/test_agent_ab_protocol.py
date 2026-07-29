from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks import agent_ab as benchmark
from tests.composition.agent_ab_support import _runtime_from_template
from tests.support._agent_ab_support import (
    _install_fake_carcara,
    _report,
    _smt_producer,
)

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.contracts.smt import SmtResourceBudget


def test_ab_sat_report_contract_identifies_the_producer_evidence_uri() -> None:
    schema_path = (
        benchmark.PROJECT_ROOT / "benchmarks" / "ab_cases" / "sat-report.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    description = schema["properties"]["evidence_uri"]["description"]

    assert "assignment_uri from sat.model.find" in description
    assert "proof_uri from sat.unsat_proof.find" in description
    assert "never the verifier's witness_uri or certificate_uri" in description
    assert (
        "Do not substitute the verifier's witness_uri"
        in benchmark.SAT_TREATMENT_INSTRUCTIONS
    )
    assert "named assignment map returned" in benchmark.SAT_TREATMENT_INSTRUCTIONS
    assert "pre-canonical variable order" in benchmark.SAT_TREATMENT_INSTRUCTIONS


def test_ab_smt_task_selects_its_own_control_and_treatment_instructions() -> None:
    select = benchmark._condition_instructions

    control = select("smt_unsat_proof", "control")
    treatment = select("smt_unsat_proof", "treatment")

    assert "SMT-LIB query directly" in control
    assert "smt.unsat_proof.find" in treatment
    assert "smt.unsat_proof.verify" in treatment
    assert "Erdos" not in control
    assert "Erdos" not in treatment


def test_autonomous_discovery_prompt_exposes_the_toolbox_without_leaking_a_path() -> (
    None
):
    instructions = benchmark.AUTONOMOUS_DISCOVERY_TREATMENT_INSTRUCTIONS
    normalized = " ".join(instructions.split())

    assert (
        "Capability IDs and a successful tool sequence are intentionally not supplied"
        in normalized
    )
    assert "own mathematical strategy" in normalized
    assert "rank is not a recommendation" in normalized
    assert "graph.search.atlas" not in instructions
    assert "graph.compute.properties" not in instructions


def test_autonomous_discovery_case_is_visible_in_the_bounded_dispatch_plan() -> None:
    load_cases = benchmark.load_cases
    build_plan = benchmark.build_dispatch_plan
    cases = load_cases(["GRAPH-DISCOVERY-AB-001"])

    plan = build_plan(
        cases,
        repetitions=2,
        model="fixture-model",
        reasoning_effort="medium",
        timeout_seconds=30,
    )

    assert plan["model_run_count"] == 4
    assert plan["cases"] == [
        {
            "case_id": "GRAPH-DISCOVERY-AB-001",
            "task_type": "graph",
            "autonomous_discovery": True,
            "conditions": ["control", "treatment"],
            "repetitions": 2,
            "model_runs": 4,
            "capability_policy_profiles": {
                "control": None,
                "treatment": "COMPUTE_VERIFY_NO_RETRIEVAL",
            },
        }
    ]


def test_ab_smt_scorer_preserves_rejected_holey_proof(
    tmp_path: Path,
    authorized_portfolio_template: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_carcara(tmp_path, monkeypatch)
    state_dir, runtime = _runtime_from_template(
        tmp_path,
        authorized_portfolio_template,
        name="state",
    )
    text = (
        "(set-logic QF_UF)\n"
        "(declare-sort U 0)\n"
        "(declare-fun a () U)\n"
        "(assert (not (= a a)))\n"
        "(check-sat)\n"
    )
    problem = runtime.core.smt.put_problem(logic="QF_UF", smtlib_text=text)
    proof = runtime.core.smt.put_proof(
        problem_uri=problem.artifact_uri,
        proof=b'(\n(step t0 (cl) :rule hole :args ("unsupported"))\n)\n',
        producer=_smt_producer(),
        resource_budget=SmtResourceBudget(wall_seconds=5),
    )
    rejected = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="smt.unsat_proof.verify",
            mode=CapabilityMode.VERIFY,
            input={"proof_uri": proof.artifact_uri},
        )
    )
    assert rejected.output["status"] == "REJECTED"
    case = {
        "case_id": "SMT-PRIVATE-TEST-001",
        "task_type": "smt_unsat_proof",
        "logic": "QF_UF",
        "smtlib_text": text,
        "expected": {
            "status": "UNSATISFIABLE",
            "verification_status": "REJECTED",
        },
    }
    report = {
        "case_id": case["case_id"],
        "status": "UNSATISFIABLE",
        "assurance": "COMPUTED",
        "final_verification": "UNVERIFIED",
        "problem_uri": problem.artifact_uri,
        "proof_uri": proof.artifact_uri,
        "verification_record_uri": None,
        "detail": "the exact proof was rejected because it contains a hole",
        "feedback": {
            "reasoning_focus": ["preserve the verification boundary"],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }
    invocations = [
        {
            "capability_id": "smt.unsat_proof.find",
            "input": {
                "logic": "QF_UF",
                "smtlib_text": text,
                "resource_budget": {"wall_seconds": 5},
            },
            "output": {
                "solver_status": "UNSATISFIABLE",
                "problem_uri": problem.artifact_uri,
                "proof_uri": proof.artifact_uri,
            },
            "artifact_uris": [problem.artifact_uri, proof.artifact_uri],
        },
        {
            "capability_id": "smt.unsat_proof.verify",
            "input": {"proof_uri": proof.artifact_uri},
            "output": rejected.output,
            "artifact_uris": list(rejected.artifact_uris),
        },
    ]
    score_report = benchmark.score_report

    score = score_report(
        case,
        report,
        condition="treatment",
        state_dir=state_dir,
        mcp_calls=["capability.invoke", "capability.invoke"],
        shell_calls=[],
        capability_invocations=invocations,
    )

    assert score["passed"] is True
    assert score["false_certification"] is False


def test_ab_transcript_parser_separates_mcp_and_shell_calls(tmp_path: Path) -> None:
    parse_transcript = benchmark.parse_transcript
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\n".join(
            json.dumps(event)
            for event in (
                {
                    "type": "item.completed",
                    "item": {
                        "type": "command_execution",
                        "command": "python solve.py",
                    },
                },
                {
                    "type": "item.completed",
                    "item": {
                        "type": "mcp_tool_call",
                        "tool": "capability.invoke",
                        "metadata": {"status": {"phase": "done"}},
                    },
                },
                {
                    "type": "turn.completed",
                    "usage": {"input_tokens": 12, "output_tokens": 3},
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )

    telemetry = parse_transcript(transcript)

    assert telemetry == {
        "mcp_calls": ["capability.invoke"],
        "shell_calls": ["python solve.py"],
        "usage": {"input_tokens": 12, "output_tokens": 3},
        "tool_error_count": 0,
        "parameter_error_count": 0,
        "capability_rejection_count": 0,
        "successful_tool_calls": ["capability.invoke"],
        "capability_attempt_ids": [],
        "capability_descriptions": [],
        "capability_ids": [],
        "capability_invocations": [],
        "mcp_response_bytes": 0,
        "mcp_response_bytes_by_tool": {},
        "mcp_wire_bytes": 0,
        "mcp_wire_bytes_by_tool": {},
        "mcp_model_visible_bytes": 0,
        "mcp_model_visible_bytes_by_tool": {},
        "mcp_logical_payload_bytes": 0,
        "mcp_logical_payload_bytes_by_tool": {},
        "mcp_logical_payload_observed_calls": 0,
        "repeated_mcp_call_count": 0,
        "repeated_mcp_calls": [],
        "capability_describe_index_calls": 0,
        "capability_describe_exact_calls": 0,
    }


def test_ab_transcript_parser_counts_completed_capability_rejections(
    tmp_path: Path,
) -> None:
    parse_transcript = benchmark.parse_transcript
    transcript = tmp_path / "transcript.jsonl"
    response = {
        "capability_id": "lean.check",
        "execution": {"status": "COMPLETED"},
        "output": {
            "conclusion": "UNKNOWN",
            "input": {"status": "REJECTED", "errors": ["unsolved goals"]},
        },
        "assurance": {"level": "HEURISTIC"},
    }
    transcript.write_text(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "mcp_tool_call",
                    "tool": "capability.invoke",
                    "arguments": {
                        "capability_id": "lean.check",
                        "payload": {
                            "environment": "MATHLIB",
                            "statement": "True",
                            "proof": "exact False.elim",
                        },
                    },
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(response)}]
                    },
                    "status": "completed",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    telemetry = parse_transcript(transcript)

    assert telemetry["capability_rejection_count"] == 1
    assert telemetry["tool_error_count"] == 0
    assert telemetry["capability_ids"] == ["lean.check"]


def test_ab_transcript_parser_counts_structured_mcp_errors(tmp_path: Path) -> None:
    parse_transcript = benchmark.parse_transcript
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "mcp_tool_call",
                    "tool": "capability.describe",
                    "arguments": {"capability_id": "missing.capability"},
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {
                                        "error": {
                                            "code": "UNKNOWN_CAPABILITY",
                                            "message": "Unknown capability",
                                        }
                                    }
                                ),
                            }
                        ]
                    },
                    "status": "completed",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    telemetry = parse_transcript(transcript)

    assert telemetry["tool_error_count"] == 1
    assert telemetry["successful_tool_calls"] == []


def test_ab_scorer_accepts_control_and_durable_treatment(
    tmp_path: Path, authorized_portfolio_template: Path
) -> None:
    load_cases = benchmark.load_cases
    score_report = benchmark.score_report
    case = load_cases(["ERDOS-STRAUS-AB-001"])[0]

    control = score_report(
        case,
        _report(assurance="SELF_CHECKED", verification_record_uri=None),
        condition="control",
        state_dir=tmp_path / "unused",
        mcp_calls=[],
    )
    assert control["passed"] is True

    state_dir, runtime = _runtime_from_template(
        tmp_path,
        authorized_portfolio_template,
        name="treatment",
    )
    reference = runtime.portfolio.references["erdos_straus"]
    claim = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="artifact.put",
            input={
                "schema_uri": reference.claim_schema_uri,
                "semantics_uri": reference.semantics_uri,
                "payload": {
                    "claim_schema_version": "1",
                    "domain_id": reference.domain_id,
                    "domain_version": reference.domain_version,
                    "semantics_uri": reference.semantics_uri,
                    "quantifiers": [],
                    "predicate": {
                        "name": "erdos_straus_range",
                        "parameters": {"lower_bound": 2, "upper_bound": 120},
                    },
                    "bounds": {},
                    "required_capabilities": ["Evaluator", "WitnessOracle"],
                    "correspondence_status": "HUMAN_REVIEWED",
                },
            },
        )
    )
    claim_uri = claim.output["artifact_uri"]
    candidate = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="artifact.put",
            input={
                "schema_uri": reference.candidate_schema_uri,
                "semantics_uri": reference.semantics_uri,
                "payload": {"lower_bound": 2, "upper_bound": 120},
                "parents": [claim_uri],
            },
        )
    )
    candidate_uri = candidate.output["artifact_uri"]
    found = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="witness.find",
            input={
                "claim_uri": claim_uri,
                "candidate_uri": candidate_uri,
                "plugin_id": reference.plugin_id,
                "witness_role": "SUPPORTS_CLAIM",
                "wall_seconds": 30,
            },
        )
    )
    witness_uri = found.output["witness_uri"]
    assert witness_uri is not None
    verified = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="witness.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "claim_uri": claim_uri,
                "candidate_uri": candidate_uri,
                "witness_uri": witness_uri,
                "checker_id": reference.witness_checker_ids[
                    "erdos_straus.decomposition_table"
                ],
            },
        )
    )
    record_uri = verified.assurance.verification_record_uri
    assert record_uri is not None
    assert verified.scope is not None
    assert verified.scope.parameters["claim_uri"] == claim_uri
    assert verified.completeness.status is CapabilityCompletenessStatus.COMPLETE
    assert verified.completeness.assurance_level is CapabilityAssuranceLevel.COMPUTED
    treatment = score_report(
        case,
        _report(assurance="VERIFIED", verification_record_uri=record_uri),
        condition="treatment",
        state_dir=state_dir,
        mcp_calls=["capability.invoke"],
    )
    assert treatment["passed"] is True


def test_ab_summary_reports_paired_deltas() -> None:
    summarize_pairs = benchmark.summarize_pairs
    results = [
        {
            "case_id": "C",
            "repetition": 1,
            "condition": "control",
            "score": {"passed": True},
            "elapsed_seconds": 10,
            "usage": {"input_tokens": 100, "output_tokens": 20},
            "shell_call_count": 2,
            "mcp_call_count": 0,
            "mcp_wire_bytes": 0,
            "mcp_model_visible_bytes": 0,
            "mcp_logical_payload_bytes": 0,
        },
        {
            "case_id": "C",
            "repetition": 1,
            "condition": "treatment",
            "score": {"passed": True},
            "elapsed_seconds": 6,
            "usage": {"input_tokens": 60, "output_tokens": 10},
            "shell_call_count": 0,
            "mcp_call_count": 1,
            "mcp_wire_bytes": 1_200,
            "mcp_model_visible_bytes": 400,
            "mcp_logical_payload_bytes": 2_000,
        },
    ]

    summary = summarize_pairs(results)

    assert summary["pair_count"] == 1
    assert summary["pairs"][0]["input_token_delta"] == -40
    assert summary["pairs"][0]["elapsed_delta_seconds"] == -4
    assert summary["pairs"][0]["mcp_wire_byte_delta"] == 1_200
    assert summary["pairs"][0]["mcp_model_visible_byte_delta"] == 400
    assert summary["pairs"][0]["mcp_logical_payload_byte_delta"] == 2_000
    assert summary["conditions"]["treatment"]["median_tool_calls"] == 1
    assert summary["conditions"]["treatment"]["median_mcp_model_visible_bytes"] == 400
