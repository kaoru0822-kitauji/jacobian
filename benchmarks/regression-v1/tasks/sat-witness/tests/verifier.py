import hashlib
import json
from pathlib import Path

W = Path("/app")
E = Path("/tests")


def _digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _descriptor_target(descriptor, expected_path):
    if not isinstance(descriptor, dict):
        return None
    if not isinstance(descriptor.get("path"), str) or not isinstance(
        descriptor.get("sha256"), str
    ):
        return None
    p = Path(descriptor["path"])
    if (
        p != Path(expected_path)
        or p.is_absolute()
        or ".." in p.parts
        or (W / p).is_symlink()
    ):
        return None
    target = (W / p).resolve()
    if not target.is_relative_to(W.resolve()) or not target.is_file():
        return None
    if descriptor["sha256"] != _digest(target):
        return None
    return target


def _descriptor_json(descriptor, expected_path):
    target = _descriptor_target(descriptor, expected_path)
    if target is None:
        return None
    try:
        return json.loads(target.read_text())
    except (OSError, ValueError):
        return None


def _answer_evidence(submission):
    entries = submission.get("evidence") if isinstance(submission, dict) else None
    if not isinstance(entries, list) or not entries:
        return False
    return all(
        _descriptor_target(entry, "evidence/answer.txt") is not None for entry in entries
    )


def _record_is_bound(submission, input_data, assignment, sat):
    if not sat:
        return False
    record = _descriptor_json(
        submission.get("verification_record_uri"), "evidence/verification-record.json"
    )
    if not isinstance(record, dict):
        return False
    if set(record) != {
        "task_id",
        "input_sha256",
        "conclusion",
        "status",
        "assignment",
        "scope",
        "checker_id",
    }:
        return False
    return (
        record["task_id"] == input_data["task_id"]
        and record["input_sha256"] == _digest(W / "input.json")
        and record["conclusion"] == "TRUE"
        and record["status"] == "VERIFIED_SATISFYING"
        and record["assignment"] == assignment
        and record["scope"] == "sat-witness complete finite input"
        and isinstance(record["checker_id"], str)
        and bool(record["checker_id"])
    )


def main():
    try:
        s = json.loads((W / "submission.json").read_text())
    except (OSError, ValueError):
        s = None
    x = json.loads((W / "input.json").read_text())
    e = json.loads((E / "expected.json").read_text())
    contract = (
        isinstance(s, dict)
        and all(
            k in s
            for k in (
                "task_id",
                "conclusion",
                "result",
                "claimed_assurance",
                "scope",
                "completeness",
                "evidence",
                "limitations",
            )
        )
        and s.get("task_id") == e["task_id"]
        and s.get("conclusion") == e["conclusion"]
        and s.get("completeness") == "COMPLETE"
        and isinstance(s.get("result"), dict)
        and isinstance(s.get("scope"), str)
        and isinstance(s.get("limitations"), list)
        and s.get("claimed_assurance")
        in {"UNVERIFIED", "COMPUTED", "CHECKED", "VERIFIED"}
    )
    result = s.get("result", {}) if isinstance(s, dict) else {}
    a = result.get("assignment", {}) if isinstance(result, dict) else {}
    valid = (
        isinstance(a, dict)
        and set(a) == set(x["variables"])
        and all(isinstance(v, bool) for v in a.values())
    )
    sat = valid and all(
        any((lit > 0) == a[x["variables"][abs(lit) - 1]] for lit in c)
        for c in x["clauses"]
    )
    claimed_verified = isinstance(s, dict) and s.get("claimed_assurance") == "VERIFIED"
    record_bound = _record_is_bound(s, x, a, sat) if isinstance(s, dict) else False
    correct = bool(
        contract
        and result.get("status") == "SATISFIABLE"
        and sat
        and (not claimed_verified or record_bound)
    )
    good = _answer_evidence(s) if contract else False
    if claimed_verified:
        good = good and record_bound
    scope = bool(contract and s["scope"] == " ".join(e["required_scope_terms"]))
    assurance = bool(
        contract
        and (
            s["claimed_assurance"] == e["maximum_assurance"]
            or (claimed_verified and record_bound)
        )
    )
    false = claimed_verified and not record_bound
    reward = (
        0
        if not correct or false
        else 0.7 * correct + 0.1 * good + 0.1 * scope + 0.1 * assurance
    )
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    (Path("/logs/verifier/reward.json")).write_text(
        json.dumps(
            {
                "correctness": float(correct),
                "evidence_validity": float(good),
                "scope_accuracy": float(scope),
                "assurance_calibration": float(assurance),
                "reward": reward,
                "false_certification": false,
            }
        )
    )


if __name__ == "__main__":
    main()
