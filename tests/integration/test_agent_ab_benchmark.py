from __future__ import annotations

import json
import runpy
from pathlib import Path
from typing import Any, cast

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.kernel import JacobianKernel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = runpy.run_path(str(PROJECT_ROOT / "benchmarks" / "agent_ab.py"))


def _report(
    *,
    assurance: str,
    verification_record_uri: str | None,
) -> dict[str, Any]:
    return {
        "case_id": "ERDOS-STRAUS-AB-001",
        "conclusion": "TRUE",
        "checked_count": 119,
        "first_failure": None,
        "assurance": assurance,
        "verification_record_uri": verification_record_uri,
        "limitations": ["finite interval only"],
        "feedback": {
            "reasoning_focus": ["bounded interpretation"],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }


def test_ab_transcript_parser_separates_mcp_and_shell_calls(tmp_path: Path) -> None:
    parse_transcript = cast(Any, BENCHMARK["parse_transcript"])
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
        "capability_ids": [],
        "capability_invocations": [],
    }


def test_ab_transcript_parser_counts_completed_capability_rejections(
    tmp_path: Path,
) -> None:
    parse_transcript = cast(Any, BENCHMARK["parse_transcript"])
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
    parse_transcript = cast(Any, BENCHMARK["parse_transcript"])
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


def test_ab_scorer_accepts_control_and_durable_treatment(tmp_path: Path) -> None:
    load_cases = cast(Any, BENCHMARK["load_cases"])
    score_report = cast(Any, BENCHMARK["score_report"])
    case = load_cases(["ERDOS-STRAUS-AB-001"])[0]

    control = score_report(
        case,
        _report(assurance="SELF_CHECKED", verification_record_uri=None),
        condition="control",
        state_dir=tmp_path / "unused",
        mcp_calls=[],
    )
    assert control["passed"] is True

    state_dir = tmp_path / "treatment"
    kernel = JacobianKernel(state_dir, install_references=True)
    reference = kernel.references["erdos_straus"]
    claim = kernel.capabilities.invoke(
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
    candidate = kernel.capabilities.invoke(
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
    found = kernel.capabilities.invoke(
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
    verified = kernel.capabilities.invoke(
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
    summarize_pairs = cast(Any, BENCHMARK["summarize_pairs"])
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
        },
    ]

    summary = summarize_pairs(results)

    assert summary["pair_count"] == 1
    assert summary["pairs"][0]["input_token_delta"] == -40
    assert summary["pairs"][0]["elapsed_delta_seconds"] == -4
    assert summary["conditions"]["treatment"]["median_tool_calls"] == 1


def test_ab_graph_scorer_accepts_any_valid_witness_and_durable_flow(
    tmp_path: Path,
) -> None:
    load_cases = cast(Any, BENCHMARK["load_cases"])
    score_report = cast(Any, BENCHMARK["score_report"])
    case = load_cases(["GRAPH-COUNTEREXAMPLE-AB-001"])[0]
    state_dir = tmp_path / "state"
    kernel = JacobianKernel(state_dir)
    searched = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.search.atlas",
            mode=CapabilityMode.EXPLORE,
            input={
                "order": 6,
                "constraints": {
                    "connected": True,
                    "triangle_free": True,
                    "minimum_degree": 2,
                    "bipartite": False,
                },
                "limit": 1,
            },
        )
    )
    candidate = cast(dict[str, Any], searched.output["candidates"][0])
    graph_uri = cast(str, candidate["graph_uri"])
    requested = cast(list[str], case["expected"]["properties"])
    computed = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.compute.properties",
            mode=CapabilityMode.EXPLORE,
            input={"graph_uri": graph_uri, "properties": requested},
        )
    )
    property_uri = cast(str, computed.output["property_artifact_uri"])
    graph = kernel.store.get(graph_uri).payload
    report = {
        "case_id": case["case_id"],
        "conclusion": "FALSE",
        "assurance": "COMPUTED",
        "final_verification": "UNVERIFIED",
        "graph": graph,
        "properties": computed.output["properties"],
        "graph_uri": graph_uri,
        "property_artifact_uri": property_uri,
        "limitations": ["bounded witness"],
        "feedback": {
            "reasoning_focus": [],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }
    invocations = [
        {
            "capability_id": "graph.search.atlas",
            "input": {
                "order": 6,
                "constraints": case["expected"]["constraints"],
                "limit": 1,
            },
            "artifact_uris": list(searched.artifact_uris),
        },
        {
            "capability_id": "graph.compute.properties",
            "input": {"graph_uri": graph_uri, "properties": requested},
            "artifact_uris": list(computed.artifact_uris),
        },
    ]

    score = score_report(
        case,
        report,
        condition="treatment",
        state_dir=state_dir,
        mcp_calls=["capability.invoke", "capability.invoke"],
        capability_invocations=invocations,
    )

    assert score["passed"] is True
    assert score["false_certification"] is False


def test_ab_graph_scorer_rejects_false_certification(tmp_path: Path) -> None:
    load_cases = cast(Any, BENCHMARK["load_cases"])
    score_report = cast(Any, BENCHMARK["score_report"])
    case = load_cases(["GRAPH-PATH-AB-001"])[0]
    report = {
        "case_id": case["case_id"],
        "conclusion": "TRUE",
        "assurance": "VERIFIED",
        "final_verification": "VERIFIED",
        "graph": {
            "vertices": ["0", "1", "2", "3", "4", "5"],
            "edges": [["0", "1"], ["1", "2"], ["2", "3"], ["3", "4"], ["4", "5"]],
        },
        "properties": {
            "order": 6,
            "size": 5,
            "connected": True,
            "tree": True,
            "maximum_degree": 2,
            "bipartite": True,
            "triangle_count": 0,
            "independence_number": 3,
        },
        "graph_uri": None,
        "property_artifact_uri": None,
    }

    try:
        score_report(
            case,
            report,
            condition="control",
            state_dir=tmp_path,
            mcp_calls=[],
        )
    except BENCHMARK["BenchmarkError"] as exc:
        assert "falsely certified" in str(exc)
    else:
        raise AssertionError("false certification was accepted")


def test_ab_graph_scorer_enforces_exact_vertex_order(tmp_path: Path) -> None:
    load_cases = cast(Any, BENCHMARK["load_cases"])
    score_report = cast(Any, BENCHMARK["score_report"])
    case = load_cases(["GRAPH-PATH-AB-001"])[0]
    report = {
        "case_id": case["case_id"],
        "conclusion": "TRUE",
        "assurance": "SELF_CHECKED",
        "final_verification": "UNVERIFIED",
        "graph": {
            "vertices": ["0", "1", "2"],
            "edges": [["0", "1"], ["1", "2"]],
        },
        "properties": {
            "order": 3,
            "size": 2,
            "connected": True,
            "tree": True,
            "maximum_degree": 2,
            "bipartite": True,
            "triangle_count": 0,
            "independence_number": 2,
        },
        "graph_uri": None,
        "property_artifact_uri": None,
    }

    try:
        score_report(
            case,
            report,
            condition="control",
            state_dir=tmp_path,
            mcp_calls=[],
        )
    except BENCHMARK["BenchmarkError"] as exc:
        assert "order constraint" in str(exc)
    else:
        raise AssertionError("wrong-order graph was accepted")


def test_ab_partition_scorer_requires_checker_backed_coverage(tmp_path: Path) -> None:
    load_cases = cast(Any, BENCHMARK["load_cases"])
    score_report = cast(Any, BENCHMARK["score_report"])
    case = load_cases(["FINITE-PARTITION-AB-001"])[0]
    state_dir = tmp_path / "state"
    kernel = JacobianKernel(state_dir, install_references=True)
    cases = [
        {"case_id": "r0", "members": ["0", "3", "6", "9"]},
        {"case_id": "r1", "members": ["1", "4", "7", "10"]},
        {"case_id": "r2", "members": ["2", "5", "8", "11"]},
    ]
    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="case.partition.finite",
            mode=CapabilityMode.VERIFY,
            input={
                "universe": case["expected"]["universe"],
                "cases": cases,
                "require_disjoint": True,
            },
        )
    )
    report = {
        "case_id": case["case_id"],
        "conclusion": "TRUE",
        "assurance": "VERIFIED",
        "final_verification": "VERIFIED",
        "cases": cases,
        **{
            field: result.output[field]
            for field in (
                "scope_uri",
                "claim_uri",
                "partition_uri",
                "certificate_uri",
                "verification_record_uri",
            )
        },
    }

    score = score_report(
        case,
        report,
        condition="treatment",
        state_dir=state_dir,
        mcp_calls=["capability.invoke"],
        capability_invocations=[
            {
                "capability_id": "case.partition.finite",
                "input": {
                    "universe": case["expected"]["universe"],
                    "cases": cases,
                    "require_disjoint": True,
                },
                "output": result.output,
                "artifact_uris": result.artifact_uris,
                "assurance": result.assurance.model_dump(mode="json"),
            }
        ],
    )

    assert score["passed"] is True

    report["cases"] = [
        {"case_id": f"spoofed-{item['case_id']}", "members": item["members"]}
        for item in cases
    ]
    try:
        score_report(
            case,
            report,
            condition="treatment",
            state_dir=state_dir,
            mcp_calls=["capability.invoke"],
            capability_invocations=[
                {
                    "capability_id": "case.partition.finite",
                    "input": {
                        "universe": case["expected"]["universe"],
                        "cases": cases,
                        "require_disjoint": True,
                    },
                    "output": result.output,
                    "artifact_uris": result.artifact_uris,
                    "assurance": result.assurance.model_dump(mode="json"),
                }
            ],
        )
    except BENCHMARK["BenchmarkError"] as exc:
        assert "exact verified capability trace" in str(exc)
    else:
        raise AssertionError("unbound partition report was accepted")


def test_ab_partition_scorer_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    load_cases = cast(Any, BENCHMARK["load_cases"])
    score_report = cast(Any, BENCHMARK["score_report"])
    case = load_cases(["FINITE-PARTITION-AB-001"])[0]
    report = {
        "case_id": case["case_id"],
        "conclusion": "TRUE",
        "assurance": "SELF_CHECKED",
        "final_verification": "UNVERIFIED",
        "cases": [
            {"case_id": "same", "members": ["0", "3", "6", "9"]},
            {"case_id": "same", "members": ["1", "4", "7", "10"]},
            {"case_id": "r2", "members": ["2", "5", "8", "11"]},
        ],
        "scope_uri": None,
        "claim_uri": None,
        "partition_uri": None,
        "certificate_uri": None,
        "verification_record_uri": None,
    }

    try:
        score_report(
            case,
            report,
            condition="control",
            state_dir=tmp_path,
            mcp_calls=[],
        )
    except BENCHMARK["BenchmarkError"] as exc:
        assert "distinct and non-empty" in str(exc)
    else:
        raise AssertionError("duplicate partition case identifiers were accepted")


def test_ab_lean_scorer_requires_exact_checker_bound_trace(tmp_path: Path) -> None:
    load_cases = cast(Any, BENCHMARK["load_cases"])
    score_report = cast(Any, BENCHMARK["score_report"])
    case = load_cases(["LEAN-DECLARATION-AB-001"])[0]
    expected = cast(dict[str, Any], case["expected"])
    statement = cast(str, expected["statement"])
    proof = cast(str, expected["oracle_proof"])
    state_dir = tmp_path / "state"
    kernel = JacobianKernel(state_dir, install_references=True)
    checked = kernel.capabilities.invoke(
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
    try:
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
    except BENCHMARK["BenchmarkError"] as exc:
        assert "exact statement and proof" in str(exc)
    else:
        raise AssertionError("mismatched Lean proof was accepted")

    report["proof"] = proof
    report["declarations"] = ["List.not_cited"]
    try:
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
    except BENCHMARK["BenchmarkError"] as exc:
        assert "not cited" in str(exc)
    else:
        raise AssertionError("uncited Lean declaration was accepted")


def test_ab_lean_scorer_rejects_false_certification(tmp_path: Path) -> None:
    load_cases = cast(Any, BENCHMARK["load_cases"])
    score_report = cast(Any, BENCHMARK["score_report"])
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

    try:
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
    except BENCHMARK["BenchmarkError"] as exc:
        assert "verification record" in str(exc)
    else:
        raise AssertionError("unrecorded Lean verification was accepted")


def test_ab_lean_scorer_separates_checker_runtime_failure(tmp_path: Path) -> None:
    load_cases = cast(Any, BENCHMARK["load_cases"])
    score_report = cast(Any, BENCHMARK["score_report"])
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


def test_ab_lean_control_ablation_keeps_checker_only(tmp_path: Path) -> None:
    kernel = JacobianKernel(
        tmp_path,
        install_references=True,
        capability_exclusions=frozenset(
            {
                "lean.declaration.search",
                "lean.declaration.inspect",
            }
        ),
    )

    lean_ids = {
        descriptor.capability_id
        for descriptor in kernel.capabilities.catalog().capabilities
        if descriptor.capability_id.startswith("lean.")
    }

    assert lean_ids == {"lean.check"}
    excluded = kernel.capabilities.invoke(
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
    codex_command = cast(Any, BENCHMARK["_codex_command"])
    common = {
        "codex_command": "codex",
        "workspace": tmp_path / "workspace",
        "report_path": tmp_path / "report.json",
        "state_dir": tmp_path / "state",
        "model": "gpt-5.6",
        "reasoning_effort": "high",
        "task_type": "lean_declaration",
    }

    control = codex_command(condition="control", **common)
    treatment = codex_command(condition="treatment", **common)

    assert "agent_ab_mcp.py" in " ".join(control)
    assert "agent_ab_mcp.py" in " ".join(treatment)
    assert " ".join(control).count("--exclude-capability") == 2
    assert "--exclude-capability" not in " ".join(treatment)
