from __future__ import annotations

import json
from pathlib import Path

from benchmarks.validation.agent_workflow_v1 import support

TASK = "sine-integral-asymptotic-audit"


def _submission(app: Path) -> dict[str, object]:
    return json.loads((app / "submission.json").read_text())


def test_accepts_reordered_equivalent_terms(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = _submission(app)
    result = submission["result"]
    assert isinstance(result, dict)
    result["tail_terms"] = list(reversed(result["tail_terms"]))
    result["si_terms"] = list(reversed(result["si_terms"]))
    support._write_json(app / "submission.json", submission)
    assert support._run_verifier(task, app, logs)["reward"] == 1.0


def test_rejects_published_wrong_sine_sign(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = _submission(app)
    result = submission["result"]
    assert isinstance(result, dict)
    for term in result["si_terms"]:
        if term["function"] == "SIN" and term["power"] == 2:
            term["coefficient"] = 1
    result["corrected_sine_coefficient"] = 1
    support._write_json(app / "submission.json", submission)
    assert support._run_verifier(task, app, logs)["correctness"] == 0.0


def test_rejects_corrupt_remainder_bound(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = _submission(app)
    result = submission["result"]
    assert isinstance(result, dict)
    result["absolute_remainder_bound"]["numerator"] = 23
    support._write_json(app / "submission.json", submission)
    assert support._run_verifier(task, app, logs)["correctness"] == 0.0


def test_rejects_duplicate_evidence(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = _submission(app)
    submission["evidence"].append(dict(submission["evidence"][0]))
    support._write_json(app / "submission.json", submission)
    assert support._run_verifier(task, app, logs)["reward"] == 0.0
