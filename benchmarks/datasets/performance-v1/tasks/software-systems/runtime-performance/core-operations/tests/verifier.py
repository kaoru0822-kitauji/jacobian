from __future__ import annotations

import json
from pathlib import Path

from verifier_support import load_submission, read_evidence_json

EXPECTED = json.loads(Path("/tests/expected.json").read_text())


def emit(reward: float, **details: object) -> None:
    target = Path("/logs/verifier/reward.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"reward": reward, **details}, sort_keys=True))


submission = load_submission()
if not isinstance(submission, dict):
    emit(0.0, error="missing or malformed submission")
    raise SystemExit
required = {
    "task_id",
    "conclusion",
    "result",
    "claimed_assurance",
    "scope",
    "completeness",
    "evidence",
    "limitations",
}
contract = (
    set(submission) == required
    and submission.get("task_id") == EXPECTED["task_id"]
    and submission.get("conclusion") == "MEASURED"
    and submission.get("claimed_assurance") == "COMPUTED"
    and submission.get("completeness") == "COMPLETE"
    and isinstance(submission.get("scope"), str)
    and isinstance(submission.get("limitations"), list)
)
descriptors = submission.get("evidence")
by_path = (
    {item.get("path"): item for item in descriptors if isinstance(item, dict)}
    if isinstance(descriptors, list)
    else {}
)
raw = read_evidence_json(
    by_path.get("evidence/pyperf.json"),
    expected_path="evidence/pyperf.json",
)
environment = read_evidence_json(
    by_path.get("evidence/environment.json"),
    expected_path="evidence/environment.json",
)
benchmarks = raw.get("benchmarks") if isinstance(raw, dict) else None
names = (
    {
        item.get("metadata", {}).get("name")
        for item in benchmarks
        if isinstance(item, dict)
    }
    if isinstance(benchmarks, list)
    else set()
)
result = submission.get("result")
correct = bool(
    contract
    and isinstance(result, dict)
    and set(result) == {"suite", "benchmark_count", "raw_format"}
    and result.get("suite") == EXPECTED["suite"]
    and result.get("raw_format") == "pyperf"
    and result.get("benchmark_count") == len(benchmarks or [])
    and set(EXPECTED["benchmarks"]) <= names
    and isinstance(environment, dict)
    and environment.get("repository_revision")
    and environment.get("driver_sha256")
)
emit(
    1.0 if correct else 0.0,
    contract_valid=contract,
    evidence_valid=bool(raw and environment),
    measurements_valid=correct,
    timing_threshold_applied=False,
)
