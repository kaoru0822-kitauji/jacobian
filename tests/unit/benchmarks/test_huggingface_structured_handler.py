from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from benchmarks.jacobian_math_evals.catalog import load_sources
from benchmarks.jacobian_math_evals.handlers.huggingface_structured import (
    HuggingFaceStructuredDiagnosticHandler,
    choose_recipe,
)
from benchmarks.jacobian_math_evals.handlers.registry import HANDLERS
from benchmarks.jacobian_math_evals.models import (
    OracleKind,
    TaskReadiness,
)


def test_recipes_route_distinct_task_families() -> None:
    assert (
        choose_recipe({"corrupted_code": "bad", "repair_target": "good"})[0].family
        == "proof-repair"
    )
    assert (
        choose_recipe({"context": "ctx", "pos_premise": "lemma"})[0].family
        == "premise-retrieval"
    )
    assert (
        choose_recipe({"informal_statement": "words", "formal_statement": "theorem t"})[
            0
        ].family
        == "statement-alignment"
    )
    assert (
        choose_recipe({"formal_statement": "theorem t", "formal_proof": "by exact h"})[
            0
        ].family
        == "formal-proof"
    )


def test_structured_handler_emits_public_exact_reproduction(
    tmp_path: Path,
) -> None:
    source = replace(
        next(source for source in load_sources() if source.host == "huggingface.co"),
        source_id="src-222222222222",
        immutable_revision="2" * 40,
    )
    snapshot = tmp_path / "rows.json"
    snapshot.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "row_idx": 7,
                        "row": {
                            "corrupted_code": "theorem t := by nope",
                            "repair_target": "theorem t := by trivial",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    [spec] = tuple(
        HuggingFaceStructuredDiagnosticHandler(source.source_id).iter_specs(
            source, snapshot, full=False
        )
    )
    assert spec.family == "proof-repair"
    assert spec.expected["expected_answer"] == "theorem t := by trivial"
    assert spec.readiness == TaskReadiness.PUBLIC_DIAGNOSTIC
    assert spec.oracle_kind == OracleKind.PUBLIC_ANSWER
    assert spec.scored is False


def test_probe_registers_34_non_overlapping_structured_sources() -> None:
    handlers = [
        handler
        for handler in HANDLERS
        if type(handler) is HuggingFaceStructuredDiagnosticHandler
    ]
    assert len(handlers) == 34
    assert len({handler.source_id for handler in handlers}) == 34
