import copy
import hashlib
import json
import shutil
from pathlib import Path

from benchmarks.validation.agent_workflow_v1.support import _run_verifier

TASK = "divisor-sum-square-sequence-repair"
TASK_ID = f"jacobian/{TASK}"


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
        "task_id": TASK_ID,
        "result": submission["result"],
        "limitations": submission["limitations"],
    }
    path = app / "evidence/sequence-construction.json"
    path.write_text(json.dumps(evidence, separators=(",", ":")))
    submission["evidence"][0]["sha256"] = (
        "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    )
    (app / "submission.json").write_text(json.dumps(submission))
    return _run_verifier(task, app, logs)


def _probe(p):
    a = 2 ** (p + 1) + p * 2 ** (2 * p)
    return {"prime": p, "a_p": a, "b_p": 1 + p * a, "square_root": 1 + p * 2**p}


def test_oracle_and_alternative_primes(tmp_path):
    assert _verify(tmp_path / "oracle", _oracle())["reward"] == 1.0
    alt = _oracle()
    alt["result"]["probes"] = [_probe(p) for p in (13, 17, 19, 23)]
    assert _verify(tmp_path / "alt", alt)["reward"] == 1.0


def test_non_ascending_probe_order_accepted(tmp_path):
    """Distinct valid probes in any order earn full reward (T9)."""
    sub = _oracle()
    sub["result"]["probes"] = [_probe(p) for p in (5, 3, 7, 11)]
    assert _verify(tmp_path / "perm", sub)["reward"] == 1.0


def test_corruption_and_false_assurance_fail(tmp_path):
    for name, mutate in [
        ("square", lambda s: s["result"]["probes"][0].update(b_p=624)),
        ("assurance", lambda s: s.update(claimed_assurance="VERIFIED")),
    ]:
        submission = copy.deepcopy(_oracle())
        mutate(submission)
        assert _verify(tmp_path / name, submission)["reward"] == 0


def test_false_verified_preserves_correctness(tmp_path):
    """Unsupported VERIFIED must force reward 0 but not erase correctness (T10)."""
    sub = _oracle()
    sub["claimed_assurance"] = "VERIFIED"
    result = _verify(tmp_path / "false_verified", sub)
    assert result["reward"] == 0
    assert result["correctness"] == 1.0
    assert result["false_certification"] is True


def test_oversized_probe_rejected(tmp_path):
    """A huge probe prime must not crash the verifier; reward is 0 (T3)."""
    sub = _oracle()
    sub["result"]["probes"][0]["prime"] = 10**400
    result = _verify(tmp_path / "huge_probe", sub)
    assert result["reward"] == 0


def test_boolean_construction_fields_rejected(tmp_path):
    """JSON true must not satisfy integer fields (T8)."""
    for field in ("a_1", "default_exponent_offset"):
        sub = _oracle()
        sub["result"][field] = True
        assert _verify(tmp_path / f"bool_{field}", sub)["reward"] == 0


def test_float_probe_values_rejected(tmp_path):
    """Integral floats must not satisfy integer probe fields (T11)."""
    sub = _oracle()
    sub["result"]["probes"][0]["a_p"] = float(sub["result"]["probes"][0]["a_p"])
    assert _verify(tmp_path / "float_a_p", sub)["reward"] == 0


def test_old_threshold_rule_rejected(tmp_path):
    """The false threshold rule must no longer earn reward (T5)."""
    sub = _oracle()
    sub["result"]["threshold_rule"] = "n>=k_implies_a_n_divisible_by_2^k"
    assert _verify(tmp_path / "old_threshold", sub)["reward"] == 0
