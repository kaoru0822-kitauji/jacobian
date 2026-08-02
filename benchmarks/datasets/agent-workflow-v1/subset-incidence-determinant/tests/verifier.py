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
LIMITATION = "The verifier checks a complete finite incidence factorization and the general counting formula but does not replay the universal theorem in Lean."


def _source() -> dict[str, Any]:
    try:
        raw = (TESTS / "input.json").read_bytes()
        if (WORKSPACE / "input.json").read_bytes() != raw:
            return {}
        value = json.loads(raw)
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _factorization(order: list[int], weights: list[int]) -> bool:
    size = len(order)
    zeta = [[int(t & a == t) for t in order] for a in order]
    for i, a in enumerate(order):
        for j, b in enumerate(order):
            reconstructed = sum(
                zeta[i][k] * weights[k] * zeta[j][k] for k in range(size)
            )
            if reconstructed != int(bool(a & b)):
                return False
    return all(
        zeta[i][i] == 1 and all(zeta[i][j] == 0 for j in range(i + 1, size))
        for i in range(size)
    )


def _result(value: object, source: dict[str, Any]) -> bool:
    required = {
        "sample_n",
        "mask_order",
        "diagonal_weights",
        "trace",
        "general_even_count",
        "general_determinant",
    }
    if not isinstance(value, dict) or set(value) != required:
        return False
    provenance = source.get("source", {})
    n = source.get("sample_n")
    if (
        provenance.get("revision") != "dfb0a47a1c1ec3a10f2a9acfdf41a2043920f33c"
        or n != 5
        or value["sample_n"] != n
    ):
        return False
    order = value["mask_order"]
    weights = value["diagonal_weights"]
    expected_order = sorted(range(1, 2**n), key=lambda mask: (mask.bit_count(), mask))
    expected_weights = [1 if mask.bit_count() % 2 else -1 for mask in expected_order]
    if (
        order != expected_order
        or weights != expected_weights
        or not _factorization(order, weights)
    ):
        return False
    trace = value["trace"]
    if not isinstance(trace, list) or len(trace) != source.get("trace_max_n"):
        return False
    expected_trace = [
        {
            "n": k,
            "even_nonempty_count": 2 ** (k - 1) - 1,
            "determinant": 1 if k == 1 else -1,
        }
        for k in range(1, source["trace_max_n"] + 1)
    ]
    return bool(
        trace == expected_trace
        and value["general_even_count"] == "2^(n-1)-1"
        and value["general_determinant"] == "1_if_n_eq_1_else_minus_1"
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
        for term in ("inclusion-exclusion", "zeta", "even subsets", "computed")
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
