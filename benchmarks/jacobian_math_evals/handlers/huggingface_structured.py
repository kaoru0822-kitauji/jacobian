"""Schema-gated public diagnostics from structured Hugging Face rows."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..models import OracleKind, SourceRecord, Split, TaskReadiness, TaskSpec
from .huggingface_rows import (
    HuggingFaceExactAnswerHandler,
    UnsupportedDatasetSchemaError,
)


@dataclass(frozen=True)
class RowRecipe:
    family: str
    input_fields: tuple[str, ...]
    target_fields: tuple[str, ...]
    instruction: str


RECIPES = (
    RowRecipe(
        "proof-repair",
        (
            "corrupted_code",
            "incorrect_formal",
            "incorrect_proof",
            "original",
            "state_before",
        ),
        (
            "repair_target",
            "correct_formal",
            "correct_proof",
            "replacement",
            "tactic",
        ),
        "Repair the supplied formal artifact. Return the repaired artifact",
    ),
    RowRecipe(
        "premise-retrieval",
        (
            "context",
            "target",
            "state",
            "tactic_context",
            "statement",
            "imports",
        ),
        ("pos_premise", "all_pos_premises", "premises"),
        "Retrieve the premises needed for the supplied proof state. Return them",
    ),
    RowRecipe(
        "statement-alignment",
        (
            "informal_statement",
            "natural_language_statement",
            "nl_statement",
            "nl_problem",
            "problem",
            "math_problem",
            "lean_statement",
            "chinese_statement",
        ),
        (
            "formal_statement",
            "lean4_formalization",
            "fl_theorem",
            "rocq_statement",
            "statement",
        ),
        "Formalize the supplied informal statement. Return the formal statement",
    ),
    RowRecipe(
        "formal-proof",
        (
            "formal_statement",
            "statement",
            "goal",
            "declaration",
            "lemma_definition",
            "state",
        ),
        (
            "formal_proof",
            "proof",
            "proof_body",
            "lean4_code",
            "fl_proof",
            "lemma_proof",
            "nextTactic",
        ),
        "Complete the supplied formal statement. Return the proof artifact",
    ),
    RowRecipe(
        "tool-application",
        ("input", "instruct", "prompt"),
        ("output",),
        "Apply the frozen upstream transformation. Return its output",
    ),
)


def _present(row: dict[str, Any], field: str) -> bool:
    value = row.get(field)
    return value is not None and value != "" and value != [] and value != {}


def choose_recipe(row: dict[str, Any]) -> tuple[RowRecipe, str, str] | None:
    for recipe in RECIPES:
        input_field = next(
            (field for field in recipe.input_fields if _present(row, field)),
            None,
        )
        target_field = next(
            (field for field in recipe.target_fields if _present(row, field)),
            None,
        )
        if input_field is not None and target_field is not None:
            return recipe, input_field, target_field
    return None


def _answer(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _message_pair(row: dict[str, Any]) -> tuple[object, object] | None:
    messages = row.get("messages")
    if not isinstance(messages, list):
        return None
    user: object | None = None
    assistant: object | None = None
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        if role == "user" and content not in (None, ""):
            user = content
        elif role == "assistant" and user is not None and content not in (None, ""):
            assistant = content
            break
    if user is None or assistant is None:
        return None
    return user, assistant


class HuggingFaceStructuredDiagnosticHandler(HuggingFaceExactAnswerHandler):
    """Extract one of several explicit input/target contracts."""

    def iter_specs(
        self,
        source: SourceRecord,
        snapshot: Path,
        *,
        full: bool,
    ) -> Iterator[TaskSpec]:
        value: Any = json.loads(snapshot.read_text(encoding="utf-8"))
        rows = value.get("rows") if isinstance(value, dict) else None
        if not isinstance(rows, list) or not rows:
            raise UnsupportedDatasetSchemaError("Viewer snapshot has no rows")
        extracted: list[tuple[int, RowRecipe, str, object, str, object]] = []
        for item in rows:
            if not isinstance(item, dict) or not isinstance(item.get("row"), dict):
                continue
            row = item["row"]
            row_index = item.get("row_idx")
            selected = choose_recipe(row)
            message_pair = _message_pair(row)
            if selected is None and message_pair is not None:
                row = {
                    **row,
                    "__user_message": message_pair[0],
                    "__assistant_message": message_pair[1],
                }
                selected = (
                    RowRecipe(
                        "formal-proof",
                        ("__user_message",),
                        ("__assistant_message",),
                        "Complete the supplied mathematical request. Return the "
                        "assistant artifact",
                    ),
                    "__user_message",
                    "__assistant_message",
                )
            if (
                selected is None
                or not isinstance(row_index, int)
                or isinstance(row_index, bool)
            ):
                continue
            recipe, input_field, target_field = selected
            extracted.append(
                (
                    row_index,
                    recipe,
                    input_field,
                    row[input_field],
                    target_field,
                    row[target_field],
                )
            )
        if not extracted:
            raise UnsupportedDatasetSchemaError(
                "no row matches a structured diagnostic recipe"
            )
        extracted.sort(key=lambda item: item[0])
        snapshot_sha = hashlib.sha256(snapshot.read_bytes()).hexdigest()
        for (
            row_index,
            recipe,
            input_field,
            input_value,
            target_field,
            target_value,
        ) in extracted if full else extracted[:1]:
            yield TaskSpec(
                task_id=(f"hf-{recipe.family}-{source.source_id[4:]}-{row_index:06d}"),
                family=recipe.family,
                source_ids=(source.source_id,),
                split=Split.PUBLIC,
                instruction=(
                    f"{recipe.instruction} in the `answer` field of "
                    "`submission.json`.\n\nFrozen input:\n"
                    f"{_answer(input_value)}\n\n"
                    "This is a public answer-visible reproduction diagnostic, "
                    "not a proof-validity or held-out score."
                ),
                keywords=(
                    "mathematics",
                    "huggingface",
                    recipe.family,
                    "public-diagnostic",
                ),
                scored=False,
                instance={
                    "source_id": source.source_id,
                    "source_revision": source.immutable_revision,
                    "snapshot_sha256": f"sha256:{snapshot_sha}",
                    "row_index": row_index,
                    "input_field": input_field,
                    "input": input_value,
                    "target_field": target_field,
                    "contamination": "PUBLIC_ANSWER_VISIBLE",
                },
                expected={
                    "answer_visible": True,
                    "expected_answer": _answer(target_value),
                    "maximum_assurance": "UNVERIFIED",
                    "source_revision": source.immutable_revision,
                    "snapshot_sha256": f"sha256:{snapshot_sha}",
                },
                admissible_for_publish=source.access_state.value == "public",
                readiness=TaskReadiness.PUBLIC_DIAGNOSTIC,
                oracle_kind=OracleKind.PUBLIC_ANSWER,
                limitations=(
                    "public answer-visible row; exclude from scored metrics",
                    "exact reproduction only; no proof-validity claim",
                ),
            )
