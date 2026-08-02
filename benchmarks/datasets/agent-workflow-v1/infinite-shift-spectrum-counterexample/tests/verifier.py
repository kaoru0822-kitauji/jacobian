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
        frozen_bytes = frozen.read_bytes()
        if workspace.read_bytes() != frozen_bytes:
            return {}
        value = json.loads(frozen_bytes)
    except (OSError, ValueError, UnicodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _right(index):
    return index + 1


def _left(index):
    return None if index == 0 else index - 1


def _compose(outer, inner, index):
    intermediate = inner(index)
    return None if intermediate is None else outer(intermediate)


def _expected_orientation(orientation):
    if orientation == "S_RIGHT_T_LEFT":
        return _right, _left, "ST", "TS"
    if orientation == "S_LEFT_T_RIGHT":
        return _left, _right, "TS", "ST"
    return None


def _valid_actions(actions, s_action, t_action, start, end):
    if not isinstance(actions, list) or len(actions) != end - start + 1:
        return False
    for action, index in zip(actions, range(start, end + 1), strict=True):
        if not isinstance(action, dict) or set(action) != {
            "basis_index",
            "s_output",
            "t_output",
            "st_output",
            "ts_output",
        }:
            return False
        expected = {
            "basis_index": index,
            "s_output": s_action(index),
            "t_output": t_action(index),
            "st_output": _compose(s_action, t_action, index),
            "ts_output": _compose(t_action, s_action, index),
        }
        if action != expected:
            return False
    return True


def _valid_result(result, frozen):
    if not isinstance(result, dict) or set(result) != {
        "orientation",
        "basis_window",
        "actions",
        "zero_eigenvalue_product",
        "identity_product",
        "zero_eigenvector_basis_index",
        "spectral_conclusion",
        "missing_assumption",
    }:
        return False
    orientation = _expected_orientation(result.get("orientation"))
    window = frozen.get("basis_window")
    if orientation is None or window != [0, 8] or result.get("basis_window") != window:
        return False
    s_action, t_action, zero_product, identity_product = orientation
    return bool(
        _valid_actions(result.get("actions"), s_action, t_action, *window)
        and result.get("zero_eigenvalue_product") == zero_product
        and result.get("identity_product") == identity_product
        and result.get("zero_eigenvector_basis_index") == 0
        and result.get("spectral_conclusion") == "EIGENVALUE_SETS_DIFFER"
        and result.get("missing_assumption") == "FINITE_DIMENSIONALITY"
    )


def _evidence_matches(evidence, result):
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
    return (
        all(
            term in text
            for term in (
                "finitely supported",
                "identity",
                "eigenvalue",
                "finite-dimensional",
            )
        )
        and result["zero_eigenvalue_product"].casefold() in text
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
    math_correct = bool(contract and _valid_result(submission.get("result"), frozen))
    evidence_valid = bool(
        contract
        and math_correct
        and _evidence_matches(submission.get("evidence"), submission["result"])
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
            "lean" in item.casefold() and "not" in item.casefold()
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
