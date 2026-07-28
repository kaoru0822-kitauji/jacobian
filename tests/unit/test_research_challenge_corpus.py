from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).parents[2]
CORPUS_DIR = REPO_ROOT / "benchmarks" / "research_challenges"
SCHEMA_PATH = CORPUS_DIR / "public_postdoc.schema.json"
SUITE_PATH = CORPUS_DIR / "public_postdoc_v1.json"
PROMPT_PREFIX = (
    "Use Jacobian MCP, and do not use web search or external knowledge retrieval,"
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_public_postdoc_suite_conforms_to_its_schema() -> None:
    schema = _read_json(SCHEMA_PATH)
    suite = _read_json(SUITE_PATH)
    Draft202012Validator.check_schema(schema)

    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(suite),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )

    assert not errors, "\n".join(
        f"{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
        for error in errors
    )


def test_public_postdoc_suite_is_explicitly_answer_visible_and_unscored() -> None:
    suite = _read_json(SUITE_PATH)

    assert suite["purpose"] == "PUBLIC_ANSWER_VISIBLE_DIAGNOSTIC"
    assert suite["scored"] is False
    assert all(case["oracle"]["answer_visible"] for case in suite["cases"])
    assert all(
        case["contamination"] == "PUBLIC_ANSWER_VISIBLE" for case in suite["cases"]
    )


def test_public_postdoc_prompts_do_not_disclose_evaluator_sources() -> None:
    suite = _read_json(SUITE_PATH)

    for case in suite["cases"]:
        prompt = case["prompt"]
        assert prompt.startswith(PROMPT_PREFIX)
        assert "http://" not in prompt
        assert "https://" not in prompt
        assert all(source["url"] not in prompt for source in case["sources"])


def test_public_postdoc_case_ids_and_tier_mix_are_stable() -> None:
    suite = _read_json(SUITE_PATH)
    cases = suite["cases"]
    ids = [case["challenge_id"] for case in cases]

    assert ids == [f"jcb-postdoc-{number:03d}" for number in range(1, 13)]
    assert len({case["title"] for case in cases}) == len(cases)
    assert Counter(case["tier"] for case in cases) == {
        "CLOSURE_CANDIDATE": 3,
        "COMPOSITIONAL_STRETCH": 4,
        "CAPABILITY_GAP_PROBE": 5,
    }
