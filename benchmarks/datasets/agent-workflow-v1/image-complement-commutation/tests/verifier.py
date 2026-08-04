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
        if left != right and failure is None:
            failure = (sorted(subset), left, right)
    return {
        "id": case["id"],
        "classification": classification,
        "commutes": failure is None,
        "checked_subsets": 1 << n,
        "first_failure": None if failure is None else failure[0],
        "left_image": None if failure is None else failure[1],
        "right_complement": None if failure is None else failure[2],
    }


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _row_type_ok(row):
    if set(row) != {
        "id",
        "classification",
        "commutes",
        "checked_subsets",
        "first_failure",
        "left_image",
        "right_complement",
    }:
        return False
    if not isinstance(row["id"], str):
        return False
    if not isinstance(row["classification"], str):
        return False
    if type(row["commutes"]) is not bool:
        return False
    if not _is_int(row["checked_subsets"]):
        return False
    for key in ("first_failure", "left_image", "right_complement"):
        value = row[key]
        if value is not None:
            if not isinstance(value, list):
                return False
            if any(not _is_int(item) for item in value):
                return False
    return True


def _normalize_row(row):
    out = dict(row)
    for key in ("first_failure", "left_image", "right_complement"):
        value = out[key]
        out[key] = None if value is None else sorted(value)
    return out


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
    if any(not _row_type_ok(row) for row in rows):
        return False
    frozen_cases = json.loads((T / "input.json").read_text())["cases"]
    expected = {
        case["id"]: _normalize_row(expected_case(case)) for case in frozen_cases
    }
    by_id = {}
    for row in rows:
        if row["id"] in by_id:
            return False
        by_id[row["id"]] = _normalize_row(row)
    if set(by_id) != set(expected):
        return False
    return all(by_id[cid] == expected[cid] for cid in expected)


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
    math_ok = bool(frozen() and valid(s.get("result")))
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
    assurance_ok = bool(s is not None and s.get("claimed_assurance") == "COMPUTED")
    false_cert = false_verified_claim(s, verification_record_bound=False)
    correct = bool(contract and math_ok and evidence_ok and scope_ok and not false_cert)
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
