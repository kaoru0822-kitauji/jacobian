from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

from verifier_support import (
    load_submission,
    normalize_reward_file,
)

WORKSPACE = Path("/app")
TESTS = Path("/tests")


def _fraction(value: object) -> Fraction | None:
    if not isinstance(value, dict) or set(value) != {"numerator", "denominator"}:
        return None
    numerator = value["numerator"]
    denominator = value["denominator"]
    if type(numerator) is not int or type(denominator) is not int or denominator < 1:
        return None
    return Fraction(numerator, denominator)


def _polynomial(value: object) -> tuple[int, ...] | None:
    if (
        not isinstance(value, list)
        or not 1 <= len(value) <= 4
        or not all(type(coefficient) is int for coefficient in value)
        or value[-1] == 0
    ):
        return None
    return tuple(value)


def _rational_function(
    value: object,
) -> tuple[tuple[int, ...], tuple[int, ...]] | None:
    if not isinstance(value, dict) or set(value) != {
        "numerator_coefficients",
        "denominator_coefficients",
    }:
        return None
    numerator = _polynomial(value["numerator_coefficients"])
    denominator = _polynomial(value["denominator_coefficients"])
    return (numerator, denominator) if numerator is not None and denominator else None


def _source_is_bound() -> bool:
    try:
        hidden = (TESTS / "input.json").read_bytes()
        if (WORKSPACE / "input.json").read_bytes() != hidden:
            return False
        source = json.loads(hidden)
    except (OSError, ValueError):
        return False
    return bool(
        source.get("source", {}).get("revision")
        == "339937d75342072a31903739b1bbbe72e1b40c21"
        and source.get("source", {}).get("rows") == [1066, 1069]
    )


def _divergent(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "term",
        "ratio",
        "ratio_error",
        "blocks",
    }:
        return False
    if tuple(
        _rational_function(value[field]) for field in ("term", "ratio", "ratio_error")
    ) != (
        ((1,), (0, 1)),
        ((0, 1), (1, 1)),
        ((1,), (1, 1)),
    ):
        return False
    blocks = value["blocks"]
    if not isinstance(blocks, list) or len(blocks) != 9:
        return False
    for block, level in zip(blocks, range(2, 11), strict=True):
        if not isinstance(block, dict) or set(block) != {
            "level",
            "start",
            "end",
            "count",
            "term_lower_bound",
            "block_lower_bound",
        }:
            return False
        start = 2**level
        count = 2**level
        lower = Fraction(1, 2 ** (level + 1))
        term_lower = _fraction(block["term_lower_bound"])
        block_lower = _fraction(block["block_lower_bound"])
        if term_lower is None or block_lower is None:
            return False
        if (
            block["level"] != level
            or block["start"] != start
            or block["end"] != 2 * start - 1
            or block["count"] != count
            or term_lower != lower
            or block_lower != Fraction(1, 2)
        ):
            return False
        if count * lower != Fraction(1, 2):
            return False
    return True


def _convergent_formulas_ok(value: dict) -> bool:
    telescoping = value["telescoping_identity"]
    if not isinstance(telescoping, list) or len(telescoping) != 2:
        return False
    return (
        _rational_function(value["term"]),
        tuple(_rational_function(term) for term in telescoping),
        _rational_function(value["ratio"]),
        _rational_function(value["ratio_error"]),
    ) == (
        ((1,), (0, 1, 1)),
        (((1,), (0, 1)), ((-1,), (1, 1))),
        ((0, 1), (2, 1)),
        ((2,), (2, 1)),
    )


def _convergent(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "term",
        "telescoping_identity",
        "ratio",
        "ratio_error",
        "checkpoints",
    }:
        return False
    if not _convergent_formulas_ok(value):
        return False
    checkpoints = value["checkpoints"]
    if not isinstance(checkpoints, list) or not 4 <= len(checkpoints) <= 12:
        return False
    seen: set[int] = set()
    for item in checkpoints:
        if not isinstance(item, dict) or set(item) != {"N", "partial_sum", "tail"}:
            return False
        n = item["N"]
        if type(n) is not int or n < 1 or n in seen:
            return False
        seen.add(n)
        partial = _fraction(item["partial_sum"])
        tail = _fraction(item["tail"])
        if partial is None or tail is None:
            return False
        if partial != Fraction(n, n + 1) or tail != Fraction(1, n + 1):
            return False
        if partial + tail != 1:
            return False
    return True


def _result(value: object) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == {"ratio_limit", "divergent_witness", "convergent_witness"}
        and value["ratio_limit"] == "1"
        and _divergent(value["divergent_witness"])
        and _convergent(value["convergent_witness"])
    )


def _evaluate(submission: object) -> dict[str, float | bool]:
    data = submission if isinstance(submission, dict) else {}
    input_binding = _source_is_bound()
    math_ok = bool(input_binding and _result(data.get("result")))
    reward = float(input_binding and submission is not None and math_ok)
    return {
        "correctness": float(math_ok),
        "input_binding": float(input_binding),
        "reward": reward,
    }


def main() -> None:
    result = _evaluate(load_submission())
    destination = Path("/logs/verifier/reward.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, sort_keys=True) + "\n")
    normalize_reward_file(destination)


if __name__ == "__main__":
    main()
