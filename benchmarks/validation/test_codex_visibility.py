"""Regression coverage for the stateless MCP visibility evaluator."""

from __future__ import annotations

from pathlib import Path

from benchmarks.tooling.codex_visibility import (
    AdoptionExpectation,
    CueLevel,
    VisibilityCase,
    classify_visibility,
    load_suite,
    surface_snapshot_digest,
)

from jacobian.catalog.builtins import BUILTIN_TOOLS


def test_completed_math_run_satisfies_visibility_without_a_verification_record() -> (
    None
):
    case = VisibilityCase(
        case_id="determinant",
        cue_level=CueLevel.EXPLICIT,
        prompt="Compute a determinant.",
        expectation=AdoptionExpectation.USE,
        expected_operation_ids=("matrix.determinant.compute",),
    )

    classification = classify_visibility(
        case,
        {
            "operation_attempt_ids": ["matrix.determinant.compute"],
            "operation_ids": ["matrix.determinant.compute"],
            "operation_invocations": [
                {
                    "operation_id": "matrix.determinant.compute",
                    "output": {"determinant": "-2"},
                }
            ],
            "mcp_calls": ["math.run"],
        },
    )

    assert classification["contract_satisfied"] is True
    assert "verified" not in classification["observed"]


def test_abstention_rejects_operation_telemetry_even_without_mcp_call_names() -> None:
    case = VisibilityCase(
        case_id="abstain",
        cue_level=CueLevel.LATENT,
        prompt="Explain a matrix.",
        expectation=AdoptionExpectation.ABSTAIN,
    )

    classification = classify_visibility(
        case,
        {"operation_attempt_ids": ["matrix.rank.compute"]},
    )

    assert classification["observed"]["abstained"] is False
    assert classification["contract_satisfied"] is False


def test_malformed_math_run_does_not_hide_direct_operation_calls() -> None:
    case = VisibilityCase(
        case_id="determinant",
        cue_level=CueLevel.EXPLICIT,
        prompt="Compute a determinant.",
        expected_operation_ids=("matrix.determinant.compute",),
    )

    classification = classify_visibility(
        case,
        {
            "mcp_calls": ["math.run", "matrix.determinant.compute"],
            "operation_attempt_ids": [],
            "direct_operation_call_count": 1,
        },
    )

    assert classification["math_run_call_count"] == 1
    assert classification["direct_operation_call_count"] == 1


def test_surface_snapshot_digest_accepts_the_current_catalog_shape() -> None:
    surface = {
        "server": {"name": "jacobian", "version": "1.0.0"},
        "instructions": "Use math.find and math.run.",
        "tools": [{"name": "math.find"}, {"name": "math.run"}],
        "catalog": {
            "catalog_version": "1",
            "catalog_digest": "sha256:" + "0" * 64,
            "operation_count": 2,
            "content_sha256": "sha256:" + "1" * 64,
        },
    }

    assert surface_snapshot_digest(surface).startswith("sha256:")


def test_checked_in_visibility_suites_reference_public_operations() -> None:
    public_ids = {tool.operation_id for tool in BUILTIN_TOOLS}
    config_dir = Path(__file__).parents[1] / "config"

    for name in (
        "codex-visibility-v2.json",
        "schema-bound-selection-v1.json",
        "typed-checker-handoff-v1.json",
    ):
        suite = load_suite(config_dir / name)
        expected_ids = {
            operation_id
            for case in suite.cases
            for operation_id in case.expected_operation_ids
        }
        assert expected_ids <= public_ids, name
