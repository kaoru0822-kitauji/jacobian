import json
from pathlib import Path

from verifier_support import (
    evidence_list_is_bound,
    false_verified_claim,
    load_submission,
    resolve_evidence,
    strict_submission_contract,
)

W = Path("/app")
E = Path("/tests")


def evidence_matches_result(evidence, result):
    if not evidence_list_is_bound(evidence, expected_path="evidence/answer.txt"):
        return False
    target = resolve_evidence(evidence[0], expected_path="evidence/answer.txt")
    if target is None:
        return False
    try:
        text = target.read_text()
        marker = next(
            line.removeprefix("RESULT_JSON:").strip()
            for line in text.splitlines()
            if line.startswith("RESULT_JSON:")
        )
        return json.loads(marker) == result and all(
            term in text for term in ("product", "difference", "quotient", "modulo")
        )
    except (OSError, StopIteration, UnicodeError, ValueError):
        return False


def _valid_witness(result, source):
    if not isinstance(result, dict) or set(result) != {
        "a",
        "b",
        "product_mod_7",
        "power_difference",
        "quotient_by_7_pow_7",
    }:
        return False
    if not all(type(result[key]) is int for key in result):
        return False

    a = result["a"]
    b = result["b"]
    minimum = source["search_scope"]["minimum"]
    maximum = source["search_scope"]["maximum"]
    if not (minimum <= a <= maximum and minimum <= b <= maximum):
        return False

    product = a * b * (a + b)
    difference = (a + b) ** 7 - a**7 - b**7
    divisor = 7**7
    return bool(
        product % 7 != 0
        and difference % divisor == 0
        and result["product_mod_7"] == product % 7
        and result["power_difference"] == difference
        and result["quotient_by_7_pow_7"] == difference // divisor
    )


def main():
    submission = load_submission()
    source = json.loads((W / "input.json").read_text())
    expected = json.loads((E / "expected.json").read_text())
    contract = strict_submission_contract(
        submission,
        task_id=expected["task_id"],
        conclusion=expected["conclusion"],
        verification_record="forbidden",
    )
    math_correct = bool(contract and _valid_witness(submission.get("result"), source))
    evidence_valid = bool(
        contract
        and evidence_matches_result(
            submission.get("evidence"), submission.get("result")
        )
    )
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
    correct = bool(contract and math_correct and not false_certification)
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
