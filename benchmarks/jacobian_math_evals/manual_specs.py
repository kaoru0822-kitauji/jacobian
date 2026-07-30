"""Manually authored, source-family evaluation instances.

These tasks cover sources whose upstream rows cannot be redistributed or
soundly extracted. They evaluate a real operation associated with the source
family; they never ask the agent to assess catalog metadata.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Callable, Iterable
from typing import cast

from .models import (
    OracleKind,
    SourceRecord,
    Split,
    TaskReadiness,
    TaskSpec,
)

TEMPLATES: dict[str, dict[str, object]] = {
    "exact-answer": {
        "instruction": (
            "Compute gcd(462, 1071). Write the base-10 integer to the `answer` "
            "field of `submission.json`, with evidence showing the Euclidean steps."
        ),
        "instance": {"operation": "gcd", "a": 462, "b": 1071},
        "answer": "21",
        "oracle_kind": OracleKind.DETERMINISTIC,
    },
    "counterexample": {
        "instruction": (
            "Give a compact JSON object with distinct nonzero integers `x` and `y` "
            "that refutes `x^2 = y^2 implies x = y`. Put that JSON object in the "
            "`answer` field and show both checks in evidence."
        ),
        "instance": {"claim": "for nonzero integers x,y, x^2 = y^2 implies x = y"},
        "answer": '{"x":1,"y":-1}',
        "oracle_kind": OracleKind.CERTIFICATE_CHECKER,
        "validator": "square-counterexample",
    },
    "formal-proof": {
        "instruction": (
            "Complete the propositional proof from premises `p` and `p -> q`. "
            "Write a compact JSON array of proof lines, ending in `q`, to the "
            "`answer` field. Each line must be either a premise or obtained by "
            "modus ponens."
        ),
        "instance": {
            "logic": "propositional",
            "premises": ["p", "p -> q"],
            "goal": "q",
            "rules": ["premise", "modus-ponens"],
        },
        "answer": '["p","p -> q","q"]',
        "oracle_kind": OracleKind.PROOF_REPLAY,
        "validator": "modus-ponens-proof",
    },
    "proof-repair": {
        "instruction": (
            "Repair the final proof line. Premises are `p` and `p -> q`; the "
            "invalid line is `r`. Return the compact JSON proof-line array in "
            "the `answer` field."
        ),
        "instance": {
            "premises": ["p", "p -> q"],
            "broken_lines": ["p", "p -> q", "r"],
            "goal": "q",
        },
        "answer": '["p","p -> q","q"]',
        "oracle_kind": OracleKind.PROOF_REPLAY,
        "validator": "modus-ponens-proof",
    },
    "premise-retrieval": {
        "instruction": (
            "From candidates `p`, `p -> q`, `q -> r`, retrieve the minimal "
            "premises sufficient to derive `q`. Return their compact JSON array "
            "in source order in the `answer` field."
        ),
        "instance": {
            "candidates": ["p", "p -> q", "q -> r"],
            "goal": "q",
        },
        "answer": '["p","p -> q"]',
        "oracle_kind": OracleKind.PROOF_REPLAY,
        "validator": "minimal-premises",
    },
    "statement-alignment": {
        "instruction": (
            "Formalize: “for every integer x, x plus zero equals x.” Return "
            "exactly `∀ x : Int, x + 0 = x` in the `answer` field."
        ),
        "instance": {
            "informal_statement": "for every integer x, x plus zero equals x",
            "target_language": "Lean-compatible Unicode proposition",
        },
        "answer": "∀ x : Int, x + 0 = x",
        "oracle_kind": OracleKind.DETERMINISTIC,
    },
    "research-artifact": {
        "instruction": (
            "Audit the bounded search claim. The search checked integers "
            "`0 <= n <= 100` and found no counterexample. Return exactly "
            "`NO_COUNTEREXAMPLE_IN_0_TO_100` in the `answer` field. Do not claim "
            "the universal conjecture is verified."
        ),
        "instance": {
            "checked_domain": {"variable": "n", "minimum": 0, "maximum": 100},
            "result": "no counterexample found",
            "completeness": "complete only for the stated finite interval",
        },
        "answer": "NO_COUNTEREXAMPLE_IN_0_TO_100",
        "oracle_kind": OracleKind.CERTIFICATE_CHECKER,
    },
    "formal-library": {
        "instruction": (
            "Inventory the top-level declarations in the frozen source "
            "`def double (n : Nat) := 2*n\\ntheorem double_zero : double 0 = 0 := "
            "by rfl`. Return the compact JSON name array in source order."
        ),
        "instance": {
            "language": "lean",
            "source": (
                "def double (n : Nat) := 2*n\n"
                "theorem double_zero : double 0 = 0 := by rfl"
            ),
        },
        "answer": '["double","double_zero"]',
        "oracle_kind": OracleKind.DETERMINISTIC,
    },
    "tool-application": {
        "instruction": (
            "Apply Horner evaluation to `2*x^3 - 3*x + 5` at `x = 4`. Return "
            "the base-10 integer result in the `answer` field and record the "
            "intermediate accumulator values as evidence."
        ),
        "instance": {
            "operation": "polynomial-evaluation",
            "coefficients_descending": [2, 0, -3, 5],
            "x": 4,
        },
        "answer": "121",
        "oracle_kind": OracleKind.DETERMINISTIC,
        "validator": "polynomial-evaluation",
    },
}

SPLIT_INDEX = {Split.TRAIN: 0, Split.DEV: 1, Split.TEST: 2}


def _variant(family: str, split: Split) -> dict[str, object]:
    template = copy.deepcopy(TEMPLATES[family])
    index = SPLIT_INDEX[split]
    if family == "exact-answer":
        pairs = ((462, 1071), (756, 1134), (899, 1241))
        a, b = pairs[index]
        template["instance"] = {"operation": "gcd", "a": a, "b": b}
        template["answer"] = str(math.gcd(a, b))
        template["instruction"] = (
            f"Compute gcd({a}, {b}). Write the base-10 integer to the `answer` "
            "field of `submission.json`, with evidence showing the Euclidean steps."
        )
    elif family == "counterexample":
        exponent = (2, 4, 6)[index]
        template["instance"] = {
            "claim": (
                f"for nonzero integers x,y, x^{exponent} = y^{exponent} implies x = y"
            ),
            "exponent": exponent,
        }
        template["answer"] = f'{{"x":{index + 1},"y":-{index + 1}}}'
        template["instruction"] = (
            "Give a compact JSON object with distinct nonzero integers `x` and "
            f"`y` that refutes `x^{exponent} = y^{exponent} implies x = y`. "
            "Put it in the `answer` field and show both checks in evidence."
        )
    elif family in {"formal-proof", "proof-repair", "premise-retrieval"}:
        atoms = (("p", "q", "r"), ("a", "b", "c"), ("u", "v", "w"))[index]
        first, second, third = atoms
        instance = cast(dict[str, object], template["instance"])
        replacements = {"p": first, "q": second, "r": third}
        for key in ("premises", "broken_lines", "candidates"):
            values = instance.get(key)
            if isinstance(values, list):
                instance[key] = [
                    replacements.get(value, value)
                    if isinstance(value, str) and " -> " not in value
                    else (
                        f"{replacements[value.split(' -> ')[0]]} -> "
                        f"{replacements[value.split(' -> ')[1]]}"
                        if isinstance(value, str) and " -> " in value
                        else value
                    )
                    for value in values
                ]
        if "goal" in instance:
            instance["goal"] = second
        if family in {"formal-proof", "proof-repair"}:
            template["answer"] = f'["{first}","{first} -> {second}","{second}"]'
        else:
            template["answer"] = f'["{first}","{first} -> {second}"]'
        template["instruction"] = (
            str(template["instruction"])
            .replace("`p`", f"`{first}`")
            .replace("`q`", f"`{second}`")
            .replace("`r`", f"`{third}`")
            .replace("p -> q", f"{first} -> {second}")
            .replace("q -> r", f"{second} -> {third}")
        )
    elif family == "statement-alignment":
        alignment_variants = (
            (
                "natural number",
                "Nat",
                "for every natural number x, x plus zero equals x",
            ),
            ("integer", "Int", "for every integer x, x plus zero equals x"),
            (
                "rational number",
                "Rat",
                "for every rational number x, x plus zero equals x",
            ),
        )
        noun, formal_type, informal = alignment_variants[index]
        template["instance"] = {
            "informal_statement": informal,
            "target_language": "Lean-compatible Unicode proposition",
        }
        template["answer"] = f"∀ x : {formal_type}, x + 0 = x"
        template["instruction"] = (
            f"Formalize: “for every {noun} x, x plus zero equals x.” Return "
            f"exactly `∀ x : {formal_type}, x + 0 = x` in the `answer` field."
        )
    elif family == "research-artifact":
        maximum = (100, 250, 1000)[index]
        template["instance"] = {
            "checked_domain": {
                "variable": "n",
                "minimum": 0,
                "maximum": maximum,
            },
            "result": "no counterexample found",
            "completeness": "complete only for the stated finite interval",
        }
        template["answer"] = f"NO_COUNTEREXAMPLE_IN_0_TO_{maximum}"
        template["instruction"] = (
            "Audit the bounded search claim. The search checked integers "
            f"`0 <= n <= {maximum}` and found no counterexample. Return exactly "
            f"`NO_COUNTEREXAMPLE_IN_0_TO_{maximum}`. Do not claim the universal "
            "conjecture is verified."
        )
    elif family == "formal-library":
        names = (
            ("double", "double_zero"),
            ("triple", "triple_zero"),
            ("quadruple", "quadruple_zero"),
        )[index]
        function, theorem = names
        multiplier = index + 2
        source = (
            f"def {function} (n : Nat) := {multiplier}*n\n"
            f"theorem {theorem} : {function} 0 = 0 := by rfl"
        )
        template["instance"] = {"language": "lean", "source": source}
        template["answer"] = f'["{function}","{theorem}"]'
        template["instruction"] = (
            "Inventory every top-level declaration in the frozen Lean source in "
            "`source.json`. Return the compact JSON name array in source order."
        )
    elif family == "tool-application":
        polynomial_variants = (
            ([2, 0, -3, 5], 4),
            ([1, -2, 4], 5),
            ([3, 1, -1, 2], -2),
        )
        coefficients, x = polynomial_variants[index]
        result = 0
        for coefficient in coefficients:
            result = result * x + coefficient
        template["instance"] = {
            "operation": "polynomial-evaluation",
            "coefficients_descending": coefficients,
            "x": x,
        }
        template["answer"] = str(result)
        template["instruction"] = (
            f"Apply Horner evaluation to coefficients {coefficients} at x = {x}. "
            "Return the base-10 integer result and record intermediate "
            "accumulators as evidence."
        )
    return template


def manual_family_specs(
    sources: Iterable[SourceRecord],
    *,
    family_of: Callable[[SourceRecord], str],
    partition_of: Callable[[SourceRecord], Split],
) -> tuple[TaskSpec, ...]:
    groups: dict[tuple[str, Split], list[SourceRecord]] = {}
    for source in sources:
        key = (family_of(source), partition_of(source))
        groups.setdefault(key, []).append(source)
    specs: list[TaskSpec] = []
    for (family, split), members in sorted(
        groups.items(), key=lambda item: (item[0][0], item[0][1].value)
    ):
        template = _variant(family, split)
        source_ids = tuple(sorted(source.source_id for source in members))
        expected: dict[str, object] = {
            "expected_answer": template["answer"],
            "maximum_assurance": "CHECKED",
            "required_scope_terms": [family, split.value],
            "requires_evidence": True,
        }
        if "accepted_answers" in template:
            expected["accepted_answers"] = list(
                cast(tuple[str, ...], template["accepted_answers"])
            )
        if "validator" in template:
            expected["validator"] = template["validator"]
            expected["validator_instance"] = template["instance"]
        specs.append(
            TaskSpec(
                task_id=f"manual-{family}-{split.value}",
                family=family,
                source_ids=source_ids,
                split=split,
                instruction=str(template["instruction"]),
                keywords=(
                    "mathematics",
                    family,
                    split.value,
                    "manually-authored",
                ),
                scored=True,
                instance={
                    **cast(dict[str, object], template["instance"]),
                    "seed": 0,
                    "coverage_source_ids": list(source_ids),
                },
                expected=expected,
                admissible_for_publish=all(
                    source.access_state.value == "public" for source in members
                ),
                readiness=TaskReadiness.READY,
                oracle_kind=cast(OracleKind, template["oracle_kind"]),
                manual=True,
                limitations=(
                    "family-level frozen instance; not an upstream row reproduction",
                ),
            )
        )
    return tuple(specs)
