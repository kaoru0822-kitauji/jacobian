import json
from pathlib import Path
from typing import Any

from verifier_support import (
    evidence_list_is_bound,
    false_verified_claim,
    load_submission,
    resolve_evidence,
    strict_submission_contract,
)

WORKSPACE = Path("/app")
TESTS = Path("/tests")
LIMITATION = "The checker validates the squarefree-class reduction and complete modulo-8 obstruction, but does not enumerate the unknown source set or replay a proof assistant."


def _source() -> dict[str, Any]:
    try:
        raw = (TESTS / "input.json").read_bytes()
        if (WORKSPACE / "input.json").read_bytes() != raw:
            return {}
        value = json.loads(raw)
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _result(value: object, source: dict[str, Any]) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "kernel_relation",
        "pair_count",
        "contradiction_assumption",
        "square_residues_mod_8",
        "three_square_sums_mod_8",
        "target_residue",
        "obstruction",
        "transversal",
    }:
        return False
    squares = sorted({(n * n) % 8 for n in range(8)})
    sums = sorted({(a + b + c) % 8 for a in squares for b in squares for c in squares})
    provenance = source.get("source", {})
    return bool(
        provenance.get("revision") == "73661e62811cf2940a0d3f82788a4f4332204c2f"
        and provenance.get("row") == 4
        and source.get("ordered_square_product_pairs") == 2023
        and value["kernel_relation"] == "xy_square_iff_squarefree_kernel_equal"
        and value["pair_count"] == "sum_of_class_sizes_squared"
        and value["contradiction_assumption"] == "at_most_three_nonempty_classes"
        and value["square_residues_mod_8"] == squares == [0, 1, 4]
        and value["three_square_sums_mod_8"] == sums
        and value["target_residue"] == 2023 % 8 == 7
        and 7 not in sums
        and value["obstruction"] == "2023_NOT_SUM_OF_AT_MOST_THREE_SQUARES"
        and value["transversal"]
        == "choose_one_element_from_each_of_four_distinct_kernel_classes"
    )


def _evidence(value: object) -> bool:
    if not evidence_list_is_bound(value):
        return False
    assert isinstance(value, list)
    path = resolve_evidence(value[0], expected_path="evidence/answer.txt")
    if path is None:
        return False
    try:
        text = path.read_text().lower()
    except (OSError, UnicodeError):
        return False
    return all(
        term in text
        for term in ("squarefree", "class", "modulo 8", "transversal", "computed")
    )


def main() -> None:
    submission = load_submission()
    data = submission if isinstance(submission, dict) else {}
    expected = json.loads((TESTS / "expected.json").read_text())
    contract = strict_submission_contract(
        submission,
        task_id=expected["task_id"],
        conclusion=expected["conclusion"],
        verification_record="forbidden",
    )
    correct = bool(contract and _result(data.get("result"), _source()))
    evidence = bool(correct and _evidence(data.get("evidence")))
    scope = bool(contract and data.get("scope") == expected["required_scope"])
    assurance = bool(
        contract and data.get("claimed_assurance") == expected["maximum_assurance"]
    )
    limitations = bool(contract and data.get("limitations") == [LIMITATION])
    false_verified = false_verified_claim(submission, verification_record_bound=False)
    passed = bool(
        correct
        and evidence
        and scope
        and assurance
        and limitations
        and not false_verified
    )
    logs = Path("/logs/verifier")
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "reward.json").write_text(
        json.dumps(
            {
                "correctness": float(correct),
                "evidence_validity": float(evidence),
                "scope_accuracy": float(scope),
                "assurance_calibration": float(assurance),
                "reward": float(passed),
                "false_certification": false_verified,
            },
            sort_keys=True,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
