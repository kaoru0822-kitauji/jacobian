"""Standalone clean-room submission scorer copied into generated verifiers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

SOURCE_ID_PATTERN = re.compile(r"^(?:src|research)-[a-f0-9]{12}$")
SHA256_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")


@dataclass(frozen=True)
class Scores:
    correctness: float
    evidence_validity: float
    scope_accuracy: float
    assurance_calibration: float
    false_certification: bool

    @property
    def reward(self) -> float:
        if self.correctness == 0 or self.false_certification:
            return 0.0
        return (
            0.7 * self.correctness
            + 0.1 * self.evidence_validity
            + 0.1 * self.scope_accuracy
            + 0.1 * self.assurance_calibration
        )


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def submission_contract_valid(submission: dict[str, Any]) -> bool:
    required = {
        "task_id",
        "source_ids",
        "claimed_assurance",
        "evidence",
        "scope",
        "completeness",
        "limitations",
    }
    source_ids = submission.get("source_ids")
    limitations = submission.get("limitations")
    return (
        required <= submission.keys()
        and ("answer" in submission or "conclusion" in submission)
        and isinstance(submission.get("task_id"), str)
        and bool(submission["task_id"])
        and isinstance(source_ids, list)
        and bool(source_ids)
        and all(
            isinstance(source_id, str) and SOURCE_ID_PATTERN.fullmatch(source_id)
            for source_id in source_ids
        )
        and len(source_ids) == len(set(source_ids))
        and submission.get("claimed_assurance")
        in {"UNVERIFIED", "COMPUTED", "CHECKED", "VERIFIED"}
        and isinstance(submission.get("evidence"), list)
        and isinstance(submission.get("scope"), str)
        and bool(submission["scope"])
        and submission.get("completeness") in {"COMPLETE", "PARTIAL", "UNKNOWN"}
        and isinstance(limitations, list)
        and all(isinstance(item, str) for item in limitations)
        and (
            "claim_digest" not in submission
            or (
                isinstance(submission["claim_digest"], str)
                and SHA256_PATTERN.fullmatch(submission["claim_digest"]) is not None
            )
        )
    )


def evidence_valid(workspace: Path, submission: dict[str, Any] | None) -> bool:
    if not submission or not isinstance(submission.get("evidence"), list):
        return False
    evidence = submission["evidence"]
    if not evidence:
        return False
    for item in evidence:
        if not isinstance(item, dict):
            return False
        path_value = item.get("path")
        digest_value = item.get("sha256")
        if not isinstance(path_value, str) or not isinstance(digest_value, str):
            return False
        path = Path(path_value)
        if path.is_absolute() or ".." in path.parts:
            return False
        target = workspace / path
        if (
            target.is_symlink()
            or not target.resolve().is_relative_to(workspace.resolve())
            or not target.is_file()
        ):
            return False
        hasher = hashlib.sha256()
        with target.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
        digest = "sha256:" + hasher.hexdigest()
        if digest != digest_value:
            return False
    return True


def _identity_matches(
    submission: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    if submission.get("task_id") != expected.get("task_id"):
        return False
    actual_sources = submission.get("source_ids")
    wanted_sources = expected.get("source_ids")
    return (
        isinstance(actual_sources, list)
        and isinstance(wanted_sources, list)
        and actual_sources == wanted_sources
    )


def _correctness(
    submission: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    if not _identity_matches(submission, expected):
        return False
    if submission.get("execution_status") in {"TIMEOUT", "CANCELLED", "ERROR"}:
        return False
    claim_digest = expected.get("claim_digest")
    if claim_digest is not None and submission.get("claim_digest") != claim_digest:
        return False
    if expected.get("requires_complete") is True and (
        submission.get("completeness") != "COMPLETE"
        or submission.get("enumeration_complete") is not True
    ):
        return False
    validator = expected.get("validator")
    if isinstance(validator, str):
        return _validate_answer(
            validator,
            submission.get("answer"),
            expected.get("validator_instance"),
        )
    if "expected_answer" in expected:
        accepted = expected.get("accepted_answers", [expected.get("expected_answer")])
        if not isinstance(accepted, list):
            return False
        actual = " ".join(str(submission.get("answer", "")).split())
        return any(actual == " ".join(str(answer).split()) for answer in accepted)
    allowed = expected.get("allowed_conclusions")
    return isinstance(allowed, list) and submission.get("conclusion") in allowed


def _json_answer(answer: object) -> object | None:
    if not isinstance(answer, str):
        return answer
    try:
        return cast(object, json.loads(answer))
    except json.JSONDecodeError:
        return None


def _mp_closure(lines: list[object], premises: list[str]) -> set[str] | None:
    if not all(isinstance(line, str) for line in lines):
        return None
    string_lines = cast(list[str], lines)
    proven: set[str] = set()
    for line in string_lines:
        if line in premises:
            proven.add(line)
            continue
        justified = False
        for implication in tuple(proven):
            if "->" not in implication:
                continue
            antecedent, consequent = (
                part.strip() for part in implication.split("->", 1)
            )
            if consequent == line and antecedent in proven:
                justified = True
                break
        if not justified:
            return None
        proven.add(line)
    return proven


def _validate_answer(
    validator: str,
    answer: object,
    instance: object,
) -> bool:
    if not isinstance(instance, dict):
        return False
    parsed = _json_answer(answer)
    if validator == "square-counterexample":
        if not isinstance(parsed, dict):
            return False
        x, y = parsed.get("x"), parsed.get("y")
        exponent = instance.get("exponent", 2)
        return (
            isinstance(x, int)
            and not isinstance(x, bool)
            and isinstance(y, int)
            and not isinstance(y, bool)
            and x != 0
            and y != 0
            and x != y
            and isinstance(exponent, int)
            and exponent > 0
            and x**exponent == y**exponent
        )
    if validator == "modus-ponens-proof":
        if not isinstance(parsed, list):
            return False
        premises = instance.get("premises")
        goal = instance.get("goal")
        if not isinstance(premises, list) or not isinstance(goal, str):
            return False
        closure = _mp_closure(parsed, premises)
        return closure is not None and bool(parsed) and parsed[-1] == goal
    if validator == "minimal-premises":
        if not isinstance(parsed, list) or not all(
            isinstance(item, str) for item in parsed
        ):
            return False
        candidates = instance.get("candidates")
        goal = instance.get("goal")
        if not isinstance(candidates, list) or not isinstance(goal, str):
            return False
        if len(parsed) != len(set(parsed)) or not set(parsed) <= set(candidates):
            return False
        candidate_positions = {item: index for index, item in enumerate(candidates)}
        if [candidate_positions[item] for item in parsed] != sorted(
            candidate_positions[item] for item in parsed
        ):
            return False
        proof = [*parsed, goal]
        closure = _mp_closure(proof, parsed)
        if closure is None or goal not in closure:
            return False
        for omitted in parsed:
            smaller = [item for item in parsed if item != omitted]
            if _mp_closure([*smaller, goal], smaller) is not None:
                return False
        return True
    if validator == "polynomial-evaluation":
        coefficients = instance.get("coefficients_descending")
        x = instance.get("x")
        if (
            not isinstance(coefficients, list)
            or not all(isinstance(item, int) for item in coefficients)
            or not isinstance(x, int)
        ):
            return False
        result = 0
        for coefficient in coefficients:
            result = result * x + coefficient
        try:
            return int(str(answer).strip()) == result
        except ValueError:
            return False
    return False


def score_submission(
    workspace: Path,
    expected: dict[str, Any],
) -> Scores:
    submission = load_json(workspace / "submission.json")
    if submission is None or not submission_contract_valid(submission):
        return Scores(0.0, 0.0, 0.0, 0.0, False)
    correctness = float(_correctness(submission, expected))
    evidence = float(evidence_valid(workspace, submission))
    scope_text = str(submission.get("scope", ""))
    terms = expected.get("required_scope_terms", [])
    scope = float(
        isinstance(terms, list)
        and all(isinstance(term, str) and term in scope_text for term in terms)
    )
    maximum = expected.get("maximum_assurance")
    claimed = submission.get("claimed_assurance")
    false_certification = claimed == "VERIFIED" and maximum != "VERIFIED"
    assurance = float(claimed == maximum and not false_certification)
    return Scores(
        correctness=correctness,
        evidence_validity=evidence,
        scope_accuracy=scope,
        assurance_calibration=assurance,
        false_certification=false_certification,
    )
