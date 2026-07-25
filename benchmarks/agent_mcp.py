"""Run public known-answer cases through a real Codex CLI and Jacobian MCP.

This is an agent-behavior pilot, not a mathematical verifier or a performance
benchmark. The scorer distrusts the agent's prose and validates the durable
verification record, evidence, bindings, claim, and candidate in the isolated
Jacobian state directory.

Run with:

    uv run python benchmarks/agent_mcp.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import networkx as nx

from jacobian.schema_registry import SchemaRegistry, SchemaRegistryError
from jacobian.store import ArtifactStore, StoreError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_ROOT = Path(__file__).with_name("agent_cases")
DEFAULT_RESULTS_ROOT = Path(__file__).with_name("results")
REPORT_SCHEMA = CASES_ROOT / "report.schema.json"
GRAPH_REPORT_SCHEMA = CASES_ROOT / "graph-report.schema.json"
ARTIFACT_PREFIX = "artifact://sha256/"
PARAMETER_ERROR_CODES = frozenset(
    {
        -32602,
        "INVALID_ARGUMENT",
        "INVALID_CONSTRAINT_RANGE",
        "INVALID_PARAMS",
        "INVALID_REQUEST",
        "SCHEMA_VALIDATION",
        "invalid_params",
    }
)

SYSTEM_TASK = """\
Use only the jacobian_local MCP tools and resources for the mathematical work.
Do not run shell commands, read repository files, edit files, or use network
retrieval. Start with {agent_contract_uri}; it contains the selected domain's
compact input contract and exact semantic identity. Treat evaluation and
witness search as
UNVERIFIED. A decisive result is VERIFIED only after the compatible independent
checker accepts the exact bound evidence. Do not reread returned evidence or
verification-record resources merely to prepare the final report; the benchmark
scorer validates them directly. For bundled witness cases, use verification.run
instead of manually calling its five component tools.

Complete public known-answer case {case_id}. Set report case_id exactly to
{case_id}.

{prompt}

Return the required JSON report. Report the exact durable URIs returned by the
tools. Do not infer verification from operational completion, exhaustive
evaluation, or failure to find a witness. State any remaining limitations.
Record concise feedback grounded in this run: useful tooling, tooling gaps,
missing domain knowledge, and concrete improvements. Empty feedback lists are
valid when the run exposed no issue.
"""

GRAPH_SYSTEM_TASK = """\
Use only the jacobian_local MCP tools for mathematical work. Do not run shell
commands, read repository files, edit files, or use network retrieval. Describe
unfamiliar capabilities before invoking them.

Complete public workflow case {case_id}. Set report case_id exactly to
{case_id}.

{prompt}

Use graph.search.atlas, then graph.compute.properties on one returned graph.
Report exact durable URIs. NetworkX computation is COMPUTED, not VERIFIED.
Complete Atlas coverage does not authorize mathematical promotion. State
limits. Record concise feedback; empty feedback lists are valid.
"""


class BenchmarkError(RuntimeError):
    """The runner or durable benchmark evidence is invalid."""


def _load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BenchmarkError(f"{path} must contain a JSON object")
    return value


def load_cases(selected: Sequence[str]) -> list[dict[str, Any]]:
    cases = [
        _load_json_object(path)
        for path in sorted(CASES_ROOT.glob("*.json"))
        if not path.name.endswith("schema.json")
    ]
    by_id = {str(case.get("case_id")): case for case in cases}
    if len(by_id) != len(cases):
        raise BenchmarkError("agent benchmark case IDs must be unique")
    if not selected or selected == ["all"]:
        return cases
    missing = sorted(set(selected) - set(by_id))
    if missing:
        raise BenchmarkError(f"unknown agent benchmark cases: {', '.join(missing)}")
    return [by_id[case_id] for case_id in selected]


def _run_text(command: Sequence[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.stdout.strip()


def _digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _artifact_uri(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith(ARTIFACT_PREFIX)
        or len(value.removeprefix(ARTIFACT_PREFIX)) != 64
    ):
        raise BenchmarkError(f"agent report has an invalid {field}")
    return value


def _contains_parameter_error(value: object) -> bool:
    if isinstance(value, Mapping):
        if value.get("code") in PARAMETER_ERROR_CODES:
            return True
        return any(_contains_parameter_error(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_contains_parameter_error(item) for item in value)
    return False


def _contains_execution_error(value: object) -> bool:
    if isinstance(value, Mapping):
        if value.get("status") in {"CANCELLED", "ERROR", "TIMEOUT"}:
            return True
        return any(_contains_execution_error(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_contains_execution_error(item) for item in value)
    return False


def _mcp_text_payload(item: Mapping[str, Any]) -> dict[str, Any] | None:
    result = item.get("result")
    if not isinstance(result, dict):
        return None
    content = result.get("content")
    if not isinstance(content, list):
        return None
    for block in content:
        if not isinstance(block, dict) or not isinstance(block.get("text"), str):
            continue
        try:
            payload = json.loads(block["text"])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def parse_transcript(
    path: Path,
) -> tuple[list[str], dict[str, Any] | None, dict[str, Any]]:
    calls: list[str] = []
    successful_calls: list[str] = []
    usage: dict[str, Any] | None = None
    tool_error_count = 0
    parameter_error_count = 0
    capability_ids: list[str] = []
    capability_invocations: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if (
            isinstance(event, dict)
            and event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "mcp_tool_call"
            and isinstance(item.get("tool"), str)
        ):
            calls.append(item["tool"])
            result = item.get("result")
            failed = bool(
                item.get("status") in {"error", "failed"}
                or item.get("error")
                or (isinstance(result, dict) and result.get("isError") is True)
                or _contains_execution_error(item)
            )
            if failed:
                tool_error_count += 1
            else:
                successful_calls.append(item["tool"])
                arguments = item.get("arguments")
                response = _mcp_text_payload(item)
                execution = (
                    response.get("execution") if isinstance(response, dict) else None
                )
                if (
                    item["tool"] == "capability.invoke"
                    and isinstance(arguments, dict)
                    and isinstance(arguments.get("capability_id"), str)
                    and isinstance(response, dict)
                    and response.get("capability_id") == arguments["capability_id"]
                    and isinstance(execution, dict)
                    and execution.get("status") == "COMPLETED"
                ):
                    capability_id = arguments["capability_id"]
                    capability_ids.append(capability_id)
                    capability_invocations.append(
                        {
                            "capability_id": capability_id,
                            "input": arguments.get("payload"),
                            "output": response.get("output"),
                            "artifact_uris": response.get("artifact_uris"),
                            "assurance": response.get("assurance"),
                            "completeness": response.get("completeness"),
                        }
                    )
            if _contains_parameter_error(item):
                parameter_error_count += 1
        if (
            isinstance(event, dict)
            and event.get("type") == "turn.completed"
            and isinstance(event.get("usage"), dict)
        ):
            usage = event["usage"]
    return (
        calls,
        usage,
        {
            "tool_error_count": tool_error_count,
            "parameter_error_count": parameter_error_count,
            "successful_tool_calls": successful_calls,
            "capability_ids": capability_ids,
            "capability_invocations": capability_invocations,
        },
    )


def _as_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BenchmarkError(f"{field} must be an object")
    return value


def _as_pairs(value: Any, field: str) -> set[tuple[str, str]]:
    if not isinstance(value, list):
        raise BenchmarkError(f"{field} must be a list")
    try:
        return {(str(item[0]), str(item[1])) for item in value}
    except (IndexError, TypeError) as exc:
        raise BenchmarkError(f"{field} contains an invalid pair") from exc


def _as_paths(value: Any, field: str) -> set[tuple[str, ...]]:
    if not isinstance(value, list):
        raise BenchmarkError(f"{field} must be a list")
    try:
        return {tuple(str(part) for part in item) for item in value}
    except TypeError as exc:
        raise BenchmarkError(f"{field} contains an invalid path") from exc


def _integer_matrix(value: Any) -> list[list[int]]:
    if not isinstance(value, list):
        raise BenchmarkError("matrix entries must be a list")
    try:
        return [[int(entry) for entry in row] for row in value]
    except (TypeError, ValueError) as exc:
        raise BenchmarkError("matrix entries must be exact integers") from exc


def _check_candidate(
    actual: dict[str, Any],
    expected: Mapping[str, Any],
) -> None:
    kind = expected.get("kind")
    if kind in {"graph", "graph_paths"}:
        if set(map(str, actual.get("vertices", ()))) != set(expected["vertices"]):
            raise BenchmarkError("candidate vertices differ from the case")
        if _as_pairs(actual.get("arcs"), "candidate arcs") != _as_pairs(
            expected["arcs"],
            "expected arcs",
        ):
            raise BenchmarkError("candidate arcs differ from the case")
        if kind == "graph_paths":
            if actual.get("source") != expected["source"]:
                raise BenchmarkError("candidate source differs from the case")
            if set(map(str, actual.get("terminals", ()))) != set(expected["terminals"]):
                raise BenchmarkError("candidate terminals differ from the case")
            if _as_paths(
                actual.get("intended_paths"),
                "candidate intended paths",
            ) != _as_paths(expected["intended_paths"], "expected intended paths"):
                raise BenchmarkError("candidate intended paths differ from the case")
        return
    if kind == "matrix":
        if (
            actual.get("rows") != expected["rows"]
            or actual.get("cols") != expected["cols"]
        ):
            raise BenchmarkError("candidate matrix dimensions differ from the case")
        if _integer_matrix(actual.get("entries")) != expected["entries"]:
            raise BenchmarkError("candidate matrix entries differ from the case")
        return
    if kind == "lean":
        if actual.get("statement") != expected.get("statement"):
            raise BenchmarkError("Lean candidate statement differs from the case")
        if actual.get("environment") != expected.get("environment", "CORE"):
            raise BenchmarkError("Lean candidate environment differs from the case")
        proof = actual.get("proof")
        if not isinstance(proof, str) or not proof.strip():
            raise BenchmarkError("Lean candidate proof is empty")
        return
    if kind == "integer_range":
        if actual.get("lower_bound") != expected.get("lower_bound") or actual.get(
            "upper_bound"
        ) != expected.get("upper_bound"):
            raise BenchmarkError("candidate integer range differs from the case")
        return
    raise BenchmarkError(f"unsupported candidate expectation kind: {kind!r}")


def _check_claim(
    actual: dict[str, Any],
    expected: Mapping[str, Any],
) -> None:
    candidate = _as_object(expected.get("candidate"), "expected candidate")
    if candidate.get("kind") == "lean":
        if actual.get("statement") != candidate.get("statement"):
            raise BenchmarkError("Lean claim statement differs from the case")
        if actual.get("environment") != candidate.get("environment", "CORE"):
            raise BenchmarkError("Lean claim environment differs from the case")
        if actual.get("allowed_axioms") != expected.get("allowed_axioms", []):
            raise BenchmarkError("Lean claim has an unexpected trust base")
        return
    predicate = _as_object(actual.get("predicate"), "claim predicate")
    if actual.get("domain_id") != expected.get("domain_id"):
        raise BenchmarkError("claim domain differs from the case")
    if predicate.get("name") != expected.get("predicate"):
        raise BenchmarkError("claim predicate differs from the case")
    if "parameters" in expected and predicate.get("parameters") != expected.get(
        "parameters"
    ):
        raise BenchmarkError("claim predicate parameters differ from the case")


def _check_evidence(
    evidence: dict[str, Any],
    candidate: dict[str, Any],
    expected: Mapping[str, Any],
) -> str:
    evidence_kind = str(expected.get("evidence_kind", "WITNESS"))
    if evidence_kind == "WITNESS":
        if evidence.get("witness_format") != expected.get("witness_format"):
            raise BenchmarkError("witness format differs from the case")
        accepted_payloads = expected.get("accepted_witness_payloads")
        if (
            accepted_payloads is not None
            and evidence.get("payload") not in accepted_payloads
        ):
            raise BenchmarkError("witness payload does not match the public oracle")
        if expected.get("witness_format") == "erdos_straus.decomposition_table":
            payload = _as_object(evidence.get("payload"), "witness payload")
            table = payload.get("decompositions")
            if not isinstance(table, list):
                raise BenchmarkError("Erdős-Straus witness table is missing")
            expected_candidate = _as_object(
                expected.get("candidate"),
                "expected candidate",
            )
            expected_ns = set(
                range(
                    int(expected_candidate["lower_bound"]),
                    int(expected_candidate["upper_bound"]) + 1,
                )
            )
            actual_ns: set[int] = set()
            for row_value in table:
                row = _as_object(row_value, "Erdős-Straus witness row")
                try:
                    n, x, y, z = (
                        int(row["n"]),
                        int(row["x"]),
                        int(row["y"]),
                        int(row["z"]),
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise BenchmarkError(
                        "Erdős-Straus witness row is malformed"
                    ) from exc
                if min(x, y, z) <= 0:
                    raise BenchmarkError(
                        "Erdős-Straus witness has a nonpositive denominator"
                    )
                if 4 * x * y * z != n * (x * y + x * z + y * z):
                    raise BenchmarkError(
                        "Erdős-Straus witness fails the exact identity"
                    )
                if n in actual_ns:
                    raise BenchmarkError("Erdős-Straus witness contains duplicate n")
                actual_ns.add(n)
            if actual_ns != expected_ns:
                raise BenchmarkError(
                    "Erdős-Straus witness does not cover the exact range"
                )
        return evidence_kind
    if evidence_kind == "CERTIFICATE":
        if evidence.get("certificate_type") != expected.get("certificate_type"):
            raise BenchmarkError("certificate format differs from the case")
        payload = _as_object(evidence.get("payload"), "certificate payload")
        if candidate.get("statement") != payload.get("statement") or candidate.get(
            "proof"
        ) != payload.get("proof"):
            raise BenchmarkError("Lean certificate source differs from the candidate")
        if candidate.get("environment") != payload.get("environment"):
            raise BenchmarkError(
                "Lean certificate environment differs from the candidate"
            )
        if payload.get("allowed_axioms") != expected.get("allowed_axioms", []):
            raise BenchmarkError("Lean certificate has an unexpected trust base")
        return evidence_kind
    raise BenchmarkError(f"unsupported evidence kind: {evidence_kind}")


def _property_values(value: object) -> dict[str, Any]:
    properties = _as_object(value, "graph properties")
    normalized: dict[str, Any] = {}
    for name, result in properties.items():
        if isinstance(result, dict) and "value" in result:
            if result.get("exactness") != "EXACT":
                raise BenchmarkError(f"graph property {name} is not labeled exact")
            normalized[name] = result["value"]
        else:
            normalized[name] = result
    return normalized


def _require_descriptor(
    store: ArtifactStore,
    uri: str,
    *,
    kind: str,
    name: str,
) -> None:
    descriptor = _as_object(store.get(uri).payload, f"{name} descriptor")
    if (
        descriptor.get("descriptor_version") != "1"
        or descriptor.get("kind") != kind
        or descriptor.get("name") != name
        or descriptor.get("version") != "1"
    ):
        raise BenchmarkError(f"artifact does not use {name}@1")


def _find_graph_invocations(
    invocations: Sequence[Mapping[str, Any]],
    *,
    graph_uri: str,
    property_uri: str,
) -> Mapping[str, Any]:
    for search_index, search in enumerate(invocations):
        if search.get("capability_id") != "graph.search.atlas":
            continue
        search_output = search.get("output")
        search_artifacts = search.get("artifact_uris")
        search_assurance = search.get("assurance")
        search_completeness = search.get("completeness")
        if (
            not isinstance(search_output, dict)
            or not isinstance(search_artifacts, list)
            or graph_uri not in search_artifacts
            or not isinstance(search_output.get("candidates"), list)
            or not any(
                isinstance(candidate, dict) and candidate.get("graph_uri") == graph_uri
                for candidate in search_output["candidates"]
            )
            or not isinstance(search_assurance, dict)
            or search_assurance.get("level") != "COMPUTED"
            or not isinstance(search_completeness, dict)
            or search_completeness.get("status") != "COMPLETE"
        ):
            continue
        for computed in invocations[search_index + 1 :]:
            if computed.get("capability_id") != "graph.compute.properties":
                continue
            computed_input = computed.get("input")
            computed_output = computed.get("output")
            computed_artifacts = computed.get("artifact_uris")
            computed_assurance = computed.get("assurance")
            computed_completeness = computed.get("completeness")
            if (
                isinstance(computed_input, dict)
                and computed_input.get("graph_uri") == graph_uri
                and isinstance(computed_output, dict)
                and computed_output.get("graph_uri") == graph_uri
                and computed_output.get("property_artifact_uri") == property_uri
                and isinstance(computed_artifacts, list)
                and graph_uri in computed_artifacts
                and property_uri in computed_artifacts
                and isinstance(computed_assurance, dict)
                and computed_assurance.get("level") == "COMPUTED"
                and isinstance(computed_completeness, dict)
                and computed_completeness.get("status") == "COMPLETE"
            ):
                return computed
    raise BenchmarkError(
        "transcript lacks a successful search-to-property artifact flow"
    )


def _score_graph_capability_run(
    case: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    state_dir: Path,
    tool_calls: Sequence[str],
    capability_ids: Sequence[str],
    capability_invocations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    expected = _as_object(case.get("expected"), "case expected")
    if report.get("case_id") != case.get("case_id"):
        raise BenchmarkError("agent report case_id does not match the case")
    if report.get("assurance") != expected.get("assurance"):
        raise BenchmarkError("graph computation assurance differs from the case")
    if report.get("completeness") != expected.get("completeness"):
        raise BenchmarkError("graph search completeness differs from the case")
    if report.get("final_verification") != "UNVERIFIED":
        raise BenchmarkError("computed graph workflow was falsely certified")
    required_tools = case.get("required_tools")
    if not isinstance(required_tools, list):
        raise BenchmarkError("case required_tools must be a list")
    missing_tools = sorted(set(required_tools) - set(tool_calls))
    if missing_tools:
        raise BenchmarkError(
            f"transcript is missing MCP calls: {', '.join(missing_tools)}"
        )
    required_capabilities = case.get("required_capability_ids")
    if not isinstance(required_capabilities, list):
        raise BenchmarkError("case required_capability_ids must be a list")
    missing_capabilities = sorted(set(required_capabilities) - set(capability_ids))
    if missing_capabilities:
        raise BenchmarkError(
            "transcript is missing capability invocations: "
            + ", ".join(missing_capabilities)
        )

    graph_uri = _artifact_uri(report.get("graph_uri"), "graph_uri")
    property_uri = _artifact_uri(
        report.get("property_artifact_uri"),
        "property_artifact_uri",
    )
    store = ArtifactStore(state_dir)
    try:
        graph_artifact = store.get(graph_uri)
        property_artifact = store.get(property_uri)
        _require_descriptor(
            store,
            graph_artifact.manifest.schema_uri,
            kind="schema",
            name="jacobian.simple-undirected-graph",
        )
        _require_descriptor(
            store,
            graph_artifact.manifest.semantics_uri,
            kind="semantics",
            name="jacobian.simple-undirected-graph",
        )
        _require_descriptor(
            store,
            property_artifact.manifest.schema_uri,
            kind="schema",
            name="jacobian.graph-property-batch",
        )
        if (
            property_artifact.manifest.semantics_uri
            != graph_artifact.manifest.semantics_uri
        ):
            raise BenchmarkError("property artifact uses different graph semantics")
        schemas = SchemaRegistry(store)
        schemas.validate(graph_artifact.manifest.schema_uri, graph_artifact.payload)
        schemas.validate(
            property_artifact.manifest.schema_uri,
            property_artifact.payload,
        )
    except (SchemaRegistryError, StoreError) as exc:
        raise BenchmarkError(
            "reported graph artifacts fail contract validation"
        ) from exc
    graph_payload = _as_object(graph_artifact.payload, "graph payload")
    vertices = graph_payload.get("vertices")
    edges = graph_payload.get("edges")
    if not isinstance(vertices, list) or not isinstance(edges, list):
        raise BenchmarkError("graph payload is malformed")
    if len(set(vertices)) != len(vertices) or any(
        not isinstance(vertex, str) for vertex in vertices
    ):
        raise BenchmarkError("graph vertices are malformed")
    vertex_set = set(vertices)
    normalized_edges: list[tuple[str, str]] = []
    for edge in edges:
        if (
            not isinstance(edge, list)
            or len(edge) != 2
            or not all(isinstance(endpoint, str) for endpoint in edge)
        ):
            raise BenchmarkError("graph edge payload is malformed")
        source, target = edge
        if source not in vertex_set or target not in vertex_set or source >= target:
            raise BenchmarkError("graph edge violates simple-graph semantics")
        normalized_edges.append((source, target))
    if len(set(normalized_edges)) != len(normalized_edges):
        raise BenchmarkError("graph contains duplicate edges")
    graph = nx.Graph()
    graph.add_nodes_from(vertices)
    graph.add_edges_from(normalized_edges)
    degree_sequence = sorted((degree for _, degree in graph.degree), reverse=True)
    if (
        graph.number_of_nodes() != 5
        or graph.number_of_edges() != 4
        or not nx.is_connected(graph)
        or degree_sequence != [2, 2, 2, 1, 1]
    ):
        raise BenchmarkError("reported graph is not the five-vertex path")

    if graph_uri not in property_artifact.manifest.parents:
        raise BenchmarkError("property artifact is not bound to the graph")
    property_payload = _as_object(property_artifact.payload, "property payload")
    if property_payload.get("graph_uri") != graph_uri:
        raise BenchmarkError("property payload names another graph")
    wanted_properties = _as_object(expected.get("properties"), "expected properties")
    artifact_properties = _property_values(property_payload.get("properties"))
    report_properties = _property_values(report.get("properties"))
    property_invocation = _find_graph_invocations(
        capability_invocations,
        graph_uri=graph_uri,
        property_uri=property_uri,
    )
    invocation_output = _as_object(
        property_invocation.get("output"),
        "property invocation output",
    )
    invocation_properties = _property_values(invocation_output.get("properties"))
    if (
        artifact_properties != wanted_properties
        or report_properties != wanted_properties
        or invocation_properties != wanted_properties
    ):
        raise BenchmarkError("graph properties differ from the frozen oracle")
    return {
        "passed": True,
        "checks": [
            "computed assurance without false certification",
            "required multi-call capability sequence",
            "five-vertex path up to relabeling",
            "bound exact property artifact",
        ],
        "case_id": case["case_id"],
        "graph_uri": graph_uri,
        "property_artifact_uri": property_uri,
    }


def score_run(
    case: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    state_dir: Path,
    tool_calls: Sequence[str],
    capability_ids: Sequence[str] = (),
    capability_invocations: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    if case.get("case_type") == "graph_capability":
        return _score_graph_capability_run(
            case,
            report,
            state_dir=state_dir,
            tool_calls=tool_calls,
            capability_ids=capability_ids,
            capability_invocations=capability_invocations,
        )
    expected = _as_object(case.get("expected"), "case expected")
    checks: list[str] = []
    if report.get("case_id") != case.get("case_id"):
        raise BenchmarkError("agent report case_id does not match the case")
    if report.get("conclusion") != expected.get("conclusion"):
        raise BenchmarkError("agent report conclusion does not match the oracle")
    if report.get("evaluation_verification") != "UNVERIFIED":
        raise BenchmarkError("evaluation was not reported as UNVERIFIED")
    if report.get("witness_search_verification") != "UNVERIFIED":
        raise BenchmarkError("witness search was not reported as UNVERIFIED")
    if report.get("final_verification") != "VERIFIED":
        raise BenchmarkError("final result was not reported as VERIFIED")
    checks.append("agent assurance labels")

    feedback = _as_object(report.get("feedback"), "agent feedback")
    feedback_fields = {
        "tooling_strengths",
        "tooling_gaps",
        "domain_knowledge_gaps",
        "suggested_improvements",
    }
    if set(feedback) != feedback_fields or not all(
        isinstance(feedback[field], list)
        and all(isinstance(item, str) for item in feedback[field])
        for field in feedback_fields
    ):
        raise BenchmarkError("agent feedback has an invalid structure")
    checks.append("structured agent feedback")

    required_tools = case.get("required_tools")
    if not isinstance(required_tools, list) or not all(
        isinstance(tool, str) for tool in required_tools
    ):
        raise BenchmarkError("case required_tools must be a string list")
    missing_tools = sorted(set(required_tools) - set(tool_calls))
    if missing_tools:
        raise BenchmarkError(
            f"transcript is missing MCP calls: {', '.join(missing_tools)}"
        )
    checks.append("required MCP tool sequence")

    claim_uri = _artifact_uri(report.get("claim_uri"), "claim_uri")
    candidate_uri = _artifact_uri(report.get("candidate_uri"), "candidate_uri")
    evidence_uri = _artifact_uri(report.get("evidence_uri"), "evidence_uri")
    record_uri = _artifact_uri(
        report.get("verification_record_uri"),
        "verification_record_uri",
    )
    store = ArtifactStore(state_dir)
    try:
        claim = store.get(claim_uri)
        candidate = store.get(candidate_uri)
        evidence = store.get(evidence_uri)
        record = store.get(record_uri)
        semantics = store.get(claim.manifest.semantics_uri)
    except StoreError as exc:
        raise BenchmarkError("reported artifact URI is unavailable") from exc

    claim_payload = _as_object(claim.payload, "claim payload")
    _check_claim(claim_payload, expected)
    candidate_payload = _as_object(candidate.payload, "candidate payload")
    _check_candidate(
        candidate_payload,
        _as_object(expected.get("candidate"), "expected candidate"),
    )
    checks.append("known case claim and candidate")

    evidence_payload = _as_object(evidence.payload, "evidence payload")
    record_payload = _as_object(record.payload, "verification record")
    evidence_kind = _check_evidence(
        evidence_payload,
        candidate_payload,
        expected,
    )
    if (
        record_payload.get("conclusion") != expected.get("conclusion")
        or record_payload.get("evidence_kind") != evidence_kind
        or record_payload.get("evidence_uri") != evidence_uri
    ):
        raise BenchmarkError("verification record does not bind the expected result")
    checks.append("known-answer evidence and verification record")

    bindings = _as_object(record_payload.get("bindings"), "record bindings")
    if bindings != evidence_payload.get("bindings"):
        raise BenchmarkError("record and witness bindings differ")
    if bindings.get("claim_digest") != claim.manifest.object_digest:
        raise BenchmarkError("verification record is bound to another claim")
    if bindings.get("candidate_digest") != candidate.manifest.object_digest:
        raise BenchmarkError("verification record is bound to another candidate")
    if bindings.get("semantics_digest") != semantics.manifest.object_digest:
        raise BenchmarkError("verification record is bound to other semantics")
    checks.append("claim, candidate, semantics, and evidence bindings")

    return {
        "passed": True,
        "checks": checks,
        "case_id": case["case_id"],
        "verification_record_uri": record_uri,
        "evidence_uri": evidence_uri,
    }


def _run_case(
    case: dict[str, Any],
    *,
    run_root: Path,
    codex_command: str,
    model: str | None,
    reasoning_effort: str,
    timeout_seconds: int,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    case_root = run_root / case_id.lower()
    state_dir = case_root / "state"
    transcript = case_root / "transcript.jsonl"
    stderr_path = case_root / "codex.stderr.log"
    report_path = case_root / "agent-report.json"
    feedback_path = case_root / "feedback.json"
    case_root.mkdir(parents=True)
    state_dir.mkdir()
    graph_case = case.get("case_type") == "graph_capability"
    if graph_case:
        prompt = GRAPH_SYSTEM_TASK.format(
            case_id=case_id,
            prompt=case["prompt"],
        )
        report_schema = GRAPH_REPORT_SCHEMA
        tool_profile = "capabilities"
    else:
        prompt = SYSTEM_TASK.format(
            agent_contract_uri=f"reference://domain/{case['reference_name']}",
            case_id=case_id,
            prompt=case["prompt"],
        )
        report_schema = REPORT_SCHEMA
        tool_profile = "verification"
    command = [
        codex_command,
        "exec",
        "--ephemeral",
        "--sandbox",
        "workspace-write",
        "--color",
        "never",
        "--json",
        "--output-schema",
        str(report_schema),
        "--output-last-message",
        str(report_path),
        "-c",
        "mcp_servers.jacobian_local.env.JACOBIAN_STATE_DIR="
        + json.dumps(str(state_dir)),
        "-c",
        "mcp_servers.jacobian_local.args="
        + json.dumps(
            [
                "run",
                "jacobian-mcp",
                "--tool-profile",
                tool_profile,
            ]
        ),
        "-c",
        "model_reasoning_effort=" + json.dumps(reasoning_effort),
    ]
    if model is not None:
        command.extend(["--model", model])
    command.append("-")
    environment = dict(os.environ)
    environment["JACOBIAN_STATE_DIR"] = str(state_dir)

    started_at = _timestamp()
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=environment,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        exit_code: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        operational_error: str | None = None
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        operational_error = f"Codex exceeded {timeout_seconds} seconds"
    elapsed = time.monotonic() - started
    transcript.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    tool_calls, usage, transcript_metrics = parse_transcript(transcript)

    score: dict[str, Any]
    report: dict[str, Any] | None = None
    if operational_error is not None:
        score = {"passed": False, "error": operational_error}
    elif exit_code != 0:
        score = {"passed": False, "error": f"Codex exited with status {exit_code}"}
    else:
        try:
            report = _load_json_object(report_path)
            feedback = _as_object(report.get("feedback"), "agent feedback")
            feedback_path.write_text(
                json.dumps(feedback, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            score = score_run(
                case,
                report,
                state_dir=state_dir,
                tool_calls=transcript_metrics["successful_tool_calls"],
                capability_ids=transcript_metrics["capability_ids"],
                capability_invocations=transcript_metrics["capability_invocations"],
            )
        except (BenchmarkError, OSError, json.JSONDecodeError) as exc:
            score = {"passed": False, "error": str(exc)}

    result = {
        **metadata,
        "case_id": case_id,
        "case_version": case["version"],
        "condition": "kernel",
        "started_at": started_at,
        "completed_at": _timestamp(),
        "elapsed_seconds": round(elapsed, 3),
        "exit_code": exit_code,
        "tool_calls": tool_calls,
        "tool_call_count": len(tool_calls),
        **transcript_metrics,
        "usage": usage,
        "correct": bool(score.get("passed", False)),
        "false_certification": bool(
            report is not None
            and report.get("final_verification") == "VERIFIED"
            and not score.get("passed", False)
        ),
        "agent_report": report,
        "score": score,
        "artifacts": {
            "state_dir": str(state_dir.relative_to(run_root)),
            "transcript": str(transcript.relative_to(run_root)),
            "stderr": str(stderr_path.relative_to(run_root)),
            "agent_report": str(report_path.relative_to(run_root)),
            "feedback": str(feedback_path.relative_to(run_root)),
        },
    }
    (case_root / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run public Jacobian cases through a real Codex MCP client.",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="case ID to run; repeat or use 'all' (default)",
    )
    parser.add_argument("--model", help="optional Codex model override")
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high"),
        default="medium",
        help="Codex reasoning budget; fixed explicitly for comparable runs",
    )
    parser.add_argument("--codex-command", default="codex")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_RESULTS_ROOT,
    )
    args = parser.parse_args(argv)
    cases = load_cases(args.case)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_root = args.output_dir.resolve() / run_id
    run_root.mkdir(parents=True)
    metadata = {
        "benchmark": "jacobian-agent-mcp-known-answer-pilot",
        "repository_commit": _run_text(["git", "rev-parse", "HEAD"]),
        "repository_dirty": bool(_run_text(["git", "status", "--porcelain"])),
        "dependency_lock_digest": _digest_file(PROJECT_ROOT / "uv.lock"),
        "codex_version": _run_text([args.codex_command, "--version"]),
        "requested_model": args.model or "configured-default",
        "reasoning_effort": args.reasoning_effort,
        "random_seed_policy": "provider-controlled; no Codex seed option",
    }
    results = [
        _run_case(
            case,
            run_root=run_root,
            codex_command=args.codex_command,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            timeout_seconds=args.timeout_seconds,
            metadata=metadata,
        )
        for case in cases
    ]
    summary = {
        **metadata,
        "run_id": run_id,
        "condition": "kernel",
        "cases": [
            {
                "case_id": result["case_id"],
                "passed": result["score"].get("passed", False),
                "elapsed_seconds": result["elapsed_seconds"],
                "tool_call_count": result["tool_call_count"],
                "tool_error_count": result["tool_error_count"],
                "parameter_error_count": result["parameter_error_count"],
                "false_certification": result["false_certification"],
                "usage": result["usage"],
                "error": result["score"].get("error"),
            }
            for result in results
        ],
        "passed": all(result["score"].get("passed", False) for result in results),
    }
    summary_path = run_root / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(summary_path)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
