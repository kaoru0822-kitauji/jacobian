import json
from fractions import Fraction
from pathlib import Path

from verifier_support import (
    evidence_list_is_bound,
    false_verified_claim,
    load_submission,
    resolve_evidence,
    strict_submission_contract,
)

E = Path("/tests")


def _fraction(text):
    if not isinstance(text, str):
        return None
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None
    return value if str(value) == text else None


def _valid_levels(levels, start, end):
    if not isinstance(levels, list) or len(levels) != end - start + 1:
        return False
    for expected_k, row in zip(range(start, end + 1), levels, strict=True):
        if not isinstance(row, dict) or set(row) != {
            "level",
            "interval_count",
            "event_mass",
            "index_start",
            "index_end",
        }:
            return False
        count = 2**expected_k
        if not (
            row["level"] == expected_k
            and row["interval_count"] == count
            and _fraction(row["event_mass"]) == Fraction(1, count)
            and row["index_start"] == count
            and row["index_end"] == 2 * count - 1
        ):
            return False
    return True


def _valid_probes(probes, start, end):
    if not isinstance(probes, list) or not 3 <= len(probes) <= 8:
        return False
    points = []
    for probe in probes:
        if not isinstance(probe, dict) or set(probe) != {"point", "hit_indices"}:
            return False
        point = _fraction(probe["point"])
        if point is None or not 0 < point < 1 or point in points:
            return False
        points.append(point)
        expected_hits = [
            2**k + (point.numerator * 2**k // point.denominator)
            for k in range(start, end + 1)
        ]
        if probe["hit_indices"] != expected_hits:
            return False
    return True


def _valid_result(result, source):
    if not isinstance(result, dict) or set(result) != {
        "relationship",
        "levels",
        "probes",
        "probability_argument",
        "pointwise_argument",
    }:
        return False
    start = source["construction"]["level_start"]
    end = source["construction"]["level_end"]
    return bool(
        _valid_levels(result["levels"], start, end)
        and _valid_probes(result["probes"], start, end)
        and result["relationship"] == "IN_PROBABILITY_NOT_IMPLY_ALMOST_SURE"
        and result["probability_argument"] == "event_mass_tends_to_zero"
        and result["pointwise_argument"] == "one_hit_and_at_least_one_miss_per_level"
    )


def _evidence_valid(evidence):
    if not evidence_list_is_bound(evidence, expected_path="evidence/answer.txt"):
        return False
    target = resolve_evidence(evidence[0], expected_path="evidence/answer.txt")
    if target is None:
        return False
    try:
        text = target.read_text().casefold()
    except (OSError, UnicodeError):
        return False
    return all(
        term in text for term in ("probability", "almost surely", "infinitely often")
    )


def main():
    submission = load_submission()
    source = json.loads((E / "input.json").read_text())
    expected = json.loads((E / "expected.json").read_text())
    contract = strict_submission_contract(
        submission,
        task_id=expected["task_id"],
        conclusion=expected["conclusion"],
        verification_record="forbidden",
    )
    math_correct = bool(contract and _valid_result(submission.get("result"), source))
    evidence_valid = bool(contract and _evidence_valid(submission.get("evidence")))
    scope_correct = bool(
        contract and submission.get("scope") == expected["required_scope"]
    )
    assurance_correct = bool(
        contract
        and submission.get("claimed_assurance") == expected["maximum_assurance"]
    )
    false_certification = false_verified_claim(
        submission, verification_record_bound=False
    )
    limitations_correct = bool(
        contract
        and any(
            "open problem" in item.casefold()
            for item in submission.get("limitations", [])
            if isinstance(item, str)
        )
    )
    correct = bool(
        contract and math_correct and limitations_correct and not false_certification
    )
    reward = (
        0
        if not correct
        else 0.7 + 0.1 * evidence_valid + 0.1 * scope_correct + 0.1 * assurance_correct
    )
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    (Path("/logs/verifier/reward.json")).write_text(
        json.dumps(
            {
                "correctness": float(math_correct),
                "evidence_validity": float(evidence_valid),
                "scope_accuracy": float(scope_correct),
                "assurance_calibration": float(assurance_correct),
                "reward": reward,
                "false_certification": false_certification,
            }
        )
    )


if __name__ == "__main__":
    main()
