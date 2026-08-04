import copy
import hashlib
import json
import shutil
from pathlib import Path

from benchmarks.validation.agent_workflow_v1.support import _run_verifier

TASK = "gf2-matrix-completion-quantifier-audit"


def _oracle():
    return json.loads(
        (
            Path("benchmarks/datasets/agent-workflow-v1")
            / TASK
            / "solution/submission.json"
        ).read_text()
    )


def _verify(tmp_path, submission):
    task = Path("benchmarks/datasets/agent-workflow-v1") / TASK
    app, logs = tmp_path / "app", tmp_path / "logs"
    (app / "evidence").mkdir(parents=True)
    logs.mkdir(parents=True)
    shutil.copy2(task / "environment/input.json", app / "input.json")
    evidence = {
        "schema_version": "1",
        "task_id": f"jacobian/{TASK}",
        "result": submission["result"],
        "limitations": submission["limitations"],
    }
    path = app / "evidence/matrix-completion.json"
    path.write_text(json.dumps(evidence, separators=(",", ":")))
    submission["evidence"][0]["sha256"] = (
        "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    )
    (app / "submission.json").write_text(json.dumps(submission))
    return _run_verifier(task, app, logs)


def test_oracle_passes(tmp_path):
    assert _verify(tmp_path, _oracle())["reward"] == 1.0


def test_rank_and_assurance_attacks_fail(tmp_path):
    for name, mutate in [
        (
            "rank",
            lambda s: s["result"].update(
                low_rank_completion=s["result"]["full_rank_completion"]
            ),
        ),
        ("assurance", lambda s: s.update(claimed_assurance="VERIFIED")),
    ]:
        submission = copy.deepcopy(_oracle())
        mutate(submission)
        assert _verify(tmp_path / name, submission)["reward"] == 0
