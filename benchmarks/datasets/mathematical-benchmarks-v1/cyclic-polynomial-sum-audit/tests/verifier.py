import json
import math
from fractions import Fraction
from pathlib import Path

from verifier_support import (
    false_verified_claim,
    load_submission,
    normalize_reward_file,
    read_evidence_json,
    strict_submission_contract,
)

APP = Path("/app")
TESTS = Path("/tests")
MAX_EVIDENCE_BYTES = 64 * 1024


def _json_equal(left: object, right: object) -> bool:
    """Compare JSON recursively without Python's bool/int coercion."""

    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if type(left) is int or type(right) is int:
        return type(left) is type(right) and left == right
    if isinstance(left, dict) or isinstance(right, dict):
        return (
            isinstance(left, dict)
            and isinstance(right, dict)
            and left.keys() == right.keys()
            and all(_json_equal(left[key], right[key]) for key in left)
        )
    if isinstance(left, list) or isinstance(right, list):
        return (
            isinstance(left, list)
            and isinstance(right, list)
            and len(left) == len(right)
            and all(_json_equal(a, b) for a, b in zip(left, right, strict=True))
        )
    return type(left) is type(right) and left == right


def _fraction(value: object) -> Fraction | None:
    if not isinstance(value, str):
        return None
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None
    return result if str(result) == value else None


def _poly_value(coefficients: list[int], value: Fraction) -> Fraction:
    result = Fraction()
    for coefficient in coefficients:
        result = result * value + coefficient
    return result


def _evidence_is_valid(evidence: object, result: object, limitations: object) -> bool:
    if not isinstance(evidence, list) or len(evidence) != 1:
        return False
    payload = read_evidence_json(
        evidence[0],
        expected_path="evidence/cyclic-elimination-certificate.json",
        max_bytes=MAX_EVIDENCE_BYTES,
    )
    return bool(
        payload
        and set(payload) == {"schema_version", "task_id", "result", "limitations"}
        and payload.get("schema_version") == "1"
        and payload.get("task_id") == "jacobian/cyclic-polynomial-sum-audit"
        and _json_equal(payload.get("result"), result)
        and _json_equal(payload.get("limitations"), limitations)
    )


def _branch_is_valid(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "sum",
        "pair_sum",
        "product",
        "product_consequence_lhs",
        "product_consequence_rhs",
        "residual",
    }:
        return False
    parsed = {key: _fraction(item) for key, item in value.items()}
    if any(item is None for item in parsed.values()):
        return False
    s = Fraction(3, 2)
    pair_sum = (s * s - (s + 18)) / 2
    product = s * pair_sum - 1
    lhs = (
        product * product
        - 6 * (pair_sum * pair_sum - 2 * product * s)
        + 36 * (s * s - 2 * pair_sum)
        - 216
    )
    rhs = product
    expected = {
        "sum": s,
        "pair_sum": pair_sum,
        "product": product,
        "product_consequence_lhs": lhs,
        "product_consequence_rhs": rhs,
        "residual": lhs - rhs,
    }
    return parsed == expected and lhs != rhs


def _roots_are_valid(value: object) -> bool:
    expected = [
        {
            "rational": "-1/2",
            "radical_coefficient": "-1/2",
            "radicand": 17,
        },
        {
            "rational": "-1/2",
            "radical_coefficient": "1/2",
            "radicand": 17,
        },
    ]
    return value == expected


def _result_is_valid(result: object, source: dict[str, object]) -> bool:
    if not isinstance(result, dict) or set(result) != {
        "necessary_polynomial",
        "proposed_evaluations",
        "proposed_classifications",
        "remaining_real_roots",
        "excluded_branch",
    }:
        return False
    coefficients = result["necessary_polynomial"]
    if coefficients != [2, -1, -11, 12]:
        return False
    # Primitive and square-free are checked explicitly, rather than trusted from labels.
    if math.gcd(*[abs(value) for value in coefficients]) != 1:
        return False
    proposed = source.get("adversarial_claimed_sums")
    if not isinstance(proposed, list):
        return False
    parsed = [_fraction(item) for item in proposed]
    if any(item is None for item in parsed):
        return False
    evaluations = [
        _poly_value(coefficients, item) for item in parsed if item is not None
    ]
    if result["proposed_evaluations"] != [str(item) for item in evaluations]:
        return False
    expected_classes = [
        "PASSES_NECESSARY_CONDITION" if item == 0 else "FAILS_NECESSARY_CONDITION"
        for item in evaluations
    ]
    return bool(
        result["proposed_classifications"] == expected_classes
        and _roots_are_valid(result["remaining_real_roots"])
        and _branch_is_valid(result["excluded_branch"])
    )


def main() -> None:
    submission = load_submission()
    source = json.loads((TESTS / "input.json").read_text())
    expected = json.loads((TESTS / "expected.json").read_text())
    result = submission.get("result") if isinstance(submission, dict) else None
    structure = strict_submission_contract(
        submission,
        task_id=expected["task_id"],
        conclusion=expected["conclusion"],
        allowed_assurances=frozenset({"UNVERIFIED", "COMPUTED", "CHECKED", "VERIFIED"}),
        verification_record="optional",
    )
    contract = strict_submission_contract(
        submission,
        task_id=expected["task_id"],
        conclusion=expected["conclusion"],
        allowed_assurances=frozenset({"UNVERIFIED", "COMPUTED"}),
        verification_record="forbidden",
    )
    mathematical = bool(structure and _result_is_valid(result, source))
    evidence = bool(
        structure
        and _evidence_is_valid(
            submission.get("evidence"), result, submission.get("limitations")
        )
    )
    scope = bool(structure and submission.get("scope") == expected["required_scope"])
    assurance = bool(
        structure
        and submission.get("claimed_assurance") == expected["maximum_assurance"]
    )
    false = false_verified_claim(submission, verification_record_bound=False)
    correct = bool(contract and mathematical and not false)
    reward = 0.0 if not correct or not evidence else 0.8 + 0.1 * scope + 0.1 * assurance
    logs = Path("/logs/verifier")
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "reward.json").write_text(
        json.dumps(
            {
                "correctness": float(mathematical),
                "evidence_validity": float(evidence),
                "scope_accuracy": float(scope),
                "assurance_calibration": float(assurance),
                "reward": reward,
                "false_certification": false,
            }
        )
    )
    normalize_reward_file(logs / "reward.json")


if __name__ == "__main__":
    main()
