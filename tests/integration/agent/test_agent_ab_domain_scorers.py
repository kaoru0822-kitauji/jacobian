from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from benchmarks import agent_ab as benchmark
from tests.integration.agent._agent_ab_support import (
    _hnf_case,
    _hnf_report,
    _linear_case,
    _linear_report,
    _polynomial_normalization_case,
    _polynomial_normalization_report,
    _runtime_from_template,
    _sat_producer,
    _sat_report,
)

from jacobian.contracts.capabilities import (
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.contracts.sat import SatResourceBudget
from jacobian.runtime import CheckerAuthorityMode


def test_ab_graph_scorer_accepts_any_valid_witness_and_durable_flow(
    tmp_path: Path,
    runtime_store_template_with_references: Path,
) -> None:
    load_cases = benchmark.load_cases
    score_report = benchmark.score_report
    case = load_cases(["GRAPH-COUNTEREXAMPLE-AB-001"])[0]
    state_dir, runtime = _runtime_from_template(
        tmp_path,
        runtime_store_template_with_references,
        name="state",
        checker_authority=CheckerAuthorityMode.NONE,
    )
    searched = runtime.core.capabilities.invoke(
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
    computed = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.compute.properties",
            mode=CapabilityMode.EXPLORE,
            input={"graph_uri": graph_uri, "properties": requested},
        )
    )
    property_uri = cast(str, computed.output["property_artifact_uri"])
    graph = runtime.core.store.get(graph_uri).payload
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
    load_cases = benchmark.load_cases
    score_report = benchmark.score_report
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

    with pytest.raises(benchmark.BenchmarkError, match="falsely certified"):
        score_report(
            case,
            report,
            condition="control",
            state_dir=tmp_path,
            mcp_calls=[],
        )


def test_ab_graph_scorer_enforces_exact_vertex_order(tmp_path: Path) -> None:
    load_cases = benchmark.load_cases
    score_report = benchmark.score_report
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

    with pytest.raises(benchmark.BenchmarkError, match="order constraint"):
        score_report(
            case,
            report,
            condition="control",
            state_dir=tmp_path,
            mcp_calls=[],
        )


def test_ab_partition_scorer_requires_checker_backed_coverage(
    tmp_path: Path, runtime_store_template_with_references: Path
) -> None:
    load_cases = benchmark.load_cases
    score_report = benchmark.score_report
    case = load_cases(["FINITE-PARTITION-AB-001"])[0]
    state_dir, runtime = _runtime_from_template(
        tmp_path,
        runtime_store_template_with_references,
        name="state",
    )
    cases = [
        {"case_id": "r0", "members": ["0", "3", "6", "9"]},
        {"case_id": "r1", "members": ["1", "4", "7", "10"]},
        {"case_id": "r2", "members": ["2", "5", "8", "11"]},
    ]
    result = runtime.core.capabilities.invoke(
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
    with pytest.raises(
        benchmark.BenchmarkError,
        match="exact verified capability trace",
    ):
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


def test_ab_partition_scorer_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    load_cases = benchmark.load_cases
    score_report = benchmark.score_report
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

    with pytest.raises(benchmark.BenchmarkError, match="distinct and non-empty"):
        score_report(
            case,
            report,
            condition="control",
            state_dir=tmp_path,
            mcp_calls=[],
        )


def test_ab_sat_scorer_requires_ordered_checker_bound_assignment(
    tmp_path: Path,
    runtime_store_template_with_references: Path,
) -> None:
    score_report = benchmark.score_report
    case = {
        "case_id": "SAT-PRIVATE-TEST-001",
        "version": "1",
        "task_type": "sat_decision",
        "prompt": "Decide the private CNF.",
        "variable_names": ["a", "b"],
        "clauses": [[1, 2], [-1, 2]],
        "expected": {"status": "SATISFIABLE"},
    }
    state_dir, runtime = _runtime_from_template(
        tmp_path,
        runtime_store_template_with_references,
        name="state",
    )
    cnf = runtime.core.sat.put_cnf(
        variable_names=("a", "b"),
        clauses=((1, 2), (-1, 2)),
    )
    assignment = runtime.core.sat.put_assignment(
        cnf_uri=cnf.artifact_uri,
        values=(False, True),
        producer=_sat_producer(),
        resource_budget=SatResourceBudget(wall_seconds=5),
    )
    verified = runtime.core.capabilities.invoke(
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
    runtime_store_template_with_references: Path,
) -> None:
    score_report = benchmark.score_report
    case = _linear_case()
    state_dir, runtime = _runtime_from_template(
        tmp_path,
        runtime_store_template_with_references,
        name="state",
    )
    found = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="linear.rational_solution.find",
            mode=CapabilityMode.EXPLORE,
            input={"system": case["system"]},
        )
    )
    solution_uri = cast(str, found.output["solution_uri"])
    system_uri = cast(str, found.output["system_uri"])
    verified = runtime.core.capabilities.invoke(
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
        benchmark.BenchmarkError,
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
    runtime_store_template_with_references: Path,
) -> None:
    score_report = benchmark.score_report
    case = _hnf_case()
    state_dir, runtime = _runtime_from_template(
        tmp_path,
        runtime_store_template_with_references,
        name="state",
    )
    computed = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.normal_form.hermite",
            mode=CapabilityMode.EXPLORE,
            input={"matrix": case["matrix"]},
        )
    )
    normal_form_uri = cast(str, computed.output["normal_form_uri"])
    matrix_uri = cast(str, computed.output["matrix_uri"])
    verified = runtime.core.capabilities.invoke(
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
        benchmark.BenchmarkError,
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
    runtime_store_template_with_references: Path,
) -> None:
    score_report = benchmark.score_report
    case = _polynomial_normalization_case()
    state_dir, runtime = _runtime_from_template(
        tmp_path,
        runtime_store_template_with_references,
        name="state",
    )
    computed = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="polynomial.expression.normalize",
            mode=CapabilityMode.EXPLORE,
            input={"expression": case["expression"]},
        )
    )
    expression_uri = cast(str, computed.output["expression_uri"])
    normalization_uri = cast(str, computed.output["normalization_uri"])
    verified = runtime.core.capabilities.invoke(
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
        benchmark.BenchmarkError,
        match="held-out exact oracle",
    ):
        score_report(
            case,
            wrong,
            condition="control",
            state_dir=state_dir,
            mcp_calls=[],
        )


def test_ab_sat_scorer_rejects_unbound_verified_claim(
    tmp_path: Path, runtime_store_template_with_references: Path
) -> None:
    score_report = benchmark.score_report
    benchmark_error = benchmark.BenchmarkError
    case = {
        "case_id": "SAT-PRIVATE-TEST-002",
        "version": "1",
        "task_type": "sat_decision",
        "prompt": "Decide the private CNF.",
        "variable_names": ["a"],
        "clauses": [[1]],
        "expected": {"status": "SATISFIABLE"},
    }
    state_dir, runtime = _runtime_from_template(
        tmp_path,
        runtime_store_template_with_references,
        name="state",
    )
    cnf = runtime.core.sat.put_cnf(variable_names=("a",), clauses=((1,),))
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


def test_ab_distance_composition_scorer_requires_bound_matrix_replay(
    tmp_path: Path,
    runtime_store_template_with_references: Path,
) -> None:
    case = benchmark.load_cases(["GRAPH-DISTANCE-COMPOSITION-AB-001"])[0]
    state_dir, runtime = _runtime_from_template(
        tmp_path,
        runtime_store_template_with_references,
        name="distance-state",
    )
    computed = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.distance_matrix.compute",
            input={"graph": case["graph"]},
        )
    )
    verified = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.distance_matrix.verify",
            mode=CapabilityMode.VERIFY,
            input={"result_uri": computed.output["result_uri"]},
        )
    )
    report = {
        "case_id": case["case_id"],
        "maximum_degree_vertices": ["4"],
        "distance_to_set": [
            {"vertex": "0", "distance": 1},
            {"vertex": "1", "distance": 1},
            {"vertex": "2", "distance": 1},
            {"vertex": "3", "distance": 1},
            {"vertex": "4", "distance": 0},
            {"vertex": "5", "distance": 2},
        ],
        "maximum_distance_to_set": 2,
        "maximizing_vertices": ["5"],
        "assurance": "SELF_CHECKED",
        "final_verification": "UNVERIFIED",
        "distance_matrix_uri": computed.output["result_uri"],
        "verification_record_uri": verified.output["verification_record_uri"],
        "limitations": ["public answer-visible harness validation"],
        "feedback": {
            "reasoning_focus": [],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }
    invocations = [
        {
            "capability_id": "graph.distance_matrix.compute",
            "input": {"graph": case["graph"]},
            "output": computed.output,
            "artifact_uris": list(computed.artifact_uris),
            "assurance": computed.assurance.model_dump(mode="json"),
        },
        {
            "capability_id": "graph.distance_matrix.verify",
            "input": {"result_uri": computed.output["result_uri"]},
            "output": verified.output,
            "artifact_uris": list(verified.artifact_uris),
            "assurance": verified.assurance.model_dump(mode="json"),
        },
    ]

    score = benchmark.score_report(
        case,
        report,
        condition="treatment",
        state_dir=state_dir,
        mcp_calls=["capability.describe", "capability.invoke", "capability.invoke"],
        capability_attempt_ids=[
            "graph.distance_matrix.compute",
            "graph.distance_matrix.verify",
        ],
        capability_invocations=invocations,
    )

    assert score == {
        "passed": True,
        "false_certification": False,
        "replay_success": True,
        "checks": [
            "independent standard-library distance-to-set oracle",
            "durable graph and matrix binding",
            "ordered compute-to-verify trace",
            "independent checker replay",
        ],
    }

    control = {
        **report,
        "distance_matrix_uri": None,
        "verification_record_uri": None,
    }
    control_score = benchmark.score_report(
        case,
        control,
        condition="control",
        state_dir=tmp_path / "unused-control",
        mcp_calls=["capability.describe"],
    )
    assert control_score["passed"] is True
    assert control_score["replay_success"] is False

    forged = {**report, "maximum_distance_to_set": 3}
    with pytest.raises(benchmark.BenchmarkError, match="differs from the oracle"):
        benchmark.score_report(
            case,
            forged,
            condition="treatment",
            state_dir=state_dir,
            mcp_calls=["capability.invoke"],
        )
