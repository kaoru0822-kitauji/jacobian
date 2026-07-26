from __future__ import annotations

import json
import runpy
import shutil
from pathlib import Path
from typing import Any, cast

import pytest

from jacobian.contracts.capabilities import CapabilityMode, CapabilityRequest
from jacobian.contracts.evidence import WitnessRole
from jacobian.kernel import JacobianKernel

pytestmark = pytest.mark.usefixtures("initialized_kernel_store")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = runpy.run_path(str(PROJECT_ROOT / "benchmarks" / "agent_mcp.py"))


def _feedback() -> dict[str, list[str]]:
    return {
        "tooling_strengths": ["explicit atomic capability composition"],
        "tooling_gaps": [],
        "domain_knowledge_gaps": [],
        "suggested_improvements": [],
    }


def _invoke(
    kernel: JacobianKernel,
    capability_id: str,
    payload: dict[str, object],
    *,
    mode: CapabilityMode = CapabilityMode.EXPLORE,
):
    return kernel.capabilities.invoke(
        CapabilityRequest(capability_id=capability_id, mode=mode, input=payload)
    )


@pytest.mark.integration
def test_graph_capability_scorer_checks_multi_call_artifacts(
    tmp_path: Path,
) -> None:
    case = BENCHMARK["load_cases"](["GRAPH-ATLAS-PATH-001"])[0]
    kernel = JacobianKernel(tmp_path, install_references=True)
    searched = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.search.atlas",
            input={
                "order": 5,
                "constraints": {"tree": True, "maximum_degree": 2},
                "limit": 1,
            },
        )
    )
    graph_uri = searched.output["candidates"][0]["graph_uri"]
    computed = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.compute.properties",
            input={
                "graph_uri": graph_uri,
                "properties": list(case["expected"]["properties"]),
            },
        )
    )
    report = {
        "case_id": case["case_id"],
        "assurance": "COMPUTED",
        "completeness": "COMPLETE",
        "final_verification": "UNVERIFIED",
        "graph_uri": graph_uri,
        "property_artifact_uri": computed.output["property_artifact_uri"],
        "properties": computed.output["properties"],
        "limitations": ["Graph Atlas contains graphs only through order 7."],
        "feedback": _feedback(),
    }

    score = BENCHMARK["score_run"](
        case,
        report,
        state_dir=tmp_path,
        tool_calls=["capability.invoke", "capability.invoke"],
        capability_ids=[
            "graph.search.atlas",
            "graph.compute.properties",
        ],
        capability_invocations=[
            {
                "capability_id": "graph.search.atlas",
                "input": {
                    "order": 5,
                    "constraints": {"tree": True, "maximum_degree": 2},
                    "limit": 1,
                },
                "output": searched.output,
                "artifact_uris": list(searched.artifact_uris),
                "assurance": searched.assurance.model_dump(mode="json"),
                "completeness": searched.completeness.model_dump(mode="json"),
            },
            {
                "capability_id": "graph.compute.properties",
                "input": {
                    "graph_uri": graph_uri,
                    "properties": list(case["expected"]["properties"]),
                },
                "output": computed.output,
                "artifact_uris": list(computed.artifact_uris),
                "assurance": computed.assurance.model_dump(mode="json"),
                "completeness": computed.completeness.model_dump(mode="json"),
            },
        ],
    )

    assert score["passed"] is True
    assert score["case_id"] == case["case_id"]

    with pytest.raises(
        BENCHMARK["BenchmarkError"],
        match="successful search-to-property artifact flow",
    ):
        BENCHMARK["score_run"](
            case,
            report,
            state_dir=tmp_path,
            tool_calls=["capability.invoke", "capability.invoke"],
            capability_ids=[
                "graph.search.atlas",
                "graph.compute.properties",
            ],
            capability_invocations=[],
        )


def test_transcript_parser_counts_completed_mcp_calls_once(tmp_path: Path) -> None:
    parse_transcript = cast(Any, BENCHMARK["parse_transcript"])
    transcript = tmp_path / "transcript.jsonl"
    events = [
        {
            "type": "item.started",
            "item": {
                "type": "mcp_tool_call",
                "tool": "artifact.put",
                "status": "in_progress",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "tool": "artifact.put",
                "status": "completed",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "tool": "capability.invoke",
                "status": "completed",
                "result": {
                    "isError": True,
                    "content": [{"code": "INVALID_PARAMS"}],
                },
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "tool": "capability.invoke",
                "status": "completed",
                "arguments": {
                    "capability_id": "graph.search.atlas",
                },
                "result": {
                    "execution": {"status": "ERROR"},
                    "diagnostics": [{"code": "INVALID_CONSTRAINT_RANGE"}],
                },
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "tool": "capability.invoke",
                "status": "completed",
                "arguments": {
                    "capability_id": "graph.compute.properties",
                    "payload": {"graph_uri": "artifact://example"},
                },
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "capability_id": "graph.compute.properties",
                                    "execution": {"status": "COMPLETED"},
                                    "output": {"property_artifact_uri": "artifact://p"},
                                    "artifact_uris": ["artifact://p"],
                                    "assurance": {"level": "COMPUTED"},
                                    "completeness": {"status": "COMPLETE"},
                                }
                            ),
                        }
                    ],
                    "structured_content": None,
                },
            },
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 12, "output_tokens": 3},
        },
    ]
    transcript.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    calls, usage, metrics = parse_transcript(transcript)

    assert calls == [
        "artifact.put",
        "capability.invoke",
        "capability.invoke",
        "capability.invoke",
    ]
    assert usage == {"input_tokens": 12, "output_tokens": 3}
    assert metrics == {
        "tool_error_count": 2,
        "parameter_error_count": 2,
        "successful_tool_calls": ["artifact.put", "capability.invoke"],
        "capability_ids": ["graph.compute.properties"],
        "capability_invocations": [
            {
                "capability_id": "graph.compute.properties",
                "input": {"graph_uri": "artifact://example"},
                "output": {"property_artifact_uri": "artifact://p"},
                "artifact_uris": ["artifact://p"],
                "assurance": {"level": "COMPUTED"},
                "completeness": {"status": "COMPLETE"},
            }
        ],
    }


def test_known_answer_scorer_replays_durable_witness_bindings(
    tmp_path: Path,
) -> None:
    load_cases = cast(Any, BENCHMARK["load_cases"])
    score_run = cast(Any, BENCHMARK["score_run"])
    case = next(case for case in load_cases(["PATH-CLOSURE-001"]) if case["case_id"])
    kernel = JacobianKernel(tmp_path, install_references=True)
    reference = kernel.references["graph_paths"]
    claim = _invoke(
        kernel,
        "artifact.put",
        {
            "schema_uri": reference.claim_schema_uri,
            "semantics_uri": reference.semantics_uri,
            "payload": {
                "claim_schema_version": "1",
                "domain_id": reference.domain_id,
                "domain_version": reference.domain_version,
                "semantics_uri": reference.semantics_uri,
                "quantifiers": [],
                "predicate": {
                    "name": "intended_paths_complete",
                    "parameters": {"simple": True},
                },
                "bounds": {},
                "required_capabilities": ["Evaluator", "WitnessOracle"],
                "correspondence_status": "HUMAN_REVIEWED",
            },
        },
    )
    claim_uri = claim.output["artifact_uri"]
    candidate = _invoke(
        kernel,
        "artifact.put",
        {
            "schema_uri": reference.candidate_schema_uri,
            "semantics_uri": reference.semantics_uri,
            "payload": {
                "vertices": ["s", "a", "b", "x", "t1", "t2"],
                "arcs": [
                    ["s", "a"],
                    ["a", "x"],
                    ["s", "b"],
                    ["b", "x"],
                    ["x", "t1"],
                    ["x", "t2"],
                ],
                "source": "s",
                "terminals": ["t1", "t2"],
                "intended_paths": [
                    ["s", "a", "x", "t1"],
                    ["s", "b", "x", "t2"],
                ],
            },
            "parents": [claim_uri],
        },
    )
    candidate_uri = candidate.output["artifact_uri"]
    validation = _invoke(
        kernel,
        "claim.validate",
        {"claim_uri": claim_uri, "plugin_id": reference.plugin_id},
    )
    assert validation.output["valid"] is True
    _invoke(
        kernel,
        "evaluate.batch",
        {
            "claim_uri": claim_uri,
            "candidate_uris": [candidate_uri],
            "plugin_id": reference.plugin_id,
            "profile": "EXACT_CANDIDATE",
            "seed": 0,
            "wall_seconds": 30,
        },
    )
    found = _invoke(
        kernel,
        "witness.find",
        {
            "claim_uri": claim_uri,
            "candidate_uri": candidate_uri,
            "plugin_id": reference.plugin_id,
            "witness_role": WitnessRole.DEFEATS_CANDIDATE.value,
            "wall_seconds": 30,
        },
    )
    witness_uri = found.output["witness_uri"]
    assert witness_uri is not None
    verified = _invoke(
        kernel,
        "witness.verify",
        {
            "claim_uri": claim_uri,
            "candidate_uri": candidate_uri,
            "witness_uri": witness_uri,
            "checker_id": reference.witness_checker_ids["graph.omitted_path"],
        },
        mode=CapabilityMode.VERIFY,
    )
    assert verified.assurance.verification_record_uri is not None
    report = {
        "case_id": case["case_id"],
        "conclusion": "FALSE",
        "evaluation_verification": "UNVERIFIED",
        "witness_search_verification": "UNVERIFIED",
        "final_verification": "VERIFIED",
        "claim_uri": claim_uri,
        "candidate_uri": candidate_uri,
        "evidence_uri": witness_uri,
        "verification_record_uri": verified.assurance.verification_record_uri,
        "witness_summary": "omitted path",
        "limitations": ["one direct witness only"],
        "feedback": _feedback(),
    }

    score = score_run(
        case,
        report,
        state_dir=tmp_path,
        tool_calls=case["required_tools"],
        capability_ids=case["required_capability_ids"],
    )

    assert score["passed"] is True
    assert score["checks"] == [
        "agent assurance labels",
        "structured agent feedback",
        "required MCP tool sequence",
        "required capability composition",
        "known case claim and candidate",
        "known-answer evidence and verification record",
        "claim, candidate, semantics, and evidence bindings",
    ]


def test_known_answer_scorer_accepts_verified_positive_witness(
    tmp_path: Path,
) -> None:
    load_cases = cast(Any, BENCHMARK["load_cases"])
    score_run = cast(Any, BENCHMARK["score_run"])
    case = next(case for case in load_cases(["GRAPH-BIP-TRUE-001"]) if case["case_id"])
    kernel = JacobianKernel(tmp_path, install_references=True)
    reference = kernel.references["graph_paths"]
    claim = _invoke(
        kernel,
        "artifact.put",
        {
            "schema_uri": reference.claim_schema_uri,
            "semantics_uri": reference.semantics_uri,
            "payload": {
                "claim_schema_version": "1",
                "domain_id": reference.domain_id,
                "domain_version": reference.domain_version,
                "semantics_uri": reference.semantics_uri,
                "quantifiers": [],
                "predicate": {"name": "is_bipartite", "parameters": {}},
                "bounds": {},
                "required_capabilities": ["Evaluator", "WitnessOracle"],
                "correspondence_status": "HUMAN_REVIEWED",
            },
        },
    )
    claim_uri = claim.output["artifact_uri"]
    candidate = _invoke(
        kernel,
        "artifact.put",
        {
            "schema_uri": reference.candidate_schema_uri,
            "semantics_uri": reference.semantics_uri,
            "payload": {
                "vertices": ["a", "b", "c", "d"],
                "arcs": [["a", "b"], ["b", "c"], ["c", "d"], ["d", "a"]],
            },
            "parents": [claim_uri],
        },
    )
    candidate_uri = candidate.output["artifact_uri"]
    validation = _invoke(
        kernel,
        "claim.validate",
        {"claim_uri": claim_uri, "plugin_id": reference.plugin_id},
    )
    assert validation.output["valid"] is True
    _invoke(
        kernel,
        "evaluate.batch",
        {
            "claim_uri": claim_uri,
            "candidate_uris": [candidate_uri],
            "plugin_id": reference.plugin_id,
            "profile": "FAST",
            "seed": 0,
            "wall_seconds": 30,
        },
    )
    found = _invoke(
        kernel,
        "witness.find",
        {
            "claim_uri": claim_uri,
            "candidate_uri": candidate_uri,
            "plugin_id": reference.plugin_id,
            "witness_role": WitnessRole.SUPPORTS_CLAIM.value,
            "wall_seconds": 30,
        },
    )
    witness_uri = found.output["witness_uri"]
    assert witness_uri is not None
    verified = _invoke(
        kernel,
        "witness.verify",
        {
            "claim_uri": claim_uri,
            "candidate_uri": candidate_uri,
            "witness_uri": witness_uri,
            "checker_id": reference.witness_checker_ids["graph.2coloring"],
        },
        mode=CapabilityMode.VERIFY,
    )
    assert verified.assurance.verification_record_uri is not None
    report = {
        "case_id": case["case_id"],
        "conclusion": "TRUE",
        "evaluation_verification": "UNVERIFIED",
        "witness_search_verification": "UNVERIFIED",
        "final_verification": "VERIFIED",
        "claim_uri": claim_uri,
        "candidate_uri": candidate_uri,
        "evidence_uri": witness_uri,
        "verification_record_uri": verified.assurance.verification_record_uri,
        "witness_summary": "complete two-coloring",
        "limitations": ["exact finite graph only"],
        "feedback": _feedback(),
    }

    score = score_run(
        case,
        report,
        state_dir=tmp_path,
        tool_calls=case["required_tools"],
        capability_ids=case["required_capability_ids"],
    )

    assert score["passed"] is True


@pytest.mark.integration
@pytest.mark.skipif(
    shutil.which("lean") is None,
    reason="Lean is not installed",
)
def test_known_answer_scorer_accepts_bound_lean_certificate(
    tmp_path: Path,
) -> None:
    load_cases = cast(Any, BENCHMARK["load_cases"])
    score_run = cast(Any, BENCHMARK["score_run"])
    case = next(
        case for case in load_cases(["LEAN-NAT-INDUCTION-001"]) if case["case_id"]
    )
    kernel = JacobianKernel(tmp_path, install_references=True)
    assert kernel.lean is not None
    verified = kernel.lean.verify(
        statement="∀ n : Nat, n + 0 = n",
        proof=(
            "intro n\n"
            "induction n with\n"
            "| zero => rfl\n"
            "| succ n ih => exact congrArg Nat.succ ih"
        ),
    )
    assert verified.result.verification_record_uri is not None
    report = {
        "case_id": case["case_id"],
        "conclusion": "TRUE",
        "evaluation_verification": "UNVERIFIED",
        "witness_search_verification": "UNVERIFIED",
        "final_verification": "VERIFIED",
        "claim_uri": verified.claim_uri,
        "candidate_uri": verified.candidate_uri,
        "evidence_uri": verified.certificate_uri,
        "verification_record_uri": verified.result.verification_record_uri,
        "witness_summary": "Lean kernel certificate",
        "limitations": ["pinned core Lean only"],
        "feedback": _feedback(),
    }

    score = score_run(
        case,
        report,
        state_dir=tmp_path,
        tool_calls=case["required_tools"],
        capability_ids=case["required_capability_ids"],
    )

    assert score["passed"] is True


def test_known_answer_scorer_accepts_bounded_erdos_straus_table(
    tmp_path: Path,
) -> None:
    load_cases = cast(Any, BENCHMARK["load_cases"])
    score_run = cast(Any, BENCHMARK["score_run"])
    case = next(case for case in load_cases(["ERDOS-STRAUS-001"]) if case["case_id"])
    kernel = JacobianKernel(tmp_path, install_references=True)
    reference = kernel.references["erdos_straus"]
    claim = _invoke(
        kernel,
        "artifact.put",
        {
            "schema_uri": reference.claim_schema_uri,
            "semantics_uri": reference.semantics_uri,
            "payload": {
                "claim_schema_version": "1",
                "domain_id": "jacobian.erdos-straus",
                "domain_version": "1",
                "semantics_uri": reference.semantics_uri,
                "quantifiers": [],
                "predicate": {
                    "name": "erdos_straus_range",
                    "parameters": {"lower_bound": 2, "upper_bound": 1000},
                },
                "bounds": {},
                "required_capabilities": ["Evaluator", "WitnessOracle"],
                "correspondence_status": "HUMAN_REVIEWED",
            },
            "summary": "bounded Erdos-Straus claim",
        },
    )
    claim_uri = claim.output["artifact_uri"]
    candidate = _invoke(
        kernel,
        "artifact.put",
        {
            "schema_uri": reference.candidate_schema_uri,
            "semantics_uri": reference.semantics_uri,
            "payload": {"lower_bound": 2, "upper_bound": 1000},
            "parents": [claim_uri],
            "summary": "bounded Erdos-Straus range",
        },
    )
    candidate_uri = candidate.output["artifact_uri"]
    validation = _invoke(
        kernel,
        "claim.validate",
        {"claim_uri": claim_uri, "plugin_id": reference.plugin_id},
    )
    assert validation.output["valid"] is True
    evaluation = _invoke(
        kernel,
        "evaluate.batch",
        {
            "claim_uri": claim_uri,
            "candidate_uris": [candidate_uri],
            "plugin_id": reference.plugin_id,
            "profile": "FAST",
            "seed": 0,
            "wall_seconds": 30,
        },
    )
    found = _invoke(
        kernel,
        "witness.find",
        {
            "claim_uri": claim_uri,
            "candidate_uri": candidate_uri,
            "plugin_id": reference.plugin_id,
            "witness_role": WitnessRole.SUPPORTS_CLAIM.value,
            "wall_seconds": 30,
        },
    )
    witness_uri = found.output["witness_uri"]
    assert witness_uri is not None
    verified = _invoke(
        kernel,
        "witness.verify",
        {
            "claim_uri": claim_uri,
            "candidate_uri": candidate_uri,
            "witness_uri": witness_uri,
            "checker_id": reference.witness_checker_ids[
                "erdos_straus.decomposition_table"
            ],
        },
        mode=CapabilityMode.VERIFY,
    )
    assert evaluation.execution.status.value == "COMPLETED"
    assert found.execution.status.value == "COMPLETED"
    assert verified.assurance.verification_record_uri is not None
    report = {
        "case_id": case["case_id"],
        "conclusion": "TRUE",
        "evaluation_verification": "UNVERIFIED",
        "witness_search_verification": "UNVERIFIED",
        "final_verification": "VERIFIED",
        "claim_uri": claim_uri,
        "candidate_uri": candidate_uri,
        "evidence_uri": witness_uri,
        "verification_record_uri": verified.assurance.verification_record_uri,
        "witness_summary": "complete bounded decomposition table",
        "limitations": ["verified only for 2 <= n <= 1000"],
        "feedback": _feedback(),
    }

    score = score_run(
        case,
        report,
        state_dir=tmp_path,
        tool_calls=case["required_tools"],
        capability_ids=case["required_capability_ids"],
    )

    assert score["passed"] is True
