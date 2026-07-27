from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel
from jacobian.plugin_execution import PluginExecutionResult

pytestmark = pytest.mark.integration


@pytest.mark.integration
@pytest.mark.contract
def test_graph_counterexample_shrink_records_verified_steps_and_exact_local_scope(
    tmp_path: Path,
    kernel_store_template_with_references: Path,
) -> None:
    kernel, graph_uri = _kernel_with_redundant_odd_cycle(
        tmp_path,
        template=kernel_store_template_with_references,
    )

    result = _shrink(kernel, graph_uri)

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE
    assert kernel.store.get(result.output["final_graph_uri"]).payload == {
        "graph_schema_version": "1",
        "vertices": ["a", "b", "c"],
        "edges": [["a", "b"], ["a", "c"], ["b", "c"]],
    }
    accepted = [
        attempt
        for attempt in result.output["attempts"]
        if attempt["outcome"] == "ACCEPTED_VERIFIED"
    ]
    assert [attempt["deleted_vertex"] for attempt in accepted] == ["d"]
    assert all(
        attempt["verification_record_uri"] in result.artifact_uris
        for attempt in accepted
    )
    scope = result.output["local_minimality_scope"]
    assert scope["tested_vertex_deletions"] == ["a", "b", "c"]
    assert scope["tested_edge_deletions"] == [
        ["a", "b"],
        ["a", "c"],
        ["b", "c"],
    ]
    assert scope["complete_for_requested_reducers"] is True
    assert scope["one_step_locally_minimal"] is True
    assert scope["global_minimality_claimed"] is False
    trace = kernel.store.get(result.output["trace_uri"])
    assert trace.payload["attempts"] == result.output["attempts"]
    assert trace.payload["local_minimality_scope"] == scope


@pytest.mark.integration
@pytest.mark.contract
def test_graph_counterexample_shrink_budget_reports_only_tested_scope(
    tmp_path: Path,
    kernel_store_template_with_references: Path,
) -> None:
    kernel, graph_uri = _kernel_with_redundant_odd_cycle(tmp_path, template=kernel_store_template_with_references)

    result = _shrink(kernel, graph_uri, evaluation_budget=2)

    scope = result.output["local_minimality_scope"]
    assert scope["complete_for_requested_reducers"] is False
    assert scope["one_step_locally_minimal"] is False
    assert scope["global_minimality_claimed"] is False
    assert scope["untested_vertex_deletions"] or scope["untested_edge_deletions"]


@pytest.mark.integration
@pytest.mark.contract
def test_graph_counterexample_shrink_timeout_returns_incumbent_without_minimality(
    tmp_path: Path,
    kernel_store_template_with_references: Path,
) -> None:
    kernel, graph_uri = _kernel_with_redundant_odd_cycle(tmp_path, template=kernel_store_template_with_references)
    kernel.shrinking.executor = _TimeoutExecutor()  # type: ignore[assignment]

    result = _shrink(kernel, graph_uri)

    assert result.execution.status is ExecutionStatus.TIMEOUT
    assert result.output["final_graph_uri"] == graph_uri
    assert result.output["attempts"] == []
    assert result.output["local_minimality_scope"]["one_step_locally_minimal"] is False
    assert result.assurance.level is CapabilityAssuranceLevel.HEURISTIC


@pytest.mark.integration
@pytest.mark.contract
def test_graph_counterexample_shrink_requires_compatible_registered_checker(
    tmp_path: Path,
    kernel_store_template_with_references: Path,
) -> None:
    kernel, graph_uri = _kernel_with_redundant_odd_cycle(tmp_path, template=kernel_store_template_with_references)
    incompatible = kernel.graph.degree_sequence_checker_id
    assert incompatible is not None

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.counterexample.shrink",
            input={
                "graph_uri": graph_uri,
                "property_id": "graph.property.non_bipartite",
                "property_checker_id": incompatible,
                "reducers": ["delete_vertex", "delete_edge"],
                "evaluation_budget": 20,
            },
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.diagnostics[0].code == "GRAPH_PROPERTY_CHECKER_INVALID"


@pytest.mark.integration
@pytest.mark.contract
def test_graph_counterexample_shrink_fails_closed_on_tampered_graph(
    tmp_path: Path,
    kernel_store_template_with_references: Path,
) -> None:
    kernel, graph_uri = _kernel_with_redundant_odd_cycle(tmp_path, template=kernel_store_template_with_references)
    graph = kernel.store.get(graph_uri)
    kernel.store._blob_path(graph.manifest.payload_digest).write_bytes(b"tampered")

    result = _shrink(kernel, graph_uri)

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.output["error"]["code"] == "GRAPH_SHRINK_INPUT_INVALID"
    assert result.diagnostics[0].code == "GRAPH_SHRINK_INPUT_INVALID"


@pytest.mark.integration
@pytest.mark.contract
def test_graph_counterexample_shrink_rejects_unrelated_reducer_edits(
    tmp_path: Path,
    kernel_store_template_with_references: Path,
) -> None:
    kernel, graph_uri = _kernel_with_redundant_odd_cycle(tmp_path, template=kernel_store_template_with_references)
    kernel.shrinking.executor = _UnrelatedEditExecutor()  # type: ignore[assignment]

    result = _shrink(kernel, graph_uri)

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["final_graph_uri"] == graph_uri
    assert result.output["attempts"][0]["outcome"] == "INVALID_REDUCTION"
    assert result.output["attempts"][0]["verification_record_uri"] is None
    assert "exact single-vertex deletion" in result.output["attempts"][0]["detail"]


@pytest.mark.integration
@pytest.mark.contract
@pytest.mark.slow
def test_graph_counterexample_shrink_order_is_deterministic(tmp_path: Path, kernel_store_template_with_references: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first, first_graph = _kernel_with_redundant_odd_cycle(first_root, template=kernel_store_template_with_references)
    second, second_graph = _kernel_with_redundant_odd_cycle(second_root, template=kernel_store_template_with_references)

    first_result = _shrink(first, first_graph)
    second_result = _shrink(second, second_graph)

    def signature(output: dict[str, Any]) -> list[tuple[Any, ...]]:
        return [
            (
                attempt["reducer"],
                attempt["deleted_vertex"],
                attempt["deleted_edge"],
                attempt["outcome"],
            )
            for attempt in output["attempts"]
        ]

    assert signature(first_result.output) == signature(second_result.output)
    assert first.store.get(first_result.output["final_graph_uri"]).payload == (
        second.store.get(second_result.output["final_graph_uri"]).payload
    )


class _TimeoutExecutor:
    def run(self, **_: Any) -> PluginExecutionResult:
        return PluginExecutionResult(
            status=ExecutionStatus.TIMEOUT,
            output=None,
            diagnostics="",
            detail="fixture reducer timeout",
            runtime_ms=1,
        )


class _UnrelatedEditExecutor:
    def run(self, **_: Any) -> PluginExecutionResult:
        return PluginExecutionResult(
            status=ExecutionStatus.COMPLETED,
            output={
                "response_version": "1",
                "current_objectives": {"vertices": 4, "edges": 4},
                "reductions": [
                    {
                        "reducer": "delete_vertex",
                        "payload": {
                            "graph_schema_version": "1",
                            "vertices": ["a", "b", "c", "e"],
                            "edges": [
                                ["a", "b"],
                                ["a", "c"],
                                ["b", "c"],
                            ],
                        },
                        "objectives": {"vertices": 3, "edges": 3},
                    }
                ],
            },
            diagnostics="",
            detail=None,
            runtime_ms=1,
        )


def _kernel_with_redundant_odd_cycle(
    root: Path,
    *,
    template: Path,
) -> tuple[JacobianKernel, str]:
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template, root, dirs_exist_ok=True)
    kernel = JacobianKernel(root, install_references=True)
    graph = kernel.artifacts.put(
        schema_uri=kernel.graph.graph_schema_uri,
        semantics_uri=kernel.graph.semantics_uri,
        payload={
            "graph_schema_version": "1",
            "vertices": ["a", "b", "c", "d"],
            "edges": [["a", "b"], ["a", "c"], ["b", "c"], ["c", "d"]],
        },
        summary="non-bipartite graph with one redundant leaf",
    )
    return kernel, graph.artifact_uri


def _shrink(
    kernel: JacobianKernel,
    graph_uri: str,
    *,
    evaluation_budget: int = 20,
) -> Any:
    checker_id = kernel.graph_shrinking.property_checker_id
    assert checker_id is not None
    return kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.counterexample.shrink",
            input={
                "graph_uri": graph_uri,
                "property_id": "graph.property.non_bipartite",
                "property_checker_id": checker_id,
                "reducers": ["delete_vertex", "delete_edge"],
                "evaluation_budget": evaluation_budget,
            },
        )
    )
