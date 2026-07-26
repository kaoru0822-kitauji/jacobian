from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from jacobian.lean_exploration import LeanReplPolicy, PersistentLeanRepl

_FAKE_REPL = r"""
import json
import pathlib
import sys

starts = pathlib.Path(sys.argv[1])
starts.write_text(starts.read_text() + "x" if starts.exists() else "x")
proof_state = 0
env = 0

while True:
    lines = []
    for line in sys.stdin:
        if not line.strip():
            break
        lines.append(line)
    if not lines:
        break
    request = json.loads("".join(lines))
    if request.get("cmd") == "import Mathlib":
        response = {"env": env}
        env += 1
    elif "cmd" in request:
        assert request.get("env") == 0
        response = {
            "env": env,
            "sorries": [{"proofState": proof_state}],
        }
        env += 1
        proof_state += 1
    else:
        assert request["proofState"] == proof_state - 1
        response = {
            "proofState": proof_state,
            "proofStatus": "Completed",
            "goals": [],
        }
        proof_state += 1
    print(json.dumps(response), end="\n\n", flush=True)
"""


def test_persistent_repl_reuses_import_then_restarts_at_request_limit(
    tmp_path: Path,
) -> None:
    starts = tmp_path / "starts"
    repl = PersistentLeanRepl(
        command=(sys.executable, "-u", "-c", _FAKE_REPL, str(starts)),
        cwd=tmp_path,
        base_command="import Mathlib",
        policy=LeanReplPolicy(max_requests=2, max_age_seconds=60, max_rss_kb=0),
    )

    first = repl.execute(command="example : True := by sorry", tactic="trivial")
    second = repl.execute(command="example : True := by sorry", tactic="trivial")
    third = repl.execute(command="example : True := by sorry", tactic="trivial")
    repl.close()

    assert all(
        response[1]["proofStatus"] == "Completed" for response in (first, second, third)
    )
    assert starts.read_text() == "xx"


def test_persistent_repl_kills_a_timed_out_process(tmp_path: Path) -> None:
    repl = PersistentLeanRepl(
        command=(sys.executable, "-u", "-c", "import time; time.sleep(10)"),
        cwd=tmp_path,
        base_command=None,
        policy=LeanReplPolicy(
            max_requests=2,
            max_age_seconds=60,
            max_rss_kb=0,
            timeout_seconds=0.05,
        ),
    )

    started = time.monotonic()
    with pytest.raises(RuntimeError, match="timed out"):
        repl.execute(command="example : True := by sorry", tactic="trivial")

    assert time.monotonic() - started < 2
