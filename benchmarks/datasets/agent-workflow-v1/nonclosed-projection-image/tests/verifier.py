import json
from fractions import Fraction
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
LIMITATION = "The verifier checks exact sequence identities and analytic bounds but does not formalize Hilbert-space topology in a proof assistant."


def _source() -> dict[str, Any]:
    try:
        raw = (TESTS / "input.json").read_bytes()
        if (WORKSPACE / "input.json").read_bytes() != raw:
            return {}
        value = json.loads(raw)
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _fraction(value: object) -> Fraction | None:
    if not isinstance(value, str):
        return None
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None
    return result if str(result) == value else None


def _result(value: object, source: dict[str, Any]) -> bool:
    required = {
        "space",
        "operator",
        "subspace",
        "projection",
        "prefixes",
        "tail_bound",
        "limit_preimage",
    }
    if not isinstance(value, dict) or set(value) != required:
        return False
    provenance = source.get("source", {})
    if provenance.get("revision") != "d4e9f8ca877552f4491a9c2d52e0d230c0fca620":
        return False
    if any(
        value[key] != expected
        for key, expected in {
            "space": "ell2_direct_sum_ell2",
            "operator": "T(x)_n=x_n/n",
            "subspace": "closed_graph_of_bounded_T",
            "projection": "P(u,v)=(0,v)",
            "tail_bound": "sum_{n>m}1/n^2<=1/m",
            "limit_preimage": "x_n=1_not_in_ell2",
        }.items()
    ):
        return False
    prefixes = value["prefixes"]
    length = source.get("prefix_length")
    if not isinstance(prefixes, list) or len(prefixes) != length or length != 12:
        return False
    partial = Fraction(0)
    for n, item in enumerate(prefixes, start=1):
        if not isinstance(item, dict) or set(item) != {
            "n",
            "weight",
            "limit_norm_sq_partial",
            "preimage_norm_sq",
        }:
            return False
        partial += Fraction(1, n * n)
        if (
            item["n"] != n
            or _fraction(item["weight"]) != Fraction(1, n)
            or _fraction(item["limit_norm_sq_partial"]) != partial
            or item["preimage_norm_sq"] != n
        ):
            return False
    # Integral comparison: sum_{n>m} n^-2 <= integral_m^infinity x^-2 dx = 1/m.
    return all(
        sum(Fraction(1, n * n) for n in range(m + 1, 10_000)) < Fraction(1, m)
        for m in range(1, 13)
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
        term in text for term in ("ell2", "graph", "projection", "all-ones", "computed")
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
