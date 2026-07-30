import hashlib
import json
from pathlib import Path

W = Path("/app")
E = Path("/tests")
AUTHORIZED_CHECKER_ID = (
    "checker://sha256/4f4ab2af490f33c77f9035ef1bef083f145553fb1ab3c578cb5b1dcf2f2f2cc0"
)
AUTHORIZED_CHECKER_DIGEST = (
    "sha256:b9c178342e86f2d533db8336162c063b64034aa99f6e84856058a0d1df4a831f"
)
AUTHORIZED_VERIFICATION_RECORD = {
    "record_schema_version": "1",
    "checker_id": AUTHORIZED_CHECKER_ID,
    "checker_digest": AUTHORIZED_CHECKER_DIGEST,
    "evidence_kind": "WITNESS",
    "evidence_uri": (
        "artifact://sha256/"
        "d98a2a68ff7ef2c48d50eca71a1618a99d8f35005f2ff82c64701a02efe71342"
    ),
    "bindings": {
        "claim_digest": (
            "sha256:6204650d53228c9801de367990c10bb3541a82ab33cef3f81165d337712b0b7a"
        ),
        "semantics_digest": (
            "sha256:663ed4ee4e97d0474bca04a9ffe71a56fc6569cb92d864ec208256a438e779622"
        ),
        "candidate_digest": (
            "sha256:0067fcba7f58ea779b0d88af49944b41d9127b8ca177d766b2f99962741d55ff"
        ),
        "scope_digest": None,
        "encoding_digest": None,
    },
    "conclusion": "TRUE",
    "arithmetic": "EXACT_INTEGER",
    "method": "DIRECT_WITNESS",
    "coverage": "NOT_APPLICABLE",
    "request_digest": (
        "sha256:557d49f80ad560c762200f3ad8f2288eb5940ff83130ce6aa640b3601388f94e"
    ),
    "environment_digest": (
        "sha256:a308d74b82cc9e43e018cb17c79180e1da140e3034feb4be03be9a6d9778d7a2"
    ),
    "relation_id": None,
    "relationship_source_artifact_uris": [],
    "relationship_target_artifact_uris": [],
    "obligation_uri": None,
}


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
        _descriptor_target(entry, "evidence/answer.txt") is not None
        for entry in entries
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
        "verification_record",
    }:
        return False
    verification_record = record["verification_record"]
    if not isinstance(verification_record, dict):
        return False
    if set(verification_record) != {
        "record_schema_version",
        "checker_id",
        "checker_digest",
        "evidence_kind",
        "evidence_uri",
        "bindings",
        "conclusion",
        "arithmetic",
        "method",
        "coverage",
        "request_digest",
        "environment_digest",
        "relation_id",
        "relationship_source_artifact_uris",
        "relationship_target_artifact_uris",
        "obligation_uri",
    }:
        return False
    bindings = verification_record["bindings"]
    if not isinstance(bindings, dict) or set(bindings) != {
        "claim_digest",
        "semantics_digest",
        "candidate_digest",
        "scope_digest",
        "encoding_digest",
    }:
        return False
    return (
        record["task_id"] == input_data["task_id"]
        and record["input_sha256"] == _digest(W / "input.json")
        and record["conclusion"] == "TRUE"
        and record["status"] == "VERIFIED_SATISFYING"
        and record["assignment"] == assignment
        and record["scope"] == "sat-witness complete finite input"
        and verification_record == AUTHORIZED_VERIFICATION_RECORD
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
