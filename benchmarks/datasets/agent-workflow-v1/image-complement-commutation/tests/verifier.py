import json
from pathlib import Path

from verifier_support import (
    false_verified_claim,
    load_submission,
    read_evidence_json,
    strict_submission_contract,
)

W, T = Path("/app"), Path("/tests")
LIMITATIONS = ["FINITE_FROZEN_MAPPINGS", "NO_GENERAL_THEOREM_PROOF"]


def frozen():
    try:
        return (W / "input.json").read_bytes() == (
            T / "input.json"
        ).read_bytes() and not (W / "input.json").is_symlink()
    except OSError:
        return False


def expected_case(case):
    n, m, mapping = case["domain_size"], case["codomain_size"], case["mapping"]
    injective = len(set(mapping)) == n
    surjective = set(mapping) == set(range(m))
    classification = (
        "BIJECTIVE"
        if injective and surjective
        else "INJECTIVE_NOT_SURJECTIVE"
        if injective
        else "SURJECTIVE_NOT_INJECTIVE"
    )
    failure = None
    for mask in range(1 << n):
        subset = {i for i in range(n) if mask >> i & 1}
        left = sorted({mapping[i] for i in range(n) if i not in subset})
        right = sorted(set(range(m)) - {mapping[i] for i in subset})
        if left != right:
            failure = (sorted(subset), left, right)
            break
    return {
        "id": case["id"],
        "classification": classification,
        "commutes": failure is None,
        "checked_subsets": 1 << n,
        "first_failure": None if failure is None else failure[0],
        "left_image": None if failure is None else failure[1],
        "right_complement": None if failure is None else failure[2],
    }


def valid(result):
    if (
        not isinstance(result, dict)
        or set(result) != {"cases"}
        or not isinstance(result["cases"], list)
        or len(result["cases"]) != 3
    ):
        return False
    rows = result["cases"]
    if any(not isinstance(row, dict) for row in rows):
        return False
    frozen_cases = json.loads((T / "input.json").read_text())["cases"]
    return rows == [expected_case(case) for case in frozen_cases]


def main():
    expected = json.loads((T / "expected.json").read_text())
    s = load_submission(W / "submission.json")
    contract = strict_submission_contract(
        s,
        task_id=expected["task_id"],
        conclusion=expected["conclusion"],
        allowed_assurances=frozenset({"COMPUTED"}),
        verification_record="forbidden",
    )
    ev = (
        read_evidence_json(
            s["evidence"][0], expected_path="evidence/image-complement-certificate.json"
        )
        if contract
        else None
    )
    math_ok = bool(contract and frozen() and valid(s.get("result")))
    evidence_ok = bool(
        ev
        and set(ev) == {"schema_version", "task_id", "result", "limitations"}
        and ev.get("schema_version") == "1"
        and ev.get("task_id") == expected["task_id"]
        and ev.get("result") == s.get("result")
        and ev.get("limitations") == LIMITATIONS
    )
    scope_ok = bool(
        contract
        and s.get("scope") == "ALL_SUBSETS_OF_ALL_THREE_FROZEN_MAPPINGS"
        and s.get("completeness") == "COMPLETE"
        and s.get("limitations") == LIMITATIONS
    )
    assurance_ok = bool(contract and s.get("claimed_assurance") == "COMPUTED")
    false_cert = false_verified_claim(s, verification_record_bound=False)
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
