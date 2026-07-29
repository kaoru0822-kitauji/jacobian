from __future__ import annotations

import json
from pathlib import Path

import pytest

from jacobian.contracts.capabilities import CapabilityMode, CapabilityRequest
from jacobian.contracts.results import ExecutionStatus
from jacobian.runtime.model import JacobianRuntime

_ROOT = Path(__file__).parents[3]
_PILOT = _ROOT / "benchmarks" / "example_cases" / "pilot.json"

pytestmark = pytest.mark.usefixtures("attached_complete_runtime")

_REQUIRED_CAPABILITIES = {
    "finite.coverage.verify",
    "graph.compute.properties",
    "graph.invariant.diameter.compute",
    "knowledge.search",
    "lean.proof_state.apply_tactic",
    "lean.statement.propose",
    "polynomial.expression.normalize",
    "polynomial.expression_normalization.verify",
    "polynomial.identity.verify",
    "polynomial.map.inverse.candidate_synthesize",
    "polynomial.map.inverse.verify",
    "search.enumerate",
}


def _pilot() -> dict[str, object]:
    return json.loads(_PILOT.read_text())


def test_pilot_manifest_is_small_source_backed_and_review_gated() -> None:
    pilot = _pilot()
    assert pilot["pilot_version"] == "1"
    assert pilot["human_review"] == "REQUIRED"

    cases = pilot["cases"]
    assert isinstance(cases, list)
    assert {case["capability_id"] for case in cases} == _REQUIRED_CAPABILITIES
    assert len(cases) == len(_REQUIRED_CAPABILITIES)

    for case in cases:
        assert case["valid_case"]
        assert case["invalid_or_boundary_case"]
        assert case["status"] in {"PILOT", "KNOWN_REGRESSION"}
        assert case["origin"] in {
            "DIRECT_INVOCATION",
            "ADAPTED_INVOCATION",
            "SOURCE_DERIVED_CONTENT",
            "GENERATED",
        }
        source = _ROOT / case["source"]
        assert source.is_file()
        assert case["validation"][:2] == ["SCHEMA", "EXECUTION"]


def test_installed_public_pilot_examples_use_descriptor_mechanism(
    attached_complete_runtime: JacobianRuntime,
) -> None:
    runtime = attached_complete_runtime
    pilot = _pilot()
    installed = {
        descriptor.capability_id: descriptor
        for descriptor in runtime.core.capabilities.catalog().capabilities
    }

    checked = set()
    for case in pilot["cases"]:
        example_name = case["public_example"]
        descriptor = installed.get(case["capability_id"])
        if example_name is None or descriptor is None:
            continue
        assert example_name in {
            example.name for example in descriptor.invocation_examples
        }
        checked.add(case["capability_id"])

    assert checked == {
        "knowledge.search",
        "lean.statement.propose",
        "polynomial.expression.normalize",
        "polynomial.identity.verify",
        "polynomial.map.inverse.candidate_synthesize",
    }


def test_search_pilot_boundaries_use_typed_public_results(
    attached_complete_runtime: JacobianRuntime,
) -> None:
    runtime = attached_complete_runtime
    artifact_uri = "artifact://sha256/" + "a" * 64
    payload = {
        "claim_uri": artifact_uri,
        "plugin_id": artifact_uri,
        "bounds": {},
        "budget": {"candidates_max": 1, "wall_seconds": 1},
    }

    unsupported = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="search.enumerate",
            mode=CapabilityMode.VERIFY,
            input=payload,
        )
    )
    invalid_budget = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="search.enumerate",
            input={
                **payload,
                "budget": {"candidates_max": 0, "wall_seconds": 1},
            },
        )
    )

    assert unsupported.execution.status is ExecutionStatus.ERROR
    assert unsupported.diagnostics[0].code == "UNSUPPORTED_MODE"
    assert invalid_budget.execution.status is ExecutionStatus.ERROR
    assert invalid_budget.diagnostics[0].code == "INVALID_REQUEST"
