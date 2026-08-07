from __future__ import annotations

import json
from pathlib import Path

from verifier_support import load_submission, read_evidence_json

expected = json.loads(Path("/tests/expected.json").read_text())
submission = load_submission()
report = None
if isinstance(submission, dict) and isinstance(submission.get("evidence"), list):
    report = read_evidence_json(
        submission["evidence"][0] if len(submission["evidence"]) == 1 else None,
        expected_path="evidence/provider-report.json",
    )
result = submission.get("result") if isinstance(submission, dict) else None


def _digest_ok(value: object) -> bool:
    return isinstance(value, str) and value.startswith("sha256:") and len(value) == 71


def _execution_bound(report: object) -> bool:
    """Reject reports that only restate public spike success literals."""

    if not isinstance(report, dict):
        return False
    if report.get("contract") != expected["contract"]:
        return False
    if report.get("status") != "COMPLETED":
        return False
    if report.get("conclusion") != expected["report_conclusion"]:
        return False
    if report.get("assurance") != expected["report_assurance"]:
        return False
    provider = report.get("provider")
    reproduction = report.get("reproduction")
    if not isinstance(provider, dict) or not isinstance(reproduction, dict):
        return False
    executables = provider.get("executables")
    if not isinstance(executables, dict) or not executables:
        return False
    expected_graph6 = reproduction.get("expected_graph6")
    if not isinstance(expected_graph6, list) or not expected_graph6:
        return False
    if type(reproduction.get("observed_count")) is not int:
        return False
    if not _digest_ok(reproduction.get("observed_output_sha256")):
        return False
    if not _digest_ok(reproduction.get("expected_output_sha256")):
        return False
    limitations = report.get("limitations")
    if not isinstance(limitations, list) or not limitations:
        return False
    return set(report) > {"contract", "status", "conclusion", "assurance"}


valid = bool(
    isinstance(submission, dict)
    and set(submission)
    == {
        "task_id",
        "conclusion",
        "result",
        "claimed_assurance",
        "scope",
        "completeness",
        "evidence",
        "limitations",
    }
    and submission.get("task_id") == expected["task_id"]
    and submission.get("conclusion") == "FEASIBLE"
    and submission.get("claimed_assurance") == "COMPUTED"
    and submission.get("completeness") == "COMPLETE"
    and isinstance(result, dict)
    and result
    == {
        "provider": expected["provider"],
        "contract": expected["contract"],
        "status": "COMPLETED",
        "pin_sha256": expected["pin_sha256"],
    }
    and _execution_bound(report)
)
target = Path("/logs/verifier/reward.json")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(
    json.dumps(
        {
            "reward": 1.0 if valid else 0.0,
            "pin_fidelity": float(valid),
            "provider_outcome": float(valid),
            "false_certification": bool(
                isinstance(submission, dict)
                and submission.get("claimed_assurance") == "VERIFIED"
            ),
        },
        sort_keys=True,
    )
)
