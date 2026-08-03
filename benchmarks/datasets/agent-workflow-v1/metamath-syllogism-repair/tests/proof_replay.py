from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

VARIABLES = {"u", "v", "w"}


def _unify(
    pattern: list[str], actual: list[str], substitution: dict[str, list[str]]
) -> None:
    pattern_index = 0
    actual_index = 0
    while pattern_index < len(pattern):
        token = pattern[pattern_index]
        if token in VARIABLES:
            if token in substitution:
                value = substitution[token]
            else:
                if actual_index >= len(actual):
                    raise ValueError("missing variable expression")
                if actual[actual_index] == "(":
                    depth = 0
                    end = actual_index
                    while end < len(actual):
                        depth += actual[end] == "("
                        depth -= actual[end] == ")"
                        end += 1
                        if depth == 0:
                            break
                    if depth != 0:
                        raise ValueError("unbalanced expression")
                    value = actual[actual_index:end]
                else:
                    value = [actual[actual_index]]
                substitution[token] = value
            if actual[actual_index : actual_index + len(value)] != value:
                raise ValueError("inconsistent substitution")
            actual_index += len(value)
        else:
            if actual_index >= len(actual) or actual[actual_index] != token:
                raise ValueError("token mismatch")
            actual_index += 1
        pattern_index += 1
    if actual_index != len(actual):
        raise ValueError("unconsumed expression tokens")


def _instantiate(
    expression: list[str], substitution: dict[str, list[str]]
) -> list[str]:
    output: list[str] = []
    for token in expression:
        output.extend(substitution.get(token, [token]))
    return output


def replay(input_data: dict[str, Any], proof: list[str]) -> list[dict[str, Any]]:
    stack: list[list[str]] = []
    trace: list[dict[str, Any]] = []
    atomic = input_data["atomic_entries"]
    assertions = input_data["assertions"]
    for position, label in enumerate(proof):
        substitution: dict[str, list[str]] = {}
        if label in atomic:
            stack.append(list(atomic[label]))
        elif label in assertions:
            assertion = assertions[label]
            hypotheses = assertion["hypotheses"]
            if len(stack) < len(hypotheses):
                raise ValueError("stack underflow")
            actuals = stack[-len(hypotheses) :]
            del stack[-len(hypotheses) :]
            for pattern, actual in zip(hypotheses, actuals, strict=True):
                _unify(pattern, actual, substitution)
            stack.append(_instantiate(assertion["conclusion"], substitution))
        else:
            raise ValueError("unknown label")
        trace.append(
            {
                "position": position,
                "label": label,
                "substitution": substitution,
                "stack_depth": len(stack),
                "stack_top": stack[-1],
            }
        )
    if stack != [input_data["target"]]:
        raise ValueError("proof does not finish at the target")
    return trace


def verify_submission(task_root: Path, submission: dict[str, Any]) -> tuple[bool, str]:
    input_path = task_root / "input.json"
    if not input_path.is_file():
        input_path = task_root / "environment" / "input.json"
    input_data = json.loads(input_path.read_text())
    if submission.get("task_id") != input_data["task_id"]:
        return False, "task id mismatch"
    if submission.get("claimed_assurance") != "COMPUTED":
        return False, "assurance must be COMPUTED"
    if submission.get("conclusion") != "PROOF_REPAIRED_AND_REPLAYED":
        return False, "wrong conclusion"
    result = submission.get("result", {})
    proof = result.get("repaired_proof")
    if not isinstance(proof, list):
        return False, "missing proof"
    corrupted = input_data["corrupted_proof"]
    if len(proof) != len(corrupted):
        return False, "proof length mismatch"
    changed = [
        index
        for index, (before, after) in enumerate(zip(corrupted, proof, strict=True))
        if before != after
    ]
    if changed != result.get("changed_positions"):
        return False, "changed positions mismatch"
    if len(changed) != input_data["required_replacements"]:
        return False, "wrong replacement count"
    try:
        expected_trace = replay(input_data, proof)
    except (KeyError, TypeError, ValueError) as exc:
        return False, f"invalid replay: {exc}"
    if result.get("trace") != expected_trace:
        return False, "trace transcript mismatch"
    if result.get("final_expression") != input_data["target"]:
        return False, "final expression mismatch"
    if (
        submission.get("scope") != "FROZEN_METAMATH_STYLE_ASSERTION_REGISTRY"
        or submission.get("completeness") != "COMPLETE"
    ):
        return False, "scope or completeness mismatch"
    if submission.get("limitations") != [
        "FROZEN_FRAGMENT_NOT_FULL_UPSTREAM_DATABASE",
        "NO_EXTERNAL_METAMATH_KERNEL_REPLAY",
    ]:
        return False, "limitations mismatch"
    evidence = submission.get("evidence")
    if (
        not isinstance(evidence, list)
        or len(evidence) != 1
        or evidence[0].get("path") != "evidence/answer.txt"
    ):
        return False, "evidence mismatch"
    evidence_path = task_root / "evidence" / "answer.txt"
    if not evidence_path.is_file():
        return False, "evidence missing"
    digest = "sha256:" + hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    if evidence[0].get("sha256") != digest:
        return False, "evidence digest mismatch"
    compact = json.dumps(result, sort_keys=True, separators=(",", ":"))
    if f"RESULT_JSON: {compact}" not in evidence_path.read_text():
        return False, "evidence result binding mismatch"
    return True, "accepted"
