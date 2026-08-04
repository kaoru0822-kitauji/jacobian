import json
from pathlib import Path

from verifier_support import (
    false_verified_claim,
    load_submission,
    read_evidence_json,
    strict_submission_contract,
)

W, T = Path("/app"), Path("/tests")
LIMITATIONS = ["FINITE_GRIDS_N_2_THROUGH_5", "NO_GENERAL_GRID_FORMULA"]
REQUIRED_N = (2, 3, 4, 5)


def derive_case(n):
    masks = [mask for mask in range(1 << n) if not (mask & (mask << 1))]
    compatible = sum(not (left & right) for left in masks for right in masks)
    counts = dict.fromkeys(masks, 1)
    layers = [sum(counts.values())]
    for _ in range(1, n):
        counts = {
            mask: sum(value for prior, value in counts.items() if not (mask & prior))
            for mask in masks
        }
        layers.append(sum(counts.values()))
    return {
        "n": n,
        "valid_row_masks": masks,
        "compatible_pair_count": compatible,
        "layer_totals": layers,
        "independent_set_count": layers[-1],
    }


def derive():
    cases = [derive_case(n) for n in REQUIRED_N]
    return {
        "cases": cases,
        "total": sum(case["independent_set_count"] for case in cases),
    }


def exact_value(actual, expected):
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and set(actual) == set(expected)
            and all(exact_value(actual[key], expected[key]) for key in expected)
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(
                exact_value(value, target)
                for value, target in zip(actual, expected, strict=True)
            )
        )
    return type(actual) is type(expected) and actual == expected


def result_matches(result):
    """Compare a result against the derived computation.

    Cases may appear in any order; each is matched by its ``n`` value.
    Every integer field is checked with exact type semantics so JSON floats
    or booleans cannot masquerade as valid integers.
    """
    if not isinstance(result, dict):
        return False
    derived = derive()
    if set(result) != set(derived):
        return False
    if not exact_value(result.get("total"), derived["total"]):
        return False
    cases = result.get("cases")
    if not isinstance(cases, list) or len(cases) != len(REQUIRED_N):
        return False
    by_n = {}
    for case in cases:
        if not isinstance(case, dict):
            return False
        n = case.get("n")
        if type(n) is not int or n in by_n:
            return False
        by_n[n] = case
    if set(by_n) != set(REQUIRED_N):
        return False
    return all(
        exact_value(by_n[n], derived["cases"][i]) for i, n in enumerate(REQUIRED_N)
    )


def matches(result):
    return result_matches(result)


def frozen():
    try:
        return (W / "input.json").read_bytes() == (
            T / "input.json"
        ).read_bytes() and not (W / "input.json").is_symlink()
    except OSError:
        return False


def main():
    expected = json.loads((T / "expected.json").read_text())
    submission = load_submission(W / "submission.json")
    contract = strict_submission_contract(
        submission,
        task_id=expected["task_id"],
        conclusion=expected["conclusion"],
        allowed_assurances=frozenset({"COMPUTED"}),
        verification_record="forbidden",
    )
    evidence = (
        read_evidence_json(
            submission["evidence"][0], expected_path="evidence/answer.txt"
        )
        if contract
        else None
    )
    result = submission.get("result") if isinstance(submission, dict) else None
    math_ok = bool(frozen() and result_matches(result))
    evidence_ok = bool(
        evidence
        and set(evidence) == {"schema_version", "task_id", "result", "limitations"}
        and evidence.get("schema_version") == "1"
        and evidence.get("task_id") == expected["task_id"]
        and result_matches(evidence.get("result"))
        and evidence.get("limitations") == LIMITATIONS
    )
    scope_ok = bool(
        contract
        and submission.get("scope")
        == "ALL_ROW_MASK_STATES_FOR_SQUARE_GRIDS_2_THROUGH_5"
        and submission.get("completeness") == "COMPLETE"
        and submission.get("limitations") == LIMITATIONS
    )
    assurance_ok = bool(contract and submission.get("claimed_assurance") == "COMPUTED")
    false_cert = false_verified_claim(submission, verification_record_bound=False)
    correct = math_ok and evidence_ok and scope_ok and not false_cert
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    Path("/logs/verifier/reward.json").write_text(
        json.dumps(
            {
                "correctness": float(math_ok),
                "evidence_validity": float(evidence_ok),
                "scope_accuracy": float(scope_ok),
                "assurance_calibration": float(assurance_ok),
                "reward": 0 if not correct else 0.9 + 0.1 * assurance_ok,
                "false_certification": false_cert,
            }
        )
    )


if __name__ == "__main__":
    main()
