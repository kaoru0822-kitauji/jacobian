import json
from pathlib import Path

from verifier_support import (
    false_verified_claim,
    load_submission,
    read_evidence_json,
    strict_submission_contract,
)

W, E = Path("/app"), Path("/tests")

PRIME_FORMULA = "2^(p+1)+p*2^(2p)"
THRESHOLD_RULE = "n>=max(2,k)_implies_2^k_divides_a_n"


def _is_small_odd_prime(p):
    """Bound p before any exponentiation so a huge probe cannot OOM the verifier."""

    if type(p) is not int or p < 3 or p > 97 or p % 2 == 0:
        return False
    return all(p % d for d in range(3, int(p**0.5) + 1, 2))


def _result_ok(result):
    if not isinstance(result, dict) or set(result) != {
        "a_1",
        "default_exponent_offset",
        "prime_formula",
        "threshold_rule",
        "probes",
    }:
        return False
    if (
        type(result["a_1"]) is not int
        or result["a_1"] != 1
        or type(result["default_exponent_offset"]) is not int
        or result["default_exponent_offset"] != 1
        or result["prime_formula"] != PRIME_FORMULA
        or result["threshold_rule"] != THRESHOLD_RULE
    ):
        return False
    probes = result["probes"]
    if not isinstance(probes, list) or not 4 <= len(probes) <= 10:
        return False
    primes = []
    for probe in probes:
        if not isinstance(probe, dict) or set(probe) != {
            "prime",
            "a_p",
            "b_p",
            "square_root",
        }:
            return False
        p = probe["prime"]
        if not _is_small_odd_prime(p):
            return False
        if not all(type(probe[k]) is int for k in ("a_p", "b_p", "square_root")):
            return False
        a_p = 2 ** (p + 1) + p * 2 ** (2 * p)
        root = 1 + p * 2**p
        if (
            probe["a_p"] != a_p
            or probe["b_p"] != 1 + p * a_p
            or probe["square_root"] != root
            or probe["b_p"] != root * root
        ):
            return False
        primes.append(p)
    return len(primes) == len(set(primes))


def _frozen_ok():
    try:
        raw = (E / "input.json").read_bytes()
        return (
            not (W / "input.json").is_symlink()
            and (W / "input.json").read_bytes() == raw
            and json.loads(raw).get("task_id")
            == "jacobian/divisor-sum-square-sequence-repair"
        )
    except (OSError, ValueError):
        return False


def main():
    submission = load_submission()
    expected = json.loads((E / "expected.json").read_text())
    contract = strict_submission_contract(
        submission,
        task_id=expected["task_id"],
        conclusion=expected["conclusion"],
        allowed_assurances=frozenset({"UNVERIFIED", "COMPUTED"}),
        verification_record="forbidden",
    )
    # Evaluate the mathematical result independently of the protocol contract so
    # a false-certification (e.g. unsupported VERIFIED) does not collapse a
    # shape-safe correct mathematical result into a mathematical failure.  The
    # aggregate reward is still forced to zero below when the contract fails.
    shape_safe = isinstance(submission, dict) and isinstance(
        submission.get("result"), dict
    )
    result = submission.get("result") if shape_safe else None
    math_ok = bool(_result_ok(result) and _frozen_ok())
    evidence = (
        read_evidence_json(
            submission["evidence"][0],
            expected_path="evidence/sequence-construction.json",
        )
        if shape_safe
        and isinstance(submission.get("evidence"), list)
        and len(submission["evidence"]) == 1
        else None
    )
    evidence_ok = bool(
        evidence
        and set(evidence) == {"schema_version", "task_id", "result", "limitations"}
        and evidence["schema_version"] == "1"
        and evidence["task_id"] == expected["task_id"]
        and evidence["result"] == result
        and evidence["limitations"] == submission.get("limitations")
    )
    scope_ok = bool(
        shape_safe
        and submission.get("scope") == "DECLARED_SEQUENCE_FORMULA_AND_PRIME_PROBES"
        and submission.get("limitations")
        == [
            "INFINITE_PRIMES_THEOREM_TRUSTED",
            "QUANTIFIED_SEQUENCE_MEMBERSHIP_NOT_PROOF_ASSISTANT_VERIFIED",
        ]
    )
    assurance_ok = bool(contract and submission.get("claimed_assurance") == "COMPUTED")
    false_cert = false_verified_claim(submission, verification_record_bound=False)
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
