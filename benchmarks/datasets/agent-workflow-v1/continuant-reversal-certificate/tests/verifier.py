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
MAX_EVIDENCE_BYTES = 1_048_576


def _load_frozen_input():
    try:
        workspace = W / "input.json"
        frozen = E / "input.json"
        if workspace.is_symlink() or frozen.is_symlink():
            return {}
        raw = frozen.read_bytes()
        if workspace.read_bytes() != raw:
            return {}
        value = json.loads(raw)
    except (OSError, UnicodeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _supports(n):
    values = [()]
    for edge in range(1, n):
        values += [
            (*support, edge)
            for support in values
            if not support or support[-1] < edge - 1
        ]
    return sorted(values, key=lambda item: (len(item), item))


def _parse_supports(value):
    if not isinstance(value, list):
        return None
    parsed = []
    for support in value:
        if not isinstance(support, list) or any(
            type(item) is not int for item in support
        ):
            return None
        if support != sorted(set(support)):
            return None
        parsed.append(tuple(support))
    return parsed


def _pairs_are_valid(value, supports, n):
    if not isinstance(value, list) or len(value) != len(supports):
        return False
    expected = [
        {"forward": list(support), "reflected": sorted(n - item for item in support)}
        for support in supports
    ]
    return value == expected


def _result_is_valid(result, frozen):
    if not isinstance(result, dict) or set(result) != {
        "board_length",
        "forward_monomials",
        "reverse_monomials",
        "reflection_pairs",
        "recurrence_contract",
        "conclusion",
    }:
        return False
    n = frozen.get("board_length")
    if n != 10 or result["board_length"] != n:
        return False
    supports = _supports(n)
    forward = _parse_supports(result["forward_monomials"])
    reverse = _parse_supports(result["reverse_monomials"])
    return bool(
        forward == supports
        and reverse == supports
        and _pairs_are_valid(result["reflection_pairs"], supports, n)
        and result["recurrence_contract"]
        == {
            "initial_values": [1, 1],
            "forward_coefficient": "a_k",
            "reverse_coefficient": "a_(n-k)",
            "reflection_rule": "i_maps_to_n_minus_i",
        }
        and result["conclusion"] == "FINAL_POLYNOMIALS_EQUAL"
    )


def _evidence_matches(evidence):
    if not evidence_list_is_bound(evidence, expected_path="evidence/answer.txt"):
        return False
    target = resolve_evidence(evidence[0], expected_path="evidence/answer.txt")
    if target is None:
        return False
    try:
        if target.stat().st_size > MAX_EVIDENCE_BYTES:
            return False
        text = target.read_text().casefold()
    except (OSError, UnicodeError):
        return False
    return all(
        term in text for term in ("tiling", "recurrence", "reflection", "monomial")
    )


def main():
    submission = load_submission()
    frozen = _load_frozen_input()
    expected = json.loads((E / "expected.json").read_text())
    contract = strict_submission_contract(
        submission,
        task_id=expected["task_id"],
        conclusion=expected["conclusion"],
        verification_record="forbidden",
    )
    math_correct = bool(contract and _result_is_valid(submission.get("result"), frozen))
    evidence_valid = bool(
        contract and math_correct and _evidence_matches(submission.get("evidence"))
    )
    scope_correct = bool(
        contract and submission.get("scope") == expected["required_scope"]
    )
    assurance_correct = bool(
        contract
        and submission.get("claimed_assurance") == expected["maximum_assurance"]
    )
    limitation_correct = bool(
        contract
        and any(
            "all real" in item.casefold() and "not" in item.casefold()
            for item in submission.get("limitations", [])
        )
    )
    false_certification = false_verified_claim(
        submission, verification_record_bound=False
    )
    correct = bool(
        contract and math_correct and limitation_correct and not false_certification
    )
    reward = (
        0
        if not correct
        else 0.7 + 0.1 * evidence_valid + 0.1 * scope_correct + 0.1 * assurance_correct
    )
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    Path("/logs/verifier/reward.json").write_text(
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
