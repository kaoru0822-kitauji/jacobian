"""Run model-in-the-loop Jacobian capability evaluations.

This benchmark measures whether Jacobian changes agent outcomes. It is
separate from ``agent_mcp.py``, which validates MCP and checker integration.

Preview a one-pair pilot with:

    uv run python benchmarks/agent_ab.py --case ERDOS-STRAUS-AB-001

Execute it only after reviewing the printed plan:

    uv run python benchmarks/agent_ab.py \
        --case ERDOS-STRAUS-AB-001 \
        --execute \
        --max-model-runs 2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import statistics
import subprocess
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any, cast

from jacobian.artifacts import ArtifactService
from jacobian.contracts.capabilities import CapabilityMode, CapabilityRequest
from jacobian.contracts.sat import (
    CanonicalCnf,
    SatAssignmentArtifact,
    SatProofArtifact,
    canonicalize_cnf,
)
from jacobian.contracts.verification import VerificationRecord
from jacobian.eval_graph_oracle import (
    GraphOracleError,
    check_constraints,
    check_reported_properties,
    compute_properties,
    normalize_graph,
)
from jacobian.eval_telemetry import parse_agent_transcript as parse_transcript
from jacobian.kernel import JacobianKernel
from jacobian.sat import install_sat_artifacts
from jacobian.schema_registry import SchemaRegistry, SchemaRegistryError
from jacobian.store import ArtifactStore, StoreError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_ROOT = Path(__file__).with_name("ab_cases")
REPORT_SCHEMA = CASES_ROOT / "report.schema.json"
GRAPH_REPORT_SCHEMA = CASES_ROOT / "graph-report.schema.json"
PARTITION_REPORT_SCHEMA = CASES_ROOT / "partition-report.schema.json"
SAT_REPORT_SCHEMA = CASES_ROOT / "sat-report.schema.json"
LEAN_DECLARATION_REPORT_SCHEMA = CASES_ROOT / "lean-report.schema.json"
LEAN_PROOF_REPORT_SCHEMA = CASES_ROOT / "lean-proof-report.schema.json"
DEFAULT_RESULTS_ROOT = Path(__file__).with_name("results") / "ab"
CONDITIONS = ("control", "treatment")
LEAN_DISCOVERY_IDS = frozenset(
    {
        "lean.declaration.search",
        "lean.declaration.inspect",
    }
)
SAT_CAPABILITY_IDS = frozenset(
    {
        "sat.model.find",
        "sat.model.verify",
        "sat.unsat_proof.find",
        "sat.unsat_proof.verify",
    }
)
LEAN_PROOF_CONDITIONS = ("baseline", "tactic", "retrieval", "combined")
LEAN_PROOF_CAPABILITY_EXCLUSIONS = {
    "baseline": ("lean.proof_state.apply_tactic", "lean.retrieve.premises"),
    "tactic": ("lean.retrieve.premises",),
    "retrieval": ("lean.proof_state.apply_tactic",),
    "combined": (),
}

COMMON_PROMPT = """\
Complete mathematical evaluation case {case_id}.

{prompt}

Return only the required JSON report. Record what work concerned mathematical
strategy in feedback.reasoning_focus, what work concerned constructing or
operating infrastructure in feedback.infrastructure_work, and missing
capabilities in feedback.tooling_gaps. Empty lists are valid. Do not claim
anything beyond the exact declared scope.
"""

CONTROL_INSTRUCTIONS = """\
Jacobian and all MCP servers are unavailable in this condition. You may create
and run local code in the empty workspace to perform the finite check. Report
assurance as SELF_CHECKED and verification_record_uri as null.
"""

TREATMENT_INSTRUCTIONS = """\
Use the jacobian_local MCP server for all mathematical computation. Do not use
shell commands or create programs. Inspect the capability and reference
catalogs, then compose the available atomic operations to materialize the
bounded Erdos-Straus claim and candidate for 2 <= n <= 120, validate the claim,
evaluate the candidate, find a supporting witness, and independently verify
that witness. Preserve the intermediate artifact URIs. Report VERIFIED only if
the final checker-backed capability returns that assurance, and copy its exact
verification_record_uri.
"""

GRAPH_CONTROL_INSTRUCTIONS = """\
Jacobian and all MCP servers are unavailable. You may write and run local code
in the empty workspace. Return one explicit simple undirected graph satisfying
the constraints. Report SELF_CHECKED, UNVERIFIED, and null artifact URIs.
Set graph-property fields not requested by the case to null.
"""

GRAPH_TREATMENT_INSTRUCTIONS = """\
Use only jacobian_local for mathematical computation. Do not use shell commands
or create programs. Describe and invoke graph.search.atlas, then invoke
graph.compute.properties on one returned graph. Return that graph and its exact
properties. Copy the exact inline graph payload returned by graph.search.atlas;
do not substitute an isomorphic relabeling. Report COMPUTED, UNVERIFIED, and the
durable graph/property URIs.
Set graph-property fields not requested by the case to null.
"""

PARTITION_CONTROL_INSTRUCTIONS = """\
Jacobian and all MCP servers are unavailable. Construct the requested cases
directly. Report SELF_CHECKED, UNVERIFIED, and null artifact URIs.
"""

PARTITION_TREATMENT_INSTRUCTIONS = """\
Use only jacobian_local for mathematical work. Describe and invoke
case.partition.finite in VERIFY mode with the exact universe and cases. Do not
use shell commands or create programs. Copy the returned durable URIs. Report
VERIFIED only when the capability returns VERIFIED assurance.
"""

SAT_CONTROL_INSTRUCTIONS = """\
Jacobian and all MCP servers are unavailable. You may write and run local code
in the empty workspace. Decide the exact supplied CNF directly. A satisfying
assignment is acceptable evidence for SAT; do not invent an UNSAT certificate.
Report SELF_CHECKED and UNVERIFIED, with null durable evidence and verification
record URIs.
"""

SAT_TREATMENT_INSTRUCTIONS = """\
Use only jacobian_local for mathematical work. Do not use shell commands or
create programs. The exact canonical CNF has already been materialized at the
URI supplied below. Inspect the installed catalog, then compose the appropriate
SAT evidence producer and its independent verifier. A solver status, failed
search, assignment artifact, or proof artifact alone is not verification.
Report VERIFIED only when the matching verify capability returns VERIFIED and
copy its exact verification-record URI. Set evidence_uri to the producer output
passed into that verifier: assignment_uri from sat.model.find or proof_uri from
sat.unsat_proof.find. Do not substitute the verifier's witness_uri or
certificate_uri. For a SAT assignment, read the assignment artifact through its
artifact:// resource to copy the variable values; artifact.get is not a
capability.
"""

LEAN_DECLARATION_INSTRUCTIONS = """\
Use only the jacobian_local MCP server for mathematical work. Do not use shell
commands or create programs. Inspect the installed capability catalog, construct
a Lean proof body for the exact MATHLIB statement, and independently replay it
with lean.check in VERIFY mode. The proof field is the body consumed by
lean.check, without a leading `by`. List declarations explicitly cited by that
body. Report VERIFIED only when lean.check returns VERIFIED assurance, and copy
its exact verification_record_uri. Retrieval or inspection alone is not
verification.
"""

LEAN_PROOF_INSTRUCTIONS = """\
Use only jacobian_local for mathematical work. Do not use shell commands or
create files. Inspect the installed capability catalog and use the available
capabilities as you judge useful. The catalog deliberately varies by condition.
Report TRUE and VERIFIED only if lean.check accepts the exact statement and
proof and returns a verification_record_uri. Otherwise report UNKNOWN and
UNVERIFIED. Public examples are not evaluation answers.
"""


class BenchmarkError(RuntimeError):
    """The A/B runner, report, or known-answer evidence is invalid."""


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BenchmarkError(f"{path} must contain a JSON object")
    return payload


def load_cases(
    selected: Sequence[str],
    case_files: Sequence[Path] = (),
) -> list[dict[str, Any]]:
    public_paths = [
        path
        for path in sorted(CASES_ROOT.glob("*.json"))
        if not path.name.endswith(".schema.json")
    ]
    external_paths = [path.resolve() for path in case_files]
    cases = []
    for path in (*public_paths, *external_paths):
        case = _load_json_object(path)
        case["_case_path"] = str(path.resolve())
        cases.append(case)
    indexed = {str(case.get("case_id")): case for case in cases}
    if len(indexed) != len(cases):
        raise BenchmarkError("A/B case IDs must be unique")
    external_ids = [str(case.get("case_id")) for case in cases[len(public_paths) :]]
    if not selected and not external_ids:
        raise BenchmarkError(
            "select a case with --case or --case-file, or explicitly use --case all"
        )
    if "all" in selected and selected != ["all"]:
        raise BenchmarkError("--case all cannot be combined with named cases")
    if selected == ["all"]:
        return cases
    requested = list(dict.fromkeys([*selected, *external_ids]))
    missing = sorted(set(requested) - set(indexed))
    if missing:
        raise BenchmarkError(f"unknown A/B cases: {', '.join(missing)}")
    return [indexed[case_id] for case_id in requested]


def _sat_case_cnf(case: Mapping[str, Any]) -> CanonicalCnf:
    variable_names = case.get("variable_names")
    clauses = case.get("clauses")
    if (
        not isinstance(variable_names, list)
        or not all(isinstance(name, str) for name in variable_names)
        or not isinstance(clauses, list)
        or not all(isinstance(clause, list) for clause in clauses)
    ):
        raise BenchmarkError("SAT case must contain variable_names and clauses")
    try:
        return canonicalize_cnf(variable_names=variable_names, clauses=clauses)
    except ValueError as exc:
        raise BenchmarkError("SAT case contains an invalid CNF") from exc


def _seed_sat_case(case: Mapping[str, Any], state_dir: Path) -> str:
    cnf = _sat_case_cnf(case)
    store = ArtifactStore(state_dir)
    schemas = SchemaRegistry(store)
    artifacts = ArtifactService(store, schemas)
    sat = install_sat_artifacts(store, schemas, artifacts)
    stored = sat.put_cnf(
        variable_names=tuple(variable.name for variable in cnf.variables),
        clauses=tuple(clause.literals for clause in cnf.clauses),
    )
    return stored.artifact_uri


def _sat_assignment_satisfies(
    cnf: CanonicalCnf,
    assignment: Mapping[str, bool],
) -> bool:
    names = {variable.id: variable.name for variable in cnf.variables}
    return all(
        any(
            assignment[names[abs(literal)]]
            if literal > 0
            else not assignment[names[abs(literal)]]
            for literal in clause.literals
        )
        for clause in cnf.clauses
    )


def _sat_hidden_status(cnf: CanonicalCnf) -> str:
    if len(cnf.variables) > 20:
        raise BenchmarkError("held-out SAT oracle is limited to 20 variables")
    names = tuple(variable.name for variable in cnf.variables)
    for values in product((False, True), repeat=len(names)):
        assignment = dict(zip(names, values, strict=True))
        if _sat_assignment_satisfies(cnf, assignment):
            return "SATISFIABLE"
    return "UNSATISFIABLE"


def _reported_sat_assignment(
    report: Mapping[str, Any],
    *,
    cnf: CanonicalCnf,
    hidden_status: str,
) -> dict[str, bool] | None:
    assignment_value = report.get("assignment")
    if hidden_status != "SATISFIABLE":
        if assignment_value is not None:
            raise BenchmarkError("UNSAT report must not contain an assignment")
        return None
    if not isinstance(assignment_value, Mapping) or not all(
        isinstance(name, str) and isinstance(value, bool)
        for name, value in assignment_value.items()
    ):
        raise BenchmarkError("SAT report omitted a Boolean assignment")
    assignment = dict(assignment_value)
    if set(assignment) != {
        variable.name for variable in cnf.variables
    } or not _sat_assignment_satisfies(cnf, assignment):
        raise BenchmarkError("SAT report assignment does not satisfy the exact CNF")
    if report.get("evidence_kind") != "ASSIGNMENT":
        raise BenchmarkError("SAT report mislabeled its assignment evidence")
    return assignment


def _score_sat_report(
    case: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    condition: str,
    state_dir: Path,
    mcp_calls: Sequence[str],
    capability_invocations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    expected = case.get("expected")
    if not isinstance(expected, Mapping):
        raise BenchmarkError("SAT expected must be an object")
    expected_cnf = _sat_case_cnf(case)
    hidden_status = _sat_hidden_status(expected_cnf)
    if expected.get("status") != hidden_status:
        raise BenchmarkError("SAT case expectation differs from the hidden oracle")
    if (
        report.get("case_id") != case.get("case_id")
        or report.get("status") != hidden_status
        or report.get("conclusion") != "TRUE"
    ):
        raise BenchmarkError("SAT report has the wrong case, status, or conclusion")
    _validate_feedback(report.get("feedback"))

    cnf_uri = report.get("cnf_uri")
    if not isinstance(cnf_uri, str):
        raise BenchmarkError("SAT report omitted its canonical CNF URI")
    store = ArtifactStore(state_dir)
    try:
        cnf_artifact = store.get(cnf_uri)
        schemas = SchemaRegistry(store)
        schemas.validate(cnf_artifact.manifest.schema_uri, cnf_artifact.payload)
        durable_cnf = CanonicalCnf.model_validate(cnf_artifact.payload)
    except (SchemaRegistryError, StoreError, ValueError) as exc:
        raise BenchmarkError("SAT canonical CNF artifact is unavailable") from exc
    if durable_cnf != expected_cnf:
        raise BenchmarkError("SAT durable CNF differs from the held-out case")

    reported_assignment = _reported_sat_assignment(
        report,
        cnf=durable_cnf,
        hidden_status=hidden_status,
    )

    evidence_uri = report.get("evidence_uri")
    record_uri = report.get("verification_record_uri")
    if condition == "control":
        if mcp_calls:
            raise BenchmarkError("SAT control condition used an MCP tool")
        if (
            report.get("assurance") != "SELF_CHECKED"
            or report.get("final_verification") != "UNVERIFIED"
            or evidence_uri is not None
            or record_uri is not None
        ):
            raise BenchmarkError("SAT control condition falsely projected verification")
        expected_kind = "ASSIGNMENT" if hidden_status == "SATISFIABLE" else "NONE"
        if report.get("evidence_kind") != expected_kind:
            raise BenchmarkError("SAT control report has the wrong evidence kind")
        return {
            "passed": True,
            "false_certification": False,
            "checks": ["hidden exact SAT oracle", "control isolation"],
        }
    if condition != "treatment":
        raise BenchmarkError(f"unknown condition: {condition}")
    if (
        report.get("assurance") != "VERIFIED"
        or report.get("final_verification") != "VERIFIED"
        or not isinstance(evidence_uri, str)
        or not isinstance(record_uri, str)
    ):
        raise BenchmarkError("SAT treatment was not independently verified")

    find_id = (
        "sat.model.find" if hidden_status == "SATISFIABLE" else "sat.unsat_proof.find"
    )
    verify_id = (
        "sat.model.verify"
        if hidden_status == "SATISFIABLE"
        else "sat.unsat_proof.verify"
    )
    evidence_field = "assignment_uri" if hidden_status == "SATISFIABLE" else "proof_uri"
    expected_kind = "ASSIGNMENT" if hidden_status == "SATISFIABLE" else "UNSAT_PROOF"
    if report.get("evidence_kind") != expected_kind:
        raise BenchmarkError("SAT treatment reported the wrong evidence kind")

    try:
        evidence_artifact = store.get(evidence_uri)
        record_artifact = store.get(record_uri)
        record = VerificationRecord.model_validate(record_artifact.payload)
        checker_evidence = store.get(record.evidence_uri)
        semantics = store.get(cnf_artifact.manifest.semantics_uri)
        schemas.validate(
            evidence_artifact.manifest.schema_uri,
            evidence_artifact.payload,
        )
        schemas.validate(record_artifact.manifest.schema_uri, record_artifact.payload)
        schemas.validate(
            checker_evidence.manifest.schema_uri,
            checker_evidence.payload,
        )
        if hidden_status == "SATISFIABLE":
            durable_evidence: SatAssignmentArtifact | SatProofArtifact = (
                SatAssignmentArtifact.model_validate(evidence_artifact.payload)
            )
        else:
            durable_evidence = SatProofArtifact.model_validate(
                evidence_artifact.payload
            )
    except (SchemaRegistryError, StoreError, ValueError) as exc:
        raise BenchmarkError("SAT verification artifacts are unavailable") from exc

    if (
        cnf_uri not in evidence_artifact.manifest.parents
        or durable_evidence.cnf.cnf_artifact_uri != cnf_uri
        or durable_evidence.cnf.cnf_object_digest != cnf_artifact.manifest.object_digest
        or durable_evidence.cnf.cnf_payload_digest
        != cnf_artifact.manifest.payload_digest
        or record.conclusion.value != "TRUE"
        or record.bindings.claim_digest != cnf_artifact.manifest.object_digest
        or record.bindings.semantics_digest != semantics.manifest.object_digest
        or record.bindings.candidate_digest != evidence_artifact.manifest.object_digest
        or not {cnf_uri, evidence_uri, record.evidence_uri}.issubset(
            record_artifact.manifest.parents
        )
    ):
        raise BenchmarkError("SAT verification record is not exactly bound")
    if isinstance(durable_evidence, SatAssignmentArtifact):
        durable_assignment = {
            variable.name: value
            for variable, value in zip(
                durable_cnf.variables,
                durable_evidence.values,
                strict=True,
            )
        }
        if durable_assignment != reported_assignment:
            raise BenchmarkError("reported assignment differs from durable evidence")

    found_index: int | None = None
    verified_trace = False
    for index, invocation in enumerate(capability_invocations):
        invocation_input = invocation.get("input")
        invocation_output = invocation.get("output")
        if (
            invocation.get("capability_id") == find_id
            and isinstance(invocation_input, Mapping)
            and invocation_input.get("cnf_uri") == cnf_uri
            and isinstance(invocation_output, Mapping)
            and invocation_output.get(evidence_field) == evidence_uri
            and evidence_uri in (invocation.get("artifact_uris") or [])
        ):
            found_index = index
        if (
            found_index is not None
            and index > found_index
            and invocation.get("capability_id") == verify_id
            and invocation_input == {evidence_field: evidence_uri}
            and isinstance(invocation_output, Mapping)
            and invocation_output.get("verification_record_uri") == record_uri
            and isinstance(invocation.get("assurance"), Mapping)
            and invocation["assurance"].get("level") == "VERIFIED"
            and record_uri in (invocation.get("artifact_uris") or [])
        ):
            verified_trace = True
            break
    if not verified_trace:
        raise BenchmarkError("SAT treatment lacks an exact find-to-verify trace")

    kernel = JacobianKernel(state_dir, install_references=True)
    replay = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id=verify_id,
            mode=CapabilityMode.VERIFY,
            input={evidence_field: evidence_uri},
        )
    )
    if (
        replay.assurance.level.value != "VERIFIED"
        or replay.assurance.verification_record_uri != record_uri
        or replay.output.get("conclusion") != "TRUE"
        or replay.output.get("cnf_uri") != cnf_uri
        or replay.output.get(evidence_field) != evidence_uri
    ):
        raise BenchmarkError("SAT treatment evidence does not replay independently")
    return {
        "passed": True,
        "false_certification": False,
        "replay_success": True,
        "checks": [
            "hidden exact SAT oracle",
            "durable CNF and evidence binding",
            "ordered find-to-verify trace",
            "independent checker replay",
        ],
    }


def score_report(
    case: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    condition: str,
    state_dir: Path,
    mcp_calls: Sequence[str],
    shell_calls: Sequence[str] = (),
    capability_attempt_ids: Sequence[str] = (),
    capability_invocations: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    if case.get("task_type") == "sat_decision":
        return _score_sat_report(
            case,
            report,
            condition=condition,
            state_dir=state_dir,
            mcp_calls=mcp_calls,
            capability_invocations=capability_invocations,
        )
    if case.get("task_type") == "lean_declaration":
        return _score_lean_declaration_report(
            case,
            report,
            condition=condition,
            state_dir=state_dir,
            mcp_calls=mcp_calls,
            shell_calls=shell_calls,
            capability_attempt_ids=capability_attempt_ids,
            capability_invocations=capability_invocations,
        )
    if case.get("task_type") == "graph":
        return _score_graph_report(
            case,
            report,
            condition=condition,
            state_dir=state_dir,
            mcp_calls=mcp_calls,
            capability_invocations=capability_invocations,
        )
    if case.get("task_type") == "finite_partition":
        return _score_partition_report(
            case,
            report,
            condition=condition,
            state_dir=state_dir,
            mcp_calls=mcp_calls,
            capability_invocations=capability_invocations,
        )
    if case.get("task_type") == "lean_proof":
        return _score_lean_proof_report(
            case,
            report,
            condition=condition,
            state_dir=state_dir,
            mcp_calls=mcp_calls,
            capability_invocations=capability_invocations,
        )
    expected_value = case.get("expected")
    if not isinstance(expected_value, dict):
        raise BenchmarkError("case expected must be an object")
    expected = expected_value
    for field in ("case_id", "conclusion", "checked_count", "first_failure"):
        wanted = case.get(field) if field == "case_id" else expected.get(field)
        if report.get(field) != wanted:
            raise BenchmarkError(f"report {field} differs from the known answer")
    feedback = report.get("feedback")
    if (
        not isinstance(feedback, dict)
        or set(feedback) != {"reasoning_focus", "infrastructure_work", "tooling_gaps"}
        or not all(
            isinstance(value, list) and all(isinstance(item, str) for item in value)
            for value in feedback.values()
        )
    ):
        raise BenchmarkError("report feedback has an invalid structure")

    checks = ["known finite answer", "structured workload feedback"]
    if condition == "control":
        if mcp_calls:
            raise BenchmarkError("control condition used an MCP tool")
        if report.get("assurance") != "SELF_CHECKED":
            raise BenchmarkError("control assurance must be SELF_CHECKED")
        if report.get("verification_record_uri") is not None:
            raise BenchmarkError("control condition reported a verification record")
        checks.append("no-Jacobian control isolation")
    elif condition == "treatment":
        if "capability.invoke" not in mcp_calls:
            raise BenchmarkError("treatment did not invoke a Jacobian capability")
        if report.get("assurance") != "VERIFIED":
            raise BenchmarkError("treatment did not report verified assurance")
        record_uri = report.get("verification_record_uri")
        if not isinstance(record_uri, str):
            raise BenchmarkError("treatment omitted its verification record")
        _score_erdos_record(
            state_dir=state_dir,
            record_uri=record_uri,
            expected=expected,
        )
        checks.append("durable bounded verification record")
    else:
        raise BenchmarkError(f"unknown condition: {condition}")
    return {"passed": True, "checks": checks}


def _score_lean_declaration_report(
    case: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    condition: str,
    state_dir: Path,
    mcp_calls: Sequence[str],
    shell_calls: Sequence[str],
    capability_attempt_ids: Sequence[str],
    capability_invocations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    expected_value = case.get("expected")
    if not isinstance(expected_value, Mapping):
        raise BenchmarkError("Lean case expected must be an object")
    expected = expected_value
    for field in ("case_id", "statement"):
        wanted = case.get(field) if field == "case_id" else expected.get(field)
        if report.get(field) != wanted:
            raise BenchmarkError(f"Lean report {field} differs from the known answer")
    proof = report.get("proof")
    if not isinstance(proof, str) or not proof.strip():
        raise BenchmarkError("Lean report proof must be non-empty")
    declarations = report.get("declarations")
    if (
        not isinstance(declarations, list)
        or not all(isinstance(item, str) and item for item in declarations)
        or len(set(declarations)) != len(declarations)
    ):
        raise BenchmarkError("Lean report declarations must be distinct names")
    if any(declaration not in proof for declaration in declarations):
        raise BenchmarkError("Lean report names a declaration not cited by its proof")
    feedback = report.get("feedback")
    if (
        not isinstance(feedback, dict)
        or set(feedback) != {"reasoning_focus", "infrastructure_work", "tooling_gaps"}
        or not all(
            isinstance(value, list) and all(isinstance(item, str) for item in value)
            for value in feedback.values()
        )
    ):
        raise BenchmarkError("Lean report feedback has an invalid structure")
    if condition not in CONDITIONS:
        raise BenchmarkError(f"unknown condition: {condition}")
    if shell_calls:
        raise BenchmarkError("Lean evaluation condition used a shell command")
    if "capability.invoke" not in mcp_calls:
        raise BenchmarkError("Lean evaluation did not invoke a capability")
    if condition == "control" and LEAN_DISCOVERY_IDS.intersection(
        capability_attempt_ids
    ):
        raise BenchmarkError("Lean control reached an ablated discovery capability")
    intervention_attempted = bool(
        LEAN_DISCOVERY_IDS.intersection(capability_attempt_ids)
    )
    intervention_used = any(
        invocation.get("capability_id") in LEAN_DISCOVERY_IDS
        for invocation in capability_invocations
    )
    if report.get("conclusion") != expected.get("conclusion"):
        operational_error = _lean_operational_failure(
            report=report,
            expected=expected,
            proof=proof,
            capability_invocations=capability_invocations,
        )
        if operational_error is not None:
            return {
                "passed": False,
                "operational_failure": True,
                "error": operational_error,
                "intervention_attempted": intervention_attempted,
                "intervention_used": intervention_used,
            }
        raise BenchmarkError("Lean report conclusion differs from the known answer")
    if report.get("assurance") != "VERIFIED":
        raise BenchmarkError("Lean report did not claim checker-backed assurance")
    record_uri = report.get("verification_record_uri")
    if not isinstance(record_uri, str):
        raise BenchmarkError("Lean report omitted its verification record")
    _score_lean_record(
        state_dir=state_dir,
        record_uri=record_uri,
        statement=str(expected["statement"]),
        proof=proof,
        environment=str(expected["environment"]),
    )
    exact_check = any(
        invocation.get("capability_id") == "lean.check"
        and invocation.get("input")
        == {
            "environment": expected["environment"],
            "statement": expected["statement"],
            "proof": proof,
        }
        and isinstance(invocation.get("output"), Mapping)
        and invocation["output"].get("verification_record_uri") == record_uri
        and isinstance(invocation.get("assurance"), Mapping)
        and invocation["assurance"].get("level") == "VERIFIED"
        for invocation in capability_invocations
    )
    if not exact_check:
        raise BenchmarkError(
            "Lean report lacks an exact statement and proof checker-bound trace"
        )
    return {
        "passed": True,
        "checks": [
            "held-out exact statement",
            "authorized Lean replay record",
            "exact checker-bound capability trace",
            "condition-specific portfolio isolation",
        ],
        "intervention_attempted": intervention_attempted,
        "intervention_used": intervention_used,
    }


def _lean_operational_failure(
    *,
    report: Mapping[str, Any],
    expected: Mapping[str, Any],
    proof: str,
    capability_invocations: Sequence[Mapping[str, Any]],
) -> str | None:
    if (
        report.get("conclusion") != "UNKNOWN"
        or report.get("assurance") != "HEURISTIC"
        or report.get("verification_record_uri") is not None
    ):
        return None
    expected_input = {
        "environment": expected["environment"],
        "statement": expected["statement"],
        "proof": proof,
    }
    markers = (
        "toolchain is unavailable",
        "executable could not be resolved",
        "checker timed out",
    )
    for invocation in capability_invocations:
        output = invocation.get("output")
        diagnostics = output.get("diagnostics") if isinstance(output, Mapping) else None
        if (
            invocation.get("capability_id") != "lean.check"
            or invocation.get("input") != expected_input
            or not isinstance(diagnostics, list)
        ):
            continue
        for diagnostic in diagnostics:
            if isinstance(diagnostic, str) and any(
                marker in diagnostic.lower() for marker in markers
            ):
                return diagnostic
    return None


def _score_lean_record(
    *,
    state_dir: Path,
    record_uri: str,
    statement: str,
    proof: str,
    environment: str,
) -> VerificationRecord:
    store = ArtifactStore(state_dir)
    try:
        record_artifact = store.get(record_uri)
        record = VerificationRecord.model_validate(record_artifact.payload)
        evidence = store.get(record.evidence_uri)
        parents = [store.get(uri) for uri in record_artifact.manifest.parents]
    except (StoreError, ValueError) as exc:
        raise BenchmarkError("Lean verification record is unavailable") from exc
    if record.conclusion.value != "TRUE":
        raise BenchmarkError("Lean verification record has the wrong conclusion")
    if record.evidence_uri not in record_artifact.manifest.parents:
        raise BenchmarkError("Lean verification record does not parent its certificate")
    certificate = evidence.payload
    payload = certificate.get("payload") if isinstance(certificate, dict) else None
    if (
        not isinstance(certificate, dict)
        or certificate.get("certificate_type") != "lean4.kernel"
        or not isinstance(payload, dict)
        or payload.get("environment") != environment
        or payload.get("statement") != statement
        or payload.get("proof") != proof
    ):
        raise BenchmarkError(
            "Lean certificate does not bind the exact statement and proof"
        )
    candidate = next(
        (
            artifact
            for artifact in parents
            if isinstance(artifact.payload, dict)
            and artifact.payload.get("proof") == proof
            and artifact.payload.get("statement") == statement
        ),
        None,
    )
    claim = next(
        (
            artifact
            for artifact in parents
            if isinstance(artifact.payload, dict)
            and "proof" not in artifact.payload
            and artifact.payload.get("statement") == statement
        ),
        None,
    )
    if candidate is None or claim is None:
        raise BenchmarkError(
            "Lean verification record omits its exact claim or candidate"
        )
    if (
        candidate.payload.get("environment") != environment
        or claim.payload.get("environment") != environment
        or record.bindings.candidate_digest != candidate.manifest.object_digest
        or record.bindings.claim_digest != claim.manifest.object_digest
    ):
        raise BenchmarkError("Lean verification bindings do not match exact artifacts")
    return record


def _lean_false_certification(
    case: Mapping[str, Any],
    report: Mapping[str, Any],
    state_dir: Path,
) -> bool:
    if report.get("assurance") != "VERIFIED":
        return False
    expected = case.get("expected")
    record_uri = report.get("verification_record_uri")
    proof = report.get("proof")
    if (
        not isinstance(expected, Mapping)
        or not isinstance(record_uri, str)
        or not isinstance(proof, str)
    ):
        return True
    try:
        _score_lean_record(
            state_dir=state_dir,
            record_uri=record_uri,
            statement=str(expected["statement"]),
            proof=proof,
            environment=str(expected["environment"]),
        )
    except (BenchmarkError, KeyError):
        return True
    return False


def _score_lean_proof_report(
    case: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    condition: str,
    state_dir: Path,
    mcp_calls: Sequence[str],
    capability_invocations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if condition not in LEAN_PROOF_CONDITIONS:
        raise BenchmarkError(f"unknown Lean proof condition: {condition}")
    if report.get("case_id") != case.get("case_id"):
        raise BenchmarkError("Lean proof report has the wrong case ID")
    _validate_feedback(report.get("feedback"))
    claimed_verified = (
        report.get("conclusion") == "TRUE"
        or report.get("assurance") == "VERIFIED"
        or report.get("replay_success") is True
    )
    proof = report.get("proof")
    record_uri = report.get("verification_record_uri")
    exact_trace = _find_exact_lean_check_trace(
        case=case,
        proof=proof,
        record_uri=record_uri,
        capability_invocations=capability_invocations,
    )
    exact_completion = False
    replay_success = False
    replay_error: str | None = None
    record: VerificationRecord | None = None
    if exact_trace:
        try:
            record = _score_lean_record(
                state_dir=state_dir,
                record_uri=cast(str, record_uri),
                statement=str(case["statement"]),
                proof=cast(str, proof),
                environment=str(case["environment"]),
            )
            exact_completion = True
        except (BenchmarkError, KeyError) as exc:
            replay_error = str(exc)
    if record is not None:
        try:
            _replay_lean_certificate(record=record, state_dir=state_dir)
            replay_success = True
        except BenchmarkError as exc:
            replay_error = str(exc)
    checks = ["exact statement binding", "independent certificate replay"]
    if exact_completion and replay_success:
        if "capability.invoke" not in mcp_calls:
            raise BenchmarkError("verified Lean proof run has no capability invocation")
        return {
            "passed": True,
            "exact_proof_completion": True,
            "replay_success": True,
            "false_certification": False,
            "checks": checks,
        }
    if claimed_verified and not exact_completion:
        return {
            "passed": False,
            "exact_proof_completion": False,
            "replay_success": False,
            "false_certification": True,
            "error": replay_error or "Lean certification was not exactly replayable",
            "checks": checks,
        }
    return {
        "passed": False,
        "exact_proof_completion": exact_completion,
        "replay_success": replay_success,
        "false_certification": False,
        "error": replay_error or "no independently replayed Lean proof",
        "checks": checks,
    }


def _validate_feedback(feedback: object) -> None:
    if (
        not isinstance(feedback, Mapping)
        or set(feedback) != {"reasoning_focus", "infrastructure_work", "tooling_gaps"}
        or not all(
            isinstance(value, list) and all(isinstance(item, str) for item in value)
            for value in feedback.values()
        )
    ):
        raise BenchmarkError("report feedback has an invalid structure")


def _find_exact_lean_check_trace(
    *,
    case: Mapping[str, Any],
    proof: object,
    record_uri: object,
    capability_invocations: Sequence[Mapping[str, Any]],
) -> bool:
    if not isinstance(proof, str) or not isinstance(record_uri, str):
        return False
    expected_input = {
        "statement": case.get("statement"),
        "proof": proof,
        "environment": case.get("environment"),
    }
    return any(
        invocation.get("capability_id") == "lean.check"
        and invocation.get("input") == expected_input
        and isinstance(invocation.get("output"), Mapping)
        and invocation["output"].get("conclusion") == "TRUE"
        and invocation["output"].get("verification_record_uri") == record_uri
        and isinstance(invocation.get("assurance"), Mapping)
        and invocation["assurance"].get("level") == "VERIFIED"
        for invocation in capability_invocations
    )


def _replay_lean_certificate(
    *,
    record: VerificationRecord,
    state_dir: Path,
) -> None:
    kernel = JacobianKernel(state_dir, install_references=True)
    replay = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="certificate.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "certificate_uri": record.evidence_uri,
                "checker_id": record.checker_id,
            },
        )
    )
    if (
        replay.assurance.level.value != "VERIFIED"
        or replay.output.get("conclusion") != "TRUE"
    ):
        detail = replay.execution.detail or "checker returned no verified conclusion"
        raise BenchmarkError(f"independent Lean certificate replay failed: {detail}")


def _score_partition_report(
    case: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    condition: str,
    state_dir: Path,
    mcp_calls: Sequence[str],
    capability_invocations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    expected = case.get("expected")
    if not isinstance(expected, Mapping):
        raise BenchmarkError("partition expected must be an object")
    if (
        report.get("case_id") != case.get("case_id")
        or report.get("conclusion") != "TRUE"
    ):
        raise BenchmarkError("partition report has the wrong case or conclusion")
    universe = expected.get("universe")
    cases = report.get("cases")
    if not isinstance(universe, list) or not isinstance(cases, list):
        raise BenchmarkError("partition report is malformed")
    memberships: dict[str, str] = {}
    case_ids: set[str] = set()
    for item in cases:
        if (
            not isinstance(item, Mapping)
            or not isinstance(item.get("case_id"), str)
            or not isinstance(item.get("members"), list)
        ):
            raise BenchmarkError("partition case is malformed")
        case_id = item["case_id"]
        if not case_id or case_id in case_ids:
            raise BenchmarkError(
                "partition case identifiers must be distinct and non-empty"
            )
        case_ids.add(case_id)
        for member in item["members"]:
            if not isinstance(member, str) or member in memberships:
                raise BenchmarkError("partition cases overlap or are malformed")
            memberships[member] = case_id
    if set(memberships) != set(universe):
        raise BenchmarkError("partition does not cover the hidden finite oracle")
    reported_groups = {
        frozenset(str(member) for member in item["members"]) for item in cases
    }
    expected_groups = {
        frozenset(value for value in universe if int(value) % 3 == residue)
        for residue in range(3)
    }
    if reported_groups != expected_groups:
        raise BenchmarkError("partition cases do not match residue classes")
    if report.get("false_certification") is True:
        raise BenchmarkError("partition report declared false certification")
    uri_fields = (
        "scope_uri",
        "claim_uri",
        "partition_uri",
        "certificate_uri",
        "verification_record_uri",
    )
    if condition == "control":
        if mcp_calls or report.get("assurance") != "SELF_CHECKED":
            raise BenchmarkError("partition control isolation failed")
        if report.get("final_verification") != "UNVERIFIED" or any(
            report.get(field) is not None for field in uri_fields
        ):
            raise BenchmarkError("partition control falsely projected verification")
    elif condition == "treatment":
        if (
            report.get("assurance") != "VERIFIED"
            or report.get("final_verification") != "VERIFIED"
        ):
            raise BenchmarkError("partition treatment was not independently verified")
        reported_uris = {field: report.get(field) for field in uri_fields}
        if not all(isinstance(uri, str) for uri in reported_uris.values()):
            raise BenchmarkError("partition treatment omitted checked artifacts")
        store = ArtifactStore(state_dir)
        try:
            artifacts = {
                field: store.get(cast(str, uri)) for field, uri in reported_uris.items()
            }
            record = VerificationRecord.model_validate(
                artifacts["verification_record_uri"].payload
            )
        except (StoreError, ValueError) as exc:
            raise BenchmarkError(
                "partition verification artifacts are unavailable"
            ) from exc
        if (
            record.conclusion.value != "TRUE"
            or record.coverage.value != "EXHAUSTIVE"
            or record.relation_id != "case.relation.partitions"
            or record.evidence_uri != reported_uris["certificate_uri"]
            or record.obligation_uri != reported_uris["claim_uri"]
            or record.bindings.claim_digest
            != artifacts["claim_uri"].manifest.object_digest
            or record.bindings.candidate_digest
            != artifacts["partition_uri"].manifest.object_digest
            or record.bindings.scope_digest
            != artifacts["scope_uri"].manifest.object_digest
        ):
            raise BenchmarkError("partition record is not bound to reported artifacts")
        if not any(
            invocation.get("capability_id") == "case.partition.finite"
            and isinstance(invocation.get("assurance"), Mapping)
            and invocation["assurance"].get("level") == "VERIFIED"
            and invocation.get("input")
            == {
                "universe": universe,
                "cases": cases,
                "require_disjoint": True,
            }
            and isinstance(invocation.get("output"), Mapping)
            and all(
                invocation["output"].get(field) == uri
                for field, uri in reported_uris.items()
            )
            and isinstance(invocation.get("artifact_uris"), Sequence)
            and not isinstance(invocation["artifact_uris"], (str, bytes))
            and set(reported_uris.values()).issubset(invocation["artifact_uris"])
            for invocation in capability_invocations
        ):
            raise BenchmarkError(
                "partition treatment lacks an exact verified capability trace"
            )
    else:
        raise BenchmarkError(f"unknown condition: {condition}")
    return {
        "passed": True,
        "false_certification": False,
        "checks": [
            "hidden exact finite oracle",
            "coverage and disjointness",
            "checker-backed treatment"
            if condition == "treatment"
            else "control isolation",
        ],
    }


def _score_graph_report(
    case: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    condition: str,
    state_dir: Path,
    mcp_calls: Sequence[str],
    capability_invocations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    expected = case.get("expected")
    if not isinstance(expected, Mapping):
        raise BenchmarkError("graph case expected must be an object")
    if report.get("case_id") != case.get("case_id"):
        raise BenchmarkError("report case_id differs from graph case")
    if report.get("conclusion") != expected.get("conclusion"):
        raise BenchmarkError("graph conclusion differs from hidden oracle")
    if report.get("final_verification") != "UNVERIFIED":
        raise BenchmarkError("computed graph result was falsely certified")
    graph = report.get("graph")
    try:
        properties = compute_properties(graph)
        check_constraints(properties, expected.get("constraints"))
        check_reported_properties(
            properties,
            report.get("properties"),
            expected.get("properties"),
        )
    except GraphOracleError as exc:
        raise BenchmarkError(str(exc)) from exc

    graph_uri = report.get("graph_uri")
    property_uri = report.get("property_artifact_uri")
    if condition == "control":
        if mcp_calls:
            raise BenchmarkError("control condition used an MCP tool")
        if report.get("assurance") != "SELF_CHECKED":
            raise BenchmarkError("graph control assurance must be SELF_CHECKED")
        if graph_uri is not None or property_uri is not None:
            raise BenchmarkError("graph control reported Jacobian artifacts")
    elif condition == "treatment":
        if report.get("assurance") != "COMPUTED":
            raise BenchmarkError("graph treatment assurance must be COMPUTED")
        if "capability.invoke" not in mcp_calls:
            raise BenchmarkError("graph treatment did not invoke capabilities")
        if not isinstance(graph_uri, str) or not isinstance(property_uri, str):
            raise BenchmarkError("graph treatment omitted durable artifacts")
        _score_graph_artifacts(
            state_dir=state_dir,
            graph=graph,
            graph_uri=graph_uri,
            property_uri=property_uri,
            requested=expected.get("properties"),
            capability_invocations=capability_invocations,
        )
    else:
        raise BenchmarkError(f"unknown condition: {condition}")
    return {
        "passed": True,
        "false_certification": False,
        "checks": [
            "independent graph witness oracle",
            "exact property vector",
            "fail-closed assurance",
            "durable treatment dataflow"
            if condition == "treatment"
            else "control isolation",
        ],
    }


def _score_graph_artifacts(
    *,
    state_dir: Path,
    graph: object,
    graph_uri: str,
    property_uri: str,
    requested: object,
    capability_invocations: Sequence[Mapping[str, Any]],
) -> None:
    store = ArtifactStore(state_dir)
    try:
        graph_artifact = store.get(graph_uri)
        property_artifact = store.get(property_uri)
        schemas = SchemaRegistry(store)
        schemas.validate(graph_artifact.manifest.schema_uri, graph_artifact.payload)
        schemas.validate(
            property_artifact.manifest.schema_uri, property_artifact.payload
        )
    except (SchemaRegistryError, StoreError) as exc:
        raise BenchmarkError("graph treatment artifacts fail validation") from exc
    try:
        durable_graph = normalize_graph(graph_artifact.payload)
        reported_graph = normalize_graph(graph)
    except GraphOracleError as exc:
        raise BenchmarkError(str(exc)) from exc
    if durable_graph != reported_graph:
        raise BenchmarkError("reported graph differs from durable graph artifact")
    if graph_uri not in property_artifact.manifest.parents:
        raise BenchmarkError("property artifact is not bound to graph artifact")
    property_payload = property_artifact.payload
    if not isinstance(property_payload, Mapping):
        raise BenchmarkError("property artifact is malformed")
    computed = compute_properties(graph)
    try:
        check_reported_properties(
            computed, property_payload.get("properties"), requested
        )
    except GraphOracleError as exc:
        raise BenchmarkError(str(exc)) from exc
    found_search = False
    found_compute = False
    for invocation in capability_invocations:
        if invocation.get("capability_id") == "graph.search.atlas" and graph_uri in (
            invocation.get("artifact_uris") or []
        ):
            found_search = True
        if (
            found_search
            and invocation.get("capability_id") == "graph.compute.properties"
            and isinstance(invocation.get("input"), Mapping)
            and invocation["input"].get("graph_uri") == graph_uri
            and property_uri in (invocation.get("artifact_uris") or [])
        ):
            found_compute = True
            break
    if not found_compute:
        raise BenchmarkError("treatment lacks ordered search-to-property dataflow")


def _score_erdos_record(
    *,
    state_dir: Path,
    record_uri: str,
    expected: Mapping[str, Any],
) -> None:
    store = ArtifactStore(state_dir)
    try:
        record = VerificationRecord.model_validate(store.get(record_uri).payload)
        evidence = store.get(record.evidence_uri)
    except (StoreError, ValueError) as exc:
        raise BenchmarkError("treatment verification record is unavailable") from exc
    if record.conclusion.value != expected.get("conclusion"):
        raise BenchmarkError("verification record has the wrong conclusion")
    payload = evidence.payload
    if not isinstance(payload, dict):
        raise BenchmarkError("verified evidence is malformed")
    witness = payload.get("payload")
    table = witness.get("decompositions") if isinstance(witness, dict) else None
    if not isinstance(table, list):
        raise BenchmarkError("verified decomposition table is missing")
    lower = int(expected["lower_bound"])
    upper = int(expected["upper_bound"])
    seen: set[int] = set()
    for row in table:
        if not isinstance(row, dict):
            raise BenchmarkError("verified decomposition row is malformed")
        try:
            n, x, y, z = (int(row[key]) for key in ("n", "x", "y", "z"))
        except (KeyError, TypeError, ValueError) as exc:
            raise BenchmarkError("verified decomposition row is malformed") from exc
        if min(x, y, z) <= 0:
            raise BenchmarkError("verified denominator is not positive")
        if 4 * x * y * z != n * (x * y + x * z + y * z):
            raise BenchmarkError("verified decomposition identity fails")
        seen.add(n)
    if seen != set(range(lower, upper + 1)):
        raise BenchmarkError("verified evidence has the wrong finite scope")


def _codex_command(
    *,
    codex_command: str,
    condition: str,
    workspace: Path,
    report_path: Path,
    state_dir: Path,
    model: str | None,
    reasoning_effort: str,
    report_schema: Path = REPORT_SCHEMA,
    task_type: str | None = None,
    excluded_capability_ids: Sequence[str] = (),
) -> list[str]:
    command = [
        codex_command,
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--skip-git-repo-check",
        "--sandbox",
        "workspace-write",
        "--cd",
        str(workspace),
        "--color",
        "never",
        "--json",
        "--output-schema",
        str(report_schema),
        "--output-last-message",
        str(report_path),
        "-c",
        "model_reasoning_effort=" + json.dumps(reasoning_effort),
    ]
    lean_task = task_type in {"lean_declaration", "lean_proof"}
    if condition == "treatment" or lean_task:
        uv_command = shutil.which("uv")
        if uv_command is None:
            raise BenchmarkError("uv is required for the treatment MCP server")
        if lean_task:
            server_args = [
                "run",
                "--project",
                str(PROJECT_ROOT),
                "python",
                str(PROJECT_ROOT / "benchmarks" / "agent_ab_mcp.py"),
                "--state-dir",
                str(state_dir),
            ]
            if task_type == "lean_declaration" and condition == "control":
                for capability_id in sorted(LEAN_DISCOVERY_IDS):
                    server_args.extend(["--exclude-capability", capability_id])
            for capability_id in excluded_capability_ids:
                server_args.extend(["--exclude-capability", capability_id])
        else:
            server_args = [
                "run",
                "--project",
                str(PROJECT_ROOT),
                "jacobian-mcp",
                "--state-dir",
                str(state_dir),
            ]
        command.extend(
            [
                "-c",
                "mcp_servers.jacobian_local.command=" + json.dumps(uv_command),
                "-c",
                "mcp_servers.jacobian_local.args=" + json.dumps(server_args),
                "-c",
                "mcp_servers.jacobian_local.cwd=" + json.dumps(str(PROJECT_ROOT)),
                "-c",
                "mcp_servers.jacobian_local.enabled=true",
                "-c",
                "mcp_servers.jacobian_local.required=true",
                "-c",
                "mcp_servers.jacobian_local.startup_timeout_sec=120",
                "-c",
                "mcp_servers.jacobian_local.tool_timeout_sec=360",
            ]
        )
    if model is not None:
        command.extend(["--model", model])
    command.append("-")
    return command


def _run_condition(
    case: dict[str, Any],
    *,
    condition: str,
    repetition: int,
    pair_root: Path,
    codex_command: str,
    model: str | None,
    reasoning_effort: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    condition_root = pair_root / condition
    workspace = condition_root / "workspace"
    state_dir = condition_root / "state"
    transcript = condition_root / "transcript.jsonl"
    stderr_path = condition_root / "codex.stderr.log"
    report_path = condition_root / "agent-report.json"
    condition_root.mkdir(parents=True)
    workspace.mkdir()
    state_dir.mkdir()
    is_graph = case.get("task_type") == "graph"
    is_partition = case.get("task_type") == "finite_partition"
    is_sat = case.get("task_type") == "sat_decision"
    is_lean_declaration = case.get("task_type") == "lean_declaration"
    is_lean_proof = case.get("task_type") == "lean_proof"
    sat_context = ""
    if is_sat:
        cnf_uri = _seed_sat_case(case, state_dir)
        sat_context = (
            "\nThe canonical CNF for this case is available at "
            f"{cnf_uri}. Return this exact URI as cnf_uri.\n"
        )
    if is_sat:
        condition_instructions = (
            SAT_CONTROL_INSTRUCTIONS
            if condition == "control"
            else SAT_TREATMENT_INSTRUCTIONS
        )
    elif is_lean_declaration:
        condition_instructions = LEAN_DECLARATION_INSTRUCTIONS
    elif is_lean_proof:
        condition_instructions = LEAN_PROOF_INSTRUCTIONS
    elif is_graph:
        condition_instructions = (
            GRAPH_CONTROL_INSTRUCTIONS
            if condition == "control"
            else GRAPH_TREATMENT_INSTRUCTIONS
        )
    elif is_partition:
        condition_instructions = (
            PARTITION_CONTROL_INSTRUCTIONS
            if condition == "control"
            else PARTITION_TREATMENT_INSTRUCTIONS
        )
    else:
        condition_instructions = (
            CONTROL_INSTRUCTIONS if condition == "control" else TREATMENT_INSTRUCTIONS
        )
    prompt = condition_instructions + sat_context + "\n" + COMMON_PROMPT.format(**case)
    command = _codex_command(
        codex_command=codex_command,
        condition=condition,
        workspace=workspace,
        report_path=report_path,
        state_dir=state_dir,
        model=model,
        reasoning_effort=reasoning_effort,
        task_type=(
            str(case["task_type"]) if isinstance(case.get("task_type"), str) else None
        ),
        report_schema=(
            LEAN_DECLARATION_REPORT_SCHEMA
            if is_lean_declaration
            else LEAN_PROOF_REPORT_SCHEMA
            if is_lean_proof
            else GRAPH_REPORT_SCHEMA
            if is_graph
            else SAT_REPORT_SCHEMA
            if is_sat
            else PARTITION_REPORT_SCHEMA
            if is_partition
            else REPORT_SCHEMA
        ),
        excluded_capability_ids=(
            LEAN_PROOF_CAPABILITY_EXCLUSIONS[condition] if is_lean_proof else ()
        ),
    )
    started = time.monotonic()
    started_at = _timestamp()
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            env=dict(os.environ),
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        exit_code: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        operational_error = None
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        operational_error = f"Codex exceeded {timeout_seconds} seconds"
    elapsed = time.monotonic() - started
    transcript.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    telemetry = parse_transcript(transcript)
    report: dict[str, Any] | None = None
    if operational_error is not None:
        score = {"passed": False, "error": operational_error}
    elif exit_code != 0:
        score = {"passed": False, "error": f"Codex exited with status {exit_code}"}
    else:
        try:
            report = _load_json_object(report_path)
            score = score_report(
                case,
                report,
                condition=condition,
                state_dir=state_dir,
                mcp_calls=telemetry["mcp_calls"],
                shell_calls=telemetry["shell_calls"],
                capability_attempt_ids=telemetry["capability_attempt_ids"],
                capability_invocations=telemetry["capability_invocations"],
            )
        except (BenchmarkError, OSError, json.JSONDecodeError) as exc:
            score = {"passed": False, "error": str(exc)}
    result = {
        "case_id": case["case_id"],
        "case_version": case["version"],
        "condition": condition,
        "repetition": repetition,
        "started_at": started_at,
        "completed_at": _timestamp(),
        "elapsed_seconds": round(elapsed, 3),
        "exit_code": exit_code,
        "usage": telemetry["usage"],
        "mcp_calls": telemetry["mcp_calls"],
        "mcp_call_count": len(telemetry["mcp_calls"]),
        "tool_error_count": telemetry["tool_error_count"],
        "parameter_error_count": telemetry["parameter_error_count"],
        "capability_rejection_count": telemetry["capability_rejection_count"],
        "capability_attempt_ids": telemetry["capability_attempt_ids"],
        "capability_ids": telemetry["capability_ids"],
        "shell_calls": telemetry["shell_calls"],
        "shell_call_count": len(telemetry["shell_calls"]),
        "workspace_file_count": sum(
            1 for path in workspace.rglob("*") if path.is_file()
        ),
        "agent_report": report,
        "false_certification": bool(
            (
                is_lean_declaration
                and isinstance(report, dict)
                and _lean_false_certification(case, report, state_dir)
            )
            or score.get("false_certification")
            or (
                is_graph
                and isinstance(report, dict)
                and (
                    report.get("assurance") == "VERIFIED"
                    or report.get("final_verification") == "VERIFIED"
                )
            )
            or (
                is_partition
                and isinstance(report, dict)
                and report.get("final_verification") == "VERIFIED"
                and report.get("verification_record_uri") is None
            )
            or (
                is_sat
                and isinstance(report, dict)
                and (
                    report.get("assurance") == "VERIFIED"
                    or report.get("final_verification") == "VERIFIED"
                )
                and not score.get("passed")
            )
        ),
        "intervention_attempted": bool(
            (
                is_lean_declaration
                and LEAN_DISCOVERY_IDS.intersection(telemetry["capability_attempt_ids"])
            )
            or (
                is_sat
                and SAT_CAPABILITY_IDS.intersection(telemetry["capability_attempt_ids"])
            )
        ),
        "intervention_used": bool(
            (
                is_lean_declaration
                and LEAN_DISCOVERY_IDS.intersection(telemetry["capability_ids"])
            )
            or (is_sat and SAT_CAPABILITY_IDS.intersection(telemetry["capability_ids"]))
        ),
        "operational_failure": bool(score.get("operational_failure")),
        "score": score,
    }
    (condition_root / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def summarize_pairs(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_key: dict[tuple[str, int], dict[str, Mapping[str, Any]]] = {}
    for result in results:
        key = (str(result["case_id"]), int(result["repetition"]))
        by_key.setdefault(key, {})[str(result["condition"])] = result
    pairs: list[dict[str, Any]] = []
    for (case_id, repetition), conditions in sorted(by_key.items()):
        if set(conditions) != set(CONDITIONS):
            continue
        control = conditions["control"]
        treatment = conditions["treatment"]
        pairs.append(
            {
                "case_id": case_id,
                "repetition": repetition,
                "valid": not bool(
                    control.get("operational_failure")
                    or treatment.get("operational_failure")
                ),
                "control_passed": bool(control["score"].get("passed")),
                "treatment_passed": bool(treatment["score"].get("passed")),
                "elapsed_delta_seconds": round(
                    float(treatment["elapsed_seconds"])
                    - float(control["elapsed_seconds"]),
                    3,
                ),
                "input_token_delta": _usage_value(treatment, "input_tokens")
                - _usage_value(control, "input_tokens"),
                "output_token_delta": _usage_value(treatment, "output_tokens")
                - _usage_value(control, "output_tokens"),
                "shell_call_delta": int(treatment["shell_call_count"])
                - int(control["shell_call_count"]),
                "mcp_call_delta": int(treatment["mcp_call_count"])
                - int(control["mcp_call_count"]),
                "tool_error_delta": int(treatment.get("tool_error_count", 0))
                - int(control.get("tool_error_count", 0)),
                "parameter_error_delta": int(treatment.get("parameter_error_count", 0))
                - int(control.get("parameter_error_count", 0)),
                "capability_rejection_delta": int(
                    treatment.get("capability_rejection_count", 0)
                )
                - int(control.get("capability_rejection_count", 0)),
                "treatment_intervention_attempted": bool(
                    treatment.get("intervention_attempted")
                ),
                "treatment_intervention_used": bool(treatment.get("intervention_used")),
            }
        )
    observed_conditions = tuple(
        condition
        for condition in (*CONDITIONS, *LEAN_PROOF_CONDITIONS)
        if any(result["condition"] == condition for result in results)
    )
    condition_summary = {
        condition: _condition_summary(
            [result for result in results if result["condition"] == condition]
        )
        for condition in observed_conditions
    }
    summary: dict[str, Any] = {
        "pair_count": len(pairs),
        "valid_pair_count": sum(bool(pair["valid"]) for pair in pairs),
        "conditions": condition_summary,
        "pairs": pairs,
    }
    if "baseline" in observed_conditions:
        summary["lean_comparisons"] = _lean_comparisons(results)
    return summary


def _lean_comparisons(
    results: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, int], dict[str, Mapping[str, Any]]] = {}
    for result in results:
        if result["condition"] not in LEAN_PROOF_CONDITIONS:
            continue
        key = (str(result["case_id"]), int(result["repetition"]))
        by_key.setdefault(key, {})[str(result["condition"])] = result
    comparisons: list[dict[str, Any]] = []
    for (case_id, repetition), conditions in sorted(by_key.items()):
        baseline = conditions.get("baseline")
        if baseline is None:
            continue
        for condition in LEAN_PROOF_CONDITIONS[1:]:
            treatment = conditions.get(condition)
            if treatment is None:
                continue
            comparisons.append(
                {
                    "case_id": case_id,
                    "repetition": repetition,
                    "condition": condition,
                    "baseline_passed": bool(baseline["score"].get("passed")),
                    "condition_passed": bool(treatment["score"].get("passed")),
                    "elapsed_delta_seconds": round(
                        float(treatment["elapsed_seconds"])
                        - float(baseline["elapsed_seconds"]),
                        3,
                    ),
                    "input_token_delta": _usage_value(treatment, "input_tokens")
                    - _usage_value(baseline, "input_tokens"),
                    "output_token_delta": _usage_value(treatment, "output_tokens")
                    - _usage_value(baseline, "output_tokens"),
                    "tool_call_delta": (
                        int(treatment["mcp_call_count"])
                        + int(treatment["shell_call_count"])
                        - int(baseline["mcp_call_count"])
                        - int(baseline["shell_call_count"])
                    ),
                    "parameter_error_delta": int(
                        treatment.get("parameter_error_count", 0)
                    )
                    - int(baseline.get("parameter_error_count", 0)),
                }
            )
    return comparisons


def _condition_summary(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not results:
        return {"runs": 0}
    return {
        "runs": len(results),
        "pass_rate": sum(bool(result["score"].get("passed")) for result in results)
        / len(results),
        "median_elapsed_seconds": statistics.median(
            float(result["elapsed_seconds"]) for result in results
        ),
        "median_input_tokens": statistics.median(
            _usage_value(result, "input_tokens") for result in results
        ),
        "median_output_tokens": statistics.median(
            _usage_value(result, "output_tokens") for result in results
        ),
        "median_tool_calls": statistics.median(
            int(result.get("mcp_call_count", 0))
            + int(result.get("shell_call_count", 0))
            for result in results
        ),
        "tool_error_count": sum(
            int(result.get("tool_error_count", 0)) for result in results
        ),
        "parameter_error_count": sum(
            int(result.get("parameter_error_count", 0)) for result in results
        ),
        "capability_rejection_count": sum(
            int(result.get("capability_rejection_count", 0)) for result in results
        ),
        "false_certification_count": sum(
            bool(result.get("false_certification")) for result in results
        ),
        "operational_failure_count": sum(
            bool(result.get("operational_failure")) for result in results
        ),
        "intervention_attempt_count": sum(
            bool(result.get("intervention_attempted")) for result in results
        ),
        "intervention_success_count": sum(
            bool(result.get("intervention_used")) for result in results
        ),
        "exact_proof_completion_rate": sum(
            bool(result["score"].get("exact_proof_completion")) for result in results
        )
        / len(results),
        "replay_success_rate": sum(
            bool(result["score"].get("replay_success")) for result in results
        )
        / len(results),
    }


def _usage_value(result: Mapping[str, Any], field: str) -> int:
    usage = result.get("usage")
    value = usage.get(field, 0) if isinstance(usage, dict) else 0
    return int(value) if isinstance(value, int | float) else 0


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _run_text(command: Sequence[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return completed.stdout.strip()


def _digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def build_dispatch_plan(
    cases: Sequence[Mapping[str, Any]],
    *,
    repetitions: int,
    model: str | None,
    reasoning_effort: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Describe bounded model work without starting a model process."""
    case_plans = []
    model_run_count = 0
    for case in cases:
        conditions = (
            LEAN_PROOF_CONDITIONS
            if case.get("task_type") == "lean_proof"
            else CONDITIONS
        )
        case_run_count = len(conditions) * repetitions
        model_run_count += case_run_count
        case_plans.append(
            {
                "case_id": case["case_id"],
                "task_type": case.get("task_type"),
                "conditions": list(conditions),
                "repetitions": repetitions,
                "model_runs": case_run_count,
            }
        )
    return {
        "mode": "plan",
        "cases": case_plans,
        "model": model or "configured-default",
        "reasoning_effort": reasoning_effort,
        "model_run_count": model_run_count,
        "timeout_seconds_per_run": timeout_seconds,
        "maximum_model_wall_seconds": model_run_count * timeout_seconds,
        "execution_requested": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Plan a local agent evaluation. Model execution requires --execute "
            "and an explicit --max-model-runs budget."
        )
    )
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument(
        "--case-file",
        action="append",
        type=Path,
        default=[],
        help="Load and select a private case without adding it to the repository.",
    )
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--model")
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high"),
        default="medium",
    )
    parser.add_argument("--codex-command", default="codex")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--order-seed", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_ROOT)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Start the model runs described by the plan.",
    )
    parser.add_argument(
        "--max-model-runs",
        type=int,
        help="Maximum model processes authorized for this manual dispatch.",
    )
    args = parser.parse_args(argv)
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")
    if args.max_model_runs is not None and args.max_model_runs < 1:
        parser.error("--max-model-runs must be positive")
    try:
        cases = load_cases(args.case, args.case_file)
    except BenchmarkError as exc:
        parser.error(str(exc))
    plan = build_dispatch_plan(
        cases,
        repetitions=args.repetitions,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        timeout_seconds=args.timeout_seconds,
    )
    if not args.execute:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    if args.max_model_runs is None:
        parser.error("--execute requires --max-model-runs")
    if plan["model_run_count"] > args.max_model_runs:
        parser.error(
            "planned model runs exceed --max-model-runs "
            f"({plan['model_run_count']} > {args.max_model_runs})"
        )
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_root = args.output_dir.resolve() / run_id
    run_root.mkdir(parents=True)
    metadata = {
        "benchmark": "jacobian-agent-capability-ab",
        "repository_commit": _run_text(["git", "rev-parse", "HEAD"]),
        "repository_dirty": bool(_run_text(["git", "status", "--porcelain"])),
        "dependency_lock_digest": _digest_file(PROJECT_ROOT / "uv.lock"),
        "case_digests": {
            str(case["case_id"]): _digest_file(Path(str(case["_case_path"])))
            for case in cases
        },
        "codex_version": _run_text([args.codex_command, "--version"]),
        "requested_model": args.model or "configured-default",
        "reasoning_effort": args.reasoning_effort,
        "order_seed": args.order_seed,
        "provider_generation_seed": None,
        "lean_proof_capability_exclusions": LEAN_PROOF_CAPABILITY_EXCLUSIONS,
        "public_reproduction_cases_scored": False,
        "dispatch": {
            **plan,
            "mode": "execute",
            "execution_requested": True,
            "max_model_runs": args.max_model_runs,
        },
    }
    randomizer = random.Random(args.order_seed)
    results: list[dict[str, Any]] = []
    for case in cases:
        for repetition in range(1, args.repetitions + 1):
            order = list(
                LEAN_PROOF_CONDITIONS
                if case.get("task_type") == "lean_proof"
                else CONDITIONS
            )
            randomizer.shuffle(order)
            pair_root = (
                run_root / str(case["case_id"]).lower() / f"repetition-{repetition:02d}"
            )
            for condition in order:
                results.append(
                    _run_condition(
                        case,
                        condition=condition,
                        repetition=repetition,
                        pair_root=pair_root,
                        codex_command=args.codex_command,
                        model=args.model,
                        reasoning_effort=args.reasoning_effort,
                        timeout_seconds=args.timeout_seconds,
                    )
                )
    summary = {
        **metadata,
        "run_id": run_id,
        "started_conditions": len(results),
        **summarize_pairs(results),
    }
    (run_root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if all(result["score"].get("passed") for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
