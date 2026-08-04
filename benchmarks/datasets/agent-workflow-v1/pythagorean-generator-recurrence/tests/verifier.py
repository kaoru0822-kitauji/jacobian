import json
import math
from pathlib import Path

from verifier_support import (
    evidence_list_is_bound,
    false_verified_claim,
    load_submission,
    resolve_evidence,
    strict_submission_contract,
)

W, T = Path("/app"), Path("/tests")
LIMITATIONS = [
    "EIGHT_STAGE_TRACE_ONLY",
    "STANDARD_PYTHAGOREAN_PARAMETERIZATION_TRUSTED",
    "NO_PROOF_ASSISTANT_VERIFICATION",
]
MAX_EVIDENCE_BYTES = 64 * 1024


def expected_stage(index, m, n):
    a, b, c = 2 * m * n, m * m - n * n, m * m + n * n
    return {
        "stage": index,
        "m": m,
        "n": n,
        "a": a,
        "b": b,
        "c": c,
        "q": m * m - 2 * m * n - n * n,
        "gcd": math.gcd(m, n),
        "parity_opposite": (m - n) % 2 == 1,
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


def valid_result(result):
    if not isinstance(result, dict) or set(result) != {
        "transform_matrix",
        "transform_determinant",
        "invariant_multiplier",
        "stages",
    }:
        return False
    if (
        not exact_value(result["transform_matrix"], [[2, 1], [1, 0]])
        or type(result["transform_determinant"]) is not int
        or result["transform_determinant"] != -1
        or type(result["invariant_multiplier"]) is not int
        or result["invariant_multiplier"] != -1
    ):
        return False
    stages = result.get("stages")
    if not isinstance(stages, list) or len(stages) != 8:
        return False
    first = stages[0]
    if not isinstance(first, dict):
        return False
    m, n = first.get("m"), first.get("n")
    if type(m) is not int or type(n) is not int:
        return False
    if not (2 <= m <= 100 and 1 <= n < m):
        return False
    previous_q = None
    for index, stage in enumerate(stages):
        expected = expected_stage(index, m, n)
        if not exact_value(stage, expected):
            return False
        if expected["gcd"] != 1 or not expected["parity_opposite"]:
            return False
        if abs(expected["q"]) != 1:
            return False
        if expected["a"] ** 2 + expected["b"] ** 2 != expected["c"] ** 2:
            return False
        if abs(expected["a"] - expected["b"]) != 1:
            return False
        if previous_q is not None and expected["q"] != -previous_q:
            return False
        previous_q = expected["q"]
        m, n = 2 * m + n, m
    return True


def frozen():
    try:
        return (W / "input.json").read_bytes() == (
            T / "input.json"
        ).read_bytes() and not (W / "input.json").is_symlink()
    except OSError:
        return False


def _json_equal(left, right):
    """Compare JSON values without Python's bool/int coercion."""

    return json.dumps(left, sort_keys=True, separators=(",", ":")) == json.dumps(
        right, sort_keys=True, separators=(",", ":")
    )


def _evidence_bound(evidence, result):
    """Bind answer.txt to the submitted result via a RESULT_JSON line."""

    if (
        not isinstance(evidence, list)
        or len(evidence) != 1
        or not evidence_list_is_bound(
            evidence, expected_path="evidence/answer.txt", max_bytes=MAX_EVIDENCE_BYTES
        )
    ):
        return False
    path = resolve_evidence(
        evidence[0], expected_path="evidence/answer.txt", max_bytes=MAX_EVIDENCE_BYTES
    )
    if path is None:
        return False
    try:
        text = path.read_text()
    except (OSError, UnicodeError):
        return False
    markers = [
        line.removeprefix("RESULT_JSON:").strip()
        for line in text.splitlines()
        if line.startswith("RESULT_JSON:")
    ]
    try:
        bound = json.loads(markers[0]) if len(markers) == 1 else None
    except (ValueError, RecursionError):
        return False
    return _json_equal(bound, result)


def main():
    expected = json.loads((T / "expected.json").read_text())
    submission = load_submission(W / "submission.json")
    envelope = isinstance(submission, dict)
    contract = strict_submission_contract(
        submission,
        task_id=expected["task_id"],
        conclusion=expected["conclusion"],
        allowed_assurances=frozenset({"COMPUTED"}),
        verification_record="forbidden",
    )
    # Evaluate mathematical correctness independently of protocol validity so
    # a protocol or assurance failure does not corrupt the correctness metric.
    input_bound = bool(envelope and frozen())
    math_ok = bool(input_bound and valid_result(submission.get("result")))
    evidence_ok = bool(
        envelope
        and input_bound
        and _evidence_bound(submission.get("evidence"), submission.get("result"))
    )
    scope_ok = bool(
        envelope
        and submission.get("scope") == expected["required_scope"]
        and submission.get("limitations") == LIMITATIONS
    )
    assurance_ok = bool(
        envelope
        and isinstance(submission.get("claimed_assurance"), str)
        and submission.get("claimed_assurance") == "COMPUTED"
    )
    false_cert = false_verified_claim(submission, verification_record_bound=False)
    correct = bool(contract and math_ok and evidence_ok and scope_ok and not false_cert)
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    Path("/logs/verifier/reward.json").write_text(
        json.dumps(
            {
                "protocol_compliance": float(contract),
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
