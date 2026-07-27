from __future__ import annotations

import hashlib
import json
import os
import runpy
from pathlib import Path
from typing import Any, cast

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityInstallTier,
    CapabilityMode,
    CapabilityProviderAvailability,
    CapabilityProviderDigestKind,
    CapabilityProviderRuntime,
    CapabilityRequest,
)
from jacobian.contracts.sat import SatResourceBudget
from jacobian.contracts.smt import SmtResourceBudget
from jacobian.kernel import JacobianKernel

pytestmark = pytest.mark.usefixtures("initialized_kernel_store")

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


def _lean_proof_case() -> dict[str, Any]:
    return {
        "case_id": "LEAN-PRIVATE-TEST-001",
        "version": "1",
        "task_type": "lean_proof",
        "prompt": "Prove the exact private test proposition.",
        "statement": "∀ n : Nat, Nat.gcd n 0 = n",
        "environment": "MATHLIB",
    }


def _write_private_case(tmp_path: Path) -> Path:
    path = tmp_path / "private-case.json"
    path.write_text(json.dumps(_lean_proof_case()), encoding="utf-8")
    return path


def _sat_producer() -> CapabilityProviderRuntime:
    return CapabilityProviderRuntime(
        provider="cadical",
        availability=CapabilityProviderAvailability.AVAILABLE,
        version="3.0.1",
        digest="sha256:" + "d" * 64,
        digest_kind=CapabilityProviderDigestKind.EXECUTABLE,
        platform="linux-x86_64",
        install_tier=CapabilityInstallTier.T2,
        license_id="MIT",
    )


def _smt_producer() -> CapabilityProviderRuntime:
    return CapabilityProviderRuntime(
        provider="cvc5",
        availability=CapabilityProviderAvailability.AVAILABLE,
        version="1.3.4",
        digest="sha256:" + "d" * 64,
        digest_kind=CapabilityProviderDigestKind.PYTHON_DISTRIBUTION_RECORD,
        platform="linux-x86_64",
        install_tier=CapabilityInstallTier.T1,
        license_id="BSD-3-Clause",
        features=("alethe-proof-production",),
        configuration={
            "profile": "jacobian.smtlib2.qf-unsat/v1",
            "proof_format": "cvc5.alethe/1.3.4",
        },
    )


def _install_fake_carcara(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    executable = tmp_path / "carcara"
    executable.write_text(
        (
            "#!/usr/bin/python3\n"
            "import sys\n"
            "if '--version' in sys.argv:\n"
            "    print('carcara 1.1.0 [git master 394edbb]')\n"
            "elif sys.argv[1:] == ['check', '--help']:\n"
            "    print('--strict-parsing --parse-hole-args '\n"
            "          '--allow-int-real-subtyping --expand-let-bindings')\n"
            "else:\n"
            "    print('valid')\n"
        ),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    digest = "sha256:" + hashlib.sha256(executable.read_bytes()).hexdigest()
    executable.with_name("carcara.jacobian-runtime.json").write_text(
        json.dumps(
            {
                "runtime_manifest_version": "1",
                "provider": "carcara",
                "version": "1.1.0",
                "source_repository": "https://github.com/ufmg-smite/carcara",
                "source_commit": "394edbb15ba95c47893f1d821fddde7e016af178",
                "compatible_cvc5_version": "1.3.4",
                "executable_sha256": digest,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")


def _sat_report(
    *,
    case_id: str,
    cnf_uri: str,
    assignment_uri: str | None,
    record_uri: str | None,
    assurance: str,
    final_verification: str,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "status": "SATISFIABLE",
        "conclusion": "TRUE",
        "assurance": assurance,
        "final_verification": final_verification,
        "evidence_kind": "ASSIGNMENT",
        "assignment": {"a": False, "b": True},
        "cnf_uri": cnf_uri,
        "evidence_uri": assignment_uri,
        "verification_record_uri": record_uri,
        "limitations": ["exact supplied CNF only"],
        "feedback": {
            "reasoning_focus": ["distinguish model production from verification"],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }


def _linear_case() -> dict[str, Any]:
    return {
        "case_id": "LINEAR-PRIVATE-TEST-001",
        "version": "1",
        "task_type": "linear_rational_solution",
        "prompt": "Find one exact solution of the supplied rational system.",
        "system": {
            "variables": ["u", "v"],
            "coefficients": {
                "entries": [
                    [
                        {"num": "2", "den": "1"},
                        {"num": "1", "den": "1"},
                    ],
                    [
                        {"num": "1", "den": "1"},
                        {"num": "-1", "den": "1"},
                    ],
                ]
            },
            "rhs": [
                {"num": "5", "den": "1"},
                {"num": "1", "den": "1"},
            ],
        },
    }


def _linear_report(
    *,
    system_uri: str | None,
    solution_uri: str | None,
    record_uri: str | None,
    assurance: str,
    final_verification: str,
) -> dict[str, Any]:
    return {
        "case_id": "LINEAR-PRIVATE-TEST-001",
        "status": "SOLUTION_FOUND",
        "conclusion": "TRUE",
        "solution": [
            {"num": "2", "den": "1"},
            {"num": "1", "den": "1"},
        ],
        "assurance": assurance,
        "final_verification": final_verification,
        "system_uri": system_uri,
        "solution_uri": solution_uri,
        "verification_record_uri": record_uri,
        "limitations": ["one exact vector; no uniqueness claim"],
        "feedback": {
            "reasoning_focus": ["preserve exact variable order"],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }


def _hnf_case() -> dict[str, Any]:
    return {
        "case_id": "HNF-PRIVATE-TEST-001",
        "version": "1",
        "task_type": "matrix_hermite_normal_form",
        "prompt": "Compute the exact row Hermite normal form.",
        "matrix": {
            "entries": [
                ["0", "2", "4"],
                ["0", "6", "8"],
            ]
        },
    }


def _hnf_report(
    *,
    matrix_uri: str | None,
    normal_form_uri: str | None,
    record_uri: str | None,
    assurance: str,
    final_verification: str,
) -> dict[str, Any]:
    return {
        "case_id": "HNF-PRIVATE-TEST-001",
        "status": "NORMAL_FORM_PRODUCED",
        "conclusion": "TRUE",
        "normal_form": [["0", "2", "0"], ["0", "0", "4"]],
        "transformation": [["-2", "1"], ["3", "-1"]],
        "assurance": assurance,
        "final_verification": final_verification,
        "matrix_uri": matrix_uri,
        "normal_form_uri": normal_form_uri,
        "verification_record_uri": record_uri,
        "limitations": ["the exact supplied integer matrix only"],
        "feedback": {
            "reasoning_focus": ["preserve row-HNF and transform conventions"],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }


def _polynomial_normalization_case() -> dict[str, Any]:
    return {
        "case_id": "POLY-NORMALIZE-PRIVATE-TEST-001",
        "version": "1",
        "task_type": "polynomial_expression_normalization",
        "prompt": "Normalize the exact supplied typed polynomial expression.",
        "expression": {
            "variables": ["x", "y"],
            "expression": {
                "kind": "multiply",
                "operands": [
                    {
                        "kind": "add",
                        "operands": [
                            {"kind": "variable", "name": "x"},
                            {"kind": "variable", "name": "y"},
                        ],
                    },
                    {
                        "kind": "add",
                        "operands": [
                            {"kind": "variable", "name": "x"},
                            {
                                "kind": "negate",
                                "operand": {"kind": "variable", "name": "y"},
                            },
                        ],
                    },
                ],
            },
        },
        "expected_normalized": {
            "terms": [
                {
                    "coefficient": {"num": "1", "den": "1"},
                    "exponents": [2, 0],
                },
                {
                    "coefficient": {"num": "-1", "den": "1"},
                    "exponents": [0, 2],
                },
            ]
        },
    }


def _polynomial_normalization_report(
    *,
    expression_uri: str | None,
    normalization_uri: str | None,
    record_uri: str | None,
    assurance: str,
    final_verification: str,
) -> dict[str, Any]:
    return {
        "case_id": "POLY-NORMALIZE-PRIVATE-TEST-001",
        "status": "NORMALIZATION_PRODUCED",
        "conclusion": "TRUE",
        "variables": ["x", "y"],
        "normalized": {
            "terms": [
                {
                    "coefficient": {"num": "1", "den": "1"},
                    "exponents": [2, 0],
                },
                {
                    "coefficient": {"num": "-1", "den": "1"},
                    "exponents": [0, 2],
                },
            ]
        },
        "assurance": assurance,
        "final_verification": final_verification,
        "expression_uri": expression_uri,
        "normalization_uri": normalization_uri,
        "verification_record_uri": record_uri,
        "limitations": ["the exact supplied QQ-polynomial expression only"],
        "feedback": {
            "reasoning_focus": ["preserve the declared variable order"],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }


def test_ab_sat_report_contract_identifies_the_producer_evidence_uri() -> None:
    schema_path = PROJECT_ROOT / "benchmarks" / "ab_cases" / "sat-report.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    description = schema["properties"]["evidence_uri"]["description"]

    assert "assignment_uri from sat.model.find" in description
    assert "proof_uri from sat.unsat_proof.find" in description
    assert "never the verifier's witness_uri or certificate_uri" in description
    assert (
        "Do not substitute the verifier's witness_uri"
        in BENCHMARK["SAT_TREATMENT_INSTRUCTIONS"]
    )
    assert "named assignment map returned" in BENCHMARK["SAT_TREATMENT_INSTRUCTIONS"]
    assert "pre-canonical variable order" in BENCHMARK["SAT_TREATMENT_INSTRUCTIONS"]


def test_ab_smt_task_selects_its_own_control_and_treatment_instructions() -> None:
    select = cast(Any, BENCHMARK["_condition_instructions"])

    control = select("smt_unsat_proof", "control")
    treatment = select("smt_unsat_proof", "treatment")

    assert "SMT-LIB query directly" in control
    assert "smt.unsat_proof.find" in treatment
    assert "smt.unsat_proof.verify" in treatment
    assert "Erdos" not in control
    assert "Erdos" not in treatment


def test_ab_smt_scorer_preserves_rejected_holey_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_carcara(tmp_path, monkeypatch)
    state_dir = tmp_path / "state"
    kernel = JacobianKernel(state_dir, install_references=True)
    text = (
        "(set-logic QF_UF)\n"
        "(declare-sort U 0)\n"
        "(declare-fun a () U)\n"
        "(assert (not (= a a)))\n"
        "(check-sat)\n"
    )
    problem = kernel.smt.put_problem(logic="QF_UF", smtlib_text=text)
    proof = kernel.smt.put_proof(
        problem_uri=problem.artifact_uri,
        proof=b'(\n(step t0 (cl) :rule hole :args ("unsupported"))\n)\n',
        producer=_smt_producer(),
        resource_budget=SmtResourceBudget(wall_seconds=5),
    )
    rejected = kernel.capabilities.invoke(
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
    score_report = cast(Any, BENCHMARK["score_report"])

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
        "mcp_response_bytes": 0,
        "mcp_response_bytes_by_tool": {},
        "repeated_mcp_call_count": 0,
        "repeated_mcp_calls": [],
        "capability_describe_index_calls": 0,
        "capability_describe_exact_calls": 0,
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


def test_agent_eval_is_plan_only_without_explicit_execute(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    main = cast(Any, BENCHMARK["main"])

    def unexpected_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("plan mode started a model evaluation")

    monkeypatch.setitem(main.__globals__, "_run_condition", unexpected_run)

    assert main(["--case", "ERDOS-STRAUS-AB-001"]) == 0

    plan = json.loads(capsys.readouterr().out)
    assert plan["mode"] == "plan"
    assert plan["execution_requested"] is False
    assert plan["model_run_count"] == 2
    assert plan["maximum_model_wall_seconds"] == 1200


def test_agent_eval_requires_explicit_case_selection() -> None:
    main = cast(Any, BENCHMARK["main"])

    with pytest.raises(SystemExit):
        main([])


def test_agent_eval_requires_sufficient_manual_run_budget(tmp_path: Path) -> None:
    main = cast(Any, BENCHMARK["main"])
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
    main = cast(Any, BENCHMARK["main"])
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
def test_lean_ab_scorer_accepts_any_exact_replayable_proof(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    score_report = cast(Any, BENCHMARK["score_report"])
    case = _lean_proof_case()
    state_dir = tmp_path / "state"
    kernel = JacobianKernel(state_dir, install_references=True)
    proof = "intro n\nsimp"
    checked = kernel.capabilities.invoke(
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
        raise BENCHMARK["BenchmarkError"]("replay runtime unavailable")

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
    score_report = cast(Any, BENCHMARK["score_report"])
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
    summarize_pairs = cast(Any, BENCHMARK["summarize_pairs"])
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


@pytest.mark.lean_runtime
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


@pytest.mark.lean_runtime
def test_ab_lean_control_ablation_removes_only_declaration_discovery(
    tmp_path: Path,
) -> None:
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

    assert lean_ids == {
        "lean.check",
        "lean.proof.repair_once",
        "lean.proof_state.apply_tactic",
        "lean.retrieve.premises",
        "lean.statement.compare",
        "lean.statement.propose",
    }
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


def test_ab_sat_scorer_requires_ordered_checker_bound_assignment(
    tmp_path: Path,
) -> None:
    score_report = cast(Any, BENCHMARK["score_report"])
    case = {
        "case_id": "SAT-PRIVATE-TEST-001",
        "version": "1",
        "task_type": "sat_decision",
        "prompt": "Decide the private CNF.",
        "variable_names": ["a", "b"],
        "clauses": [[1, 2], [-1, 2]],
        "expected": {"status": "SATISFIABLE"},
    }
    state_dir = tmp_path / "state"
    kernel = JacobianKernel(state_dir, install_references=True)
    cnf = kernel.sat.put_cnf(
        variable_names=("a", "b"),
        clauses=((1, 2), (-1, 2)),
    )
    assignment = kernel.sat.put_assignment(
        cnf_uri=cnf.artifact_uri,
        values=(False, True),
        producer=_sat_producer(),
        resource_budget=SatResourceBudget(wall_seconds=5),
    )
    verified = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="sat.model.verify",
            mode=CapabilityMode.VERIFY,
            input={"assignment_uri": assignment.artifact_uri},
        )
    )
    record_uri = verified.assurance.verification_record_uri
    assert record_uri is not None

    control = score_report(
        case,
        _sat_report(
            case_id=str(case["case_id"]),
            cnf_uri=cnf.artifact_uri,
            assignment_uri=None,
            record_uri=None,
            assurance="SELF_CHECKED",
            final_verification="UNVERIFIED",
        ),
        condition="control",
        state_dir=state_dir,
        mcp_calls=[],
    )
    assert control["passed"] is True

    treatment = score_report(
        case,
        _sat_report(
            case_id=str(case["case_id"]),
            cnf_uri=cnf.artifact_uri,
            assignment_uri=assignment.artifact_uri,
            record_uri=record_uri,
            assurance="VERIFIED",
            final_verification="VERIFIED",
        ),
        condition="treatment",
        state_dir=state_dir,
        mcp_calls=["capability.invoke"],
        capability_invocations=[
            {
                "capability_id": "sat.model.find",
                "input": {
                    "cnf_uri": cnf.artifact_uri,
                    "resource_budget": {"wall_seconds": 5},
                },
                "output": {
                    "cnf_uri": cnf.artifact_uri,
                    "assignment_uri": assignment.artifact_uri,
                },
                "artifact_uris": [assignment.artifact_uri],
            },
            {
                "capability_id": "sat.model.verify",
                "input": {"assignment_uri": assignment.artifact_uri},
                "output": verified.output,
                "artifact_uris": verified.artifact_uris,
                "assurance": verified.assurance.model_dump(mode="json"),
            },
        ],
    )
    assert treatment["passed"] is True
    assert treatment["false_certification"] is False
    assert treatment["replay_success"] is True


def test_ab_linear_scorer_requires_ordered_checker_bound_solution(
    tmp_path: Path,
) -> None:
    score_report = cast(Any, BENCHMARK["score_report"])
    case = _linear_case()
    state_dir = tmp_path / "state"
    kernel = JacobianKernel(state_dir, install_references=True)
    found = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="linear.rational_solution.find",
            mode=CapabilityMode.EXPLORE,
            input={"system": case["system"]},
        )
    )
    solution_uri = cast(str, found.output["solution_uri"])
    system_uri = cast(str, found.output["system_uri"])
    verified = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="linear.rational_solution.verify",
            mode=CapabilityMode.VERIFY,
            input={"solution_uri": solution_uri},
        )
    )
    record_uri = verified.assurance.verification_record_uri
    assert record_uri is not None

    control = score_report(
        case,
        _linear_report(
            system_uri=None,
            solution_uri=None,
            record_uri=None,
            assurance="SELF_CHECKED",
            final_verification="UNVERIFIED",
        ),
        condition="control",
        state_dir=state_dir,
        mcp_calls=[],
    )
    assert control["passed"] is True

    treatment = score_report(
        case,
        _linear_report(
            system_uri=system_uri,
            solution_uri=solution_uri,
            record_uri=record_uri,
            assurance="VERIFIED",
            final_verification="VERIFIED",
        ),
        condition="treatment",
        state_dir=state_dir,
        mcp_calls=["capability.invoke"],
        capability_invocations=[
            {
                "capability_id": "linear.rational_solution.find",
                "input": {"system": case["system"]},
                "output": found.output,
                "artifact_uris": found.artifact_uris,
            },
            {
                "capability_id": "linear.rational_solution.verify",
                "input": {"solution_uri": solution_uri},
                "output": verified.output,
                "artifact_uris": verified.artifact_uris,
                "assurance": verified.assurance.model_dump(mode="json"),
            },
        ],
    )

    assert treatment["passed"] is True
    assert treatment["false_certification"] is False
    assert treatment["replay_success"] is True

    wrong = _linear_report(
        system_uri=None,
        solution_uri=None,
        record_uri=None,
        assurance="SELF_CHECKED",
        final_verification="UNVERIFIED",
    )
    wrong["solution"][0] = {"num": "0", "den": "1"}
    with pytest.raises(
        cast(type[Exception], BENCHMARK["BenchmarkError"]),
        match="does not satisfy",
    ):
        score_report(
            case,
            wrong,
            condition="control",
            state_dir=state_dir,
            mcp_calls=[],
        )


def test_ab_hnf_scorer_requires_bound_independently_replayed_evidence(
    tmp_path: Path,
) -> None:
    score_report = cast(Any, BENCHMARK["score_report"])
    case = _hnf_case()
    state_dir = tmp_path / "state"
    kernel = JacobianKernel(state_dir, install_references=True)
    computed = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.normal_form.hermite",
            mode=CapabilityMode.EXPLORE,
            input={"matrix": case["matrix"]},
        )
    )
    normal_form_uri = cast(str, computed.output["normal_form_uri"])
    matrix_uri = cast(str, computed.output["matrix_uri"])
    verified = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.normal_form.hermite.verify",
            mode=CapabilityMode.VERIFY,
            input={"normal_form_uri": normal_form_uri},
        )
    )
    record_uri = verified.assurance.verification_record_uri
    assert record_uri is not None

    control = score_report(
        case,
        _hnf_report(
            matrix_uri=None,
            normal_form_uri=None,
            record_uri=None,
            assurance="SELF_CHECKED",
            final_verification="UNVERIFIED",
        ),
        condition="control",
        state_dir=state_dir,
        mcp_calls=[],
    )
    assert control["passed"] is True

    treatment = score_report(
        case,
        _hnf_report(
            matrix_uri=matrix_uri,
            normal_form_uri=normal_form_uri,
            record_uri=record_uri,
            assurance="VERIFIED",
            final_verification="VERIFIED",
        ),
        condition="treatment",
        state_dir=state_dir,
        mcp_calls=["capability.invoke"],
        capability_invocations=[
            {
                "capability_id": "matrix.normal_form.hermite",
                "input": {"matrix": case["matrix"]},
                "output": computed.output,
                "artifact_uris": computed.artifact_uris,
            },
            {
                "capability_id": "matrix.normal_form.hermite.verify",
                "input": {"normal_form_uri": normal_form_uri},
                "output": verified.output,
                "artifact_uris": verified.artifact_uris,
                "assurance": verified.assurance.model_dump(mode="json"),
            },
        ],
    )

    assert treatment["passed"] is True
    assert treatment["false_certification"] is False
    assert treatment["replay_success"] is True

    wrong = _hnf_report(
        matrix_uri=None,
        normal_form_uri=None,
        record_uri=None,
        assurance="SELF_CHECKED",
        final_verification="UNVERIFIED",
    )
    wrong["transformation"][0][0] = "0"
    with pytest.raises(
        cast(type[Exception], BENCHMARK["BenchmarkError"]),
        match="independent exact oracle",
    ):
        score_report(
            case,
            wrong,
            condition="control",
            state_dir=state_dir,
            mcp_calls=[],
        )


def test_ab_polynomial_normalization_scorer_requires_bound_replay(
    tmp_path: Path,
) -> None:
    score_report = cast(Any, BENCHMARK["score_report"])
    case = _polynomial_normalization_case()
    state_dir = tmp_path / "state"
    kernel = JacobianKernel(state_dir, install_references=True)
    computed = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.expression.normalize",
            mode=CapabilityMode.EXPLORE,
            input={"expression": case["expression"]},
        )
    )
    expression_uri = cast(str, computed.output["expression_uri"])
    normalization_uri = cast(str, computed.output["normalization_uri"])
    verified = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.expression_normalization.verify",
            mode=CapabilityMode.VERIFY,
            input={"normalization_uri": normalization_uri},
        )
    )
    record_uri = verified.assurance.verification_record_uri
    assert record_uri is not None

    control = score_report(
        case,
        _polynomial_normalization_report(
            expression_uri=None,
            normalization_uri=None,
            record_uri=None,
            assurance="SELF_CHECKED",
            final_verification="UNVERIFIED",
        ),
        condition="control",
        state_dir=state_dir,
        mcp_calls=[],
    )
    assert control["passed"] is True

    treatment = score_report(
        case,
        _polynomial_normalization_report(
            expression_uri=expression_uri,
            normalization_uri=normalization_uri,
            record_uri=record_uri,
            assurance="VERIFIED",
            final_verification="VERIFIED",
        ),
        condition="treatment",
        state_dir=state_dir,
        mcp_calls=["capability.invoke"],
        capability_invocations=[
            {
                "capability_id": "polynomial.expression.normalize",
                "input": {"expression": case["expression"]},
                "output": computed.output,
                "artifact_uris": computed.artifact_uris,
            },
            {
                "capability_id": "polynomial.expression_normalization.verify",
                "input": {"normalization_uri": normalization_uri},
                "output": verified.output,
                "artifact_uris": verified.artifact_uris,
                "assurance": verified.assurance.model_dump(mode="json"),
            },
        ],
    )

    assert treatment["passed"] is True
    assert treatment["false_certification"] is False
    assert treatment["replay_success"] is True

    wrong = _polynomial_normalization_report(
        expression_uri=None,
        normalization_uri=None,
        record_uri=None,
        assurance="SELF_CHECKED",
        final_verification="UNVERIFIED",
    )
    wrong["normalized"]["terms"][1]["coefficient"]["num"] = "-2"
    with pytest.raises(
        cast(type[Exception], BENCHMARK["BenchmarkError"]),
        match="held-out exact oracle",
    ):
        score_report(
            case,
            wrong,
            condition="control",
            state_dir=state_dir,
            mcp_calls=[],
        )


def test_ab_sat_scorer_rejects_unbound_verified_claim(tmp_path: Path) -> None:
    score_report = cast(Any, BENCHMARK["score_report"])
    benchmark_error = cast(type[Exception], BENCHMARK["BenchmarkError"])
    case = {
        "case_id": "SAT-PRIVATE-TEST-002",
        "version": "1",
        "task_type": "sat_decision",
        "prompt": "Decide the private CNF.",
        "variable_names": ["a"],
        "clauses": [[1]],
        "expected": {"status": "SATISFIABLE"},
    }
    state_dir = tmp_path / "state"
    kernel = JacobianKernel(state_dir, install_references=True)
    cnf = kernel.sat.put_cnf(variable_names=("a",), clauses=((1,),))
    report = _sat_report(
        case_id=str(case["case_id"]),
        cnf_uri=cnf.artifact_uri,
        assignment_uri="artifact://sha256/" + "a" * 64,
        record_uri=None,
        assurance="VERIFIED",
        final_verification="VERIFIED",
    )
    report["assignment"] = {"a": True}

    with pytest.raises(benchmark_error, match="not independently verified"):
        score_report(
            case,
            report,
            condition="treatment",
            state_dir=state_dir,
            mcp_calls=["capability.invoke"],
            capability_invocations=[],
        )
