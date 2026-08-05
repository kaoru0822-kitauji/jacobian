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
tasks = report.get("tasks") if isinstance(report, dict) else None
expected_task_ids = {"CONJUNCTION-DECOMPOSITION", "LOCAL-PREMISE-APPLICATION"}
valid_tasks = bool(
    isinstance(tasks, list)
    and len(tasks) == 2
    and all(
        isinstance(item, dict) and type(item.get("task_id")) is str for item in tasks
    )
    and {item["task_id"] for item in tasks} == expected_task_ids
)
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
    and isinstance(report, dict)
    and report.get("protocol") == "leanprover-community/repl"
    and report.get("task_count") == 2
    and report.get("completed_count") == 2
    and report.get("parameter_error_count") == 0
    and report.get("return_code") == 0
    and valid_tasks
    and all(
        isinstance(item, dict)
        and item.get("completed") is True
        and item.get("decomposition_observed") is True
        and isinstance(item.get("tactics"), list)
        and item["tactics"]
        and all(
            isinstance(trace, dict)
            and isinstance(trace.get("tactic"), str)
            and type(trace.get("goal_count")) is int
            and type(trace.get("error_count")) is int
            and trace.get("error_count") == 0
            for trace in item["tactics"]
        )
        for item in tasks
    )
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
