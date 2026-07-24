from __future__ import annotations

import json
import runpy
from pathlib import Path
from typing import Any, cast

from jacobian.contracts.evidence import WitnessRole
from jacobian.kernel import JacobianKernel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = runpy.run_path(str(PROJECT_ROOT / "benchmarks" / "agent_mcp.py"))


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
            "type": "turn.completed",
            "usage": {"input_tokens": 12, "output_tokens": 3},
        },
    ]
    transcript.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    calls, usage = parse_transcript(transcript)

    assert calls == ["artifact.put"]
    assert usage == {"input_tokens": 12, "output_tokens": 3}


def test_known_answer_scorer_replays_durable_witness_bindings(
    tmp_path: Path,
) -> None:
    load_cases = cast(Any, BENCHMARK["load_cases"])
    score_run = cast(Any, BENCHMARK["score_run"])
    case = next(case for case in load_cases(["PATH-CLOSURE-001"]) if case["case_id"])
    kernel = JacobianKernel(tmp_path, install_references=True)
    reference = kernel.references["graph_paths"]
    claim = kernel.artifacts.put(
        schema_uri=reference.claim_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={
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
    )
    candidate = kernel.artifacts.put(
        schema_uri=reference.candidate_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={
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
    )
    found = kernel.witnesses.find(
        claim_uri=claim.artifact_uri,
        candidate_uri=candidate.artifact_uri,
        plugin_id=reference.plugin_id,
        witness_role=WitnessRole.DEFEATS_CANDIDATE,
        wall_seconds=30,
    )
    assert found.witness_uri is not None
    verified = kernel.verification.verify_witness(
        claim_uri=claim.artifact_uri,
        candidate_uri=candidate.artifact_uri,
        witness_uri=found.witness_uri,
        checker_id=reference.witness_checker_ids["graph.omitted_path"],
    )
    assert verified.verification_record_uri is not None
    report = {
        "case_id": case["case_id"],
        "conclusion": "FALSE",
        "evaluation_verification": "UNVERIFIED",
        "witness_search_verification": "UNVERIFIED",
        "final_verification": "VERIFIED",
        "claim_uri": claim.artifact_uri,
        "candidate_uri": candidate.artifact_uri,
        "evidence_uri": found.witness_uri,
        "verification_record_uri": verified.verification_record_uri,
        "witness_summary": "omitted path",
        "limitations": ["one direct witness only"],
    }

    score = score_run(
        case,
        report,
        state_dir=tmp_path,
        tool_calls=case["required_tools"],
    )

    assert score["passed"] is True
    assert score["checks"] == [
        "agent assurance labels",
        "required MCP tool sequence",
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
    claim = kernel.artifacts.put(
        schema_uri=reference.claim_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={
            "claim_schema_version": "1",
            "domain_id": reference.domain_id,
            "domain_version": reference.domain_version,
            "semantics_uri": reference.semantics_uri,
            "quantifiers": [],
            "predicate": {
                "name": "is_bipartite",
                "parameters": {},
            },
            "bounds": {},
            "required_capabilities": ["Evaluator", "WitnessOracle"],
            "correspondence_status": "HUMAN_REVIEWED",
        },
    )
    candidate = kernel.artifacts.put(
        schema_uri=reference.candidate_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={
            "vertices": ["a", "b", "c", "d"],
            "arcs": [["a", "b"], ["b", "c"], ["c", "d"], ["d", "a"]],
        },
    )
    found = kernel.witnesses.find(
        claim_uri=claim.artifact_uri,
        candidate_uri=candidate.artifact_uri,
        plugin_id=reference.plugin_id,
        witness_role=WitnessRole.SUPPORTS_CLAIM,
        wall_seconds=30,
    )
    assert found.witness_uri is not None
    verified = kernel.verification.verify_witness(
        claim_uri=claim.artifact_uri,
        candidate_uri=candidate.artifact_uri,
        witness_uri=found.witness_uri,
        checker_id=reference.witness_checker_ids["graph.2coloring"],
    )
    assert verified.verification_record_uri is not None
    report = {
        "case_id": case["case_id"],
        "conclusion": "TRUE",
        "evaluation_verification": "UNVERIFIED",
        "witness_search_verification": "UNVERIFIED",
        "final_verification": "VERIFIED",
        "claim_uri": claim.artifact_uri,
        "candidate_uri": candidate.artifact_uri,
        "evidence_uri": found.witness_uri,
        "verification_record_uri": verified.verification_record_uri,
        "witness_summary": "complete two-coloring",
        "limitations": ["exact finite graph only"],
    }

    score = score_run(
        case,
        report,
        state_dir=tmp_path,
        tool_calls=case["required_tools"],
    )

    assert score["passed"] is True


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
    }

    score = score_run(
        case,
        report,
        state_dir=tmp_path,
        tool_calls=case["required_tools"],
    )

    assert score["passed"] is True
