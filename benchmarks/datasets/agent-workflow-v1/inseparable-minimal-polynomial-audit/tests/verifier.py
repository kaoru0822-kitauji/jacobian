import json
import math
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
LIMITATION = "The checker validates the valuation and minimal-polynomial certificate contract, but does not replay a proof assistant or implement arbitrary rational-function fields."


def _source() -> dict[str, Any]:
    try:
        raw = (TESTS / "input.json").read_bytes()
        if (WORKSPACE / "input.json").read_bytes() != raw:
            return {}
        value = json.loads(raw)
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _prime(p: object) -> bool:
    return (
        type(p) is int
        and 2 <= p <= 97
        and all(p % d for d in range(2, math.isqrt(p) + 1))
    )


def _result(value: object, source: dict[str, Any]) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "diagnosis",
        "candidate_polynomial",
        "valuation_obstruction",
        "irreducibility",
        "minimal_polynomial",
        "inseparability",
        "sanity_prime",
    }:
        return False
    provenance = source.get("source", {})
    p = value["sanity_prime"]
    if not _prime(p):
        return False
    # Independently replay the characteristic-p derivative and exponent-class
    # separation used by the symbolic valuation obstruction.
    derivative_coeff = p % p
    exponent_classes = {0 % p, p % p}
    return bool(
        provenance.get("revision") == "f5935720f176cedff4ecd8ebf83d1696e31cfac8"
        and provenance.get("row") == 2
        and value["diagnosis"] == "ANNIHILATING_POLYNOMIAL_NOT_YET_MINIMAL"
        and value["candidate_polynomial"] == "X^p-u"
        and value["valuation_obstruction"]
        == {
            "v_u_u": 1,
            "pth_power_multiple": "p*integer",
            "residue_contradiction": [1, 0],
        }
        and value["irreducibility"] == "X^p-u_IRREDUCIBLE_OVER_K(u)"
        and value["minimal_polynomial"] == {"polynomial": "X^p-u", "degree": "p"}
        and value["inseparability"]
        == {
            "formal_derivative": "0",
            "root_multiplicity": "p",
            "conclusion": "t_INSEPARABLE_OVER_K(u)",
        }
        and derivative_coeff == 0
        and exponent_classes == {0}
        and 1 % p != 0
    )


def _evidence(value: object) -> bool:
    if not isinstance(value, list) or len(value) != 1 or not evidence_list_is_bound(value):
        return False
    assert isinstance(value, list)
    path = resolve_evidence(value[0], expected_path="evidence/answer.txt")
    if path is None:
        return False
    try:
        text = path.read_text().lower()
    except (OSError, UnicodeError):
        return False
    return bool(
        len(text) >= 180
        and all(
            term in text
            for term in (
                "annihilating",
                "irreducible",
                "valuation",
                "minimal polynomial",
            )
        )
        and "divisible by p" in text
        and "X^p-u" in text
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
    limitations = bool(
        contract
        and isinstance(data.get("limitations"), list)
        and any(
            isinstance(item, str)
            and "proof assistant" in item.casefold()
            and "not" in item.casefold()
            for item in data["limitations"]
        )
    )
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
