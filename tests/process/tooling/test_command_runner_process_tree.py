from __future__ import annotations

import os
import sys
import time
from io import StringIO
from pathlib import Path

import pytest
from tools.command_runner import (
    ToolCommandRequest,
    ToolCommandStatus,
    output_sink,
    run_tool_command,
)

ROOT = Path(__file__).resolve().parents[3]


def test_timeout_kills_a_descendant_that_ignores_sigterm(tmp_path: Path) -> None:
    marker = tmp_path / "child.pid"
    script = tmp_path / "ignore_term.py"
    script.write_text(
        "\n".join(
            [
                "import os",
                "import signal",
                "import time",
                "import sys",
                "child = os.fork()",
                "if child == 0:",
                "    signal.signal(signal.SIGTERM, signal.SIG_IGN)",
                "    with open(sys.argv[1], 'w', encoding='utf-8') as handle:",
                "        handle.write(str(os.getpid()))",
                "        handle.flush()",
                "        os.fsync(handle.fileno())",
                "    time.sleep(30)",
                "    os._exit(0)",
                "time.sleep(30)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_tool_command(
        ToolCommandRequest(
            executable=str(Path(sys.executable).resolve()),
            arguments=(str(script), str(marker)),
            environment=dict(os.environ),
            cwd=str(ROOT),
            timeout_seconds=1.0,
            stdout_limit_bytes=4096,
            stderr_limit_bytes=4096,
        )
    )

    assert result.status is ToolCommandStatus.TIMED_OUT

    # Wait for the descendant PID marker until the deadline.
    deadline = time.monotonic() + 5
    child_pid: int | None = None
    while time.monotonic() < deadline:
        if marker.exists():
            text = marker.read_text(encoding="utf-8").strip()
            if text:
                child_pid = int(text)
                break
        time.sleep(0.05)

    if child_pid is None:
        raise AssertionError("descendant did not record its pid before timeout")

    # Verify the SIGTERM-ignoring descendant was actually killed.
    # Poll for termination: the runner sends SIGTERM then SIGKILL.
    kill_deadline = time.monotonic() + 10
    still_alive = True
    while time.monotonic() < kill_deadline:
        try:
            os.kill(child_pid, 0)
        except OSError:
            still_alive = False
            break
        time.sleep(0.05)

    assert still_alive is False, (
        f"descendant (pid={child_pid}) survived timeout — SIGKILL not sent?"
    )


def test_explicit_parent_environment_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JACOBIAN_COMMAND_RUNNER_ENV_PROBE", "available")

    result = run_tool_command(
        ToolCommandRequest(
            executable=str(Path(sys.executable).resolve()),
            arguments=(
                "-c",
                "import os; raise SystemExit(os.environ['JACOBIAN_COMMAND_RUNNER_ENV_PROBE'] != 'available')",
            ),
            environment=dict(os.environ),
            cwd=str(tmp_path),
            timeout_seconds=5.0,
            stdout_limit_bytes=4096,
            stderr_limit_bytes=4096,
        )
    )

    assert result.exit_code == 0
    assert result.status is ToolCommandStatus.EXITED


def test_text_only_output_stream_receives_decoded_child_output(
    tmp_path: Path,
) -> None:
    output = StringIO()

    result = run_tool_command(
        ToolCommandRequest(
            executable=str(Path(sys.executable).resolve()),
            arguments=("-c", "print('hello')"),
            environment=dict(os.environ),
            cwd=str(tmp_path),
            timeout_seconds=5.0,
            stdout_limit_bytes=4096,
            stderr_limit_bytes=4096,
            stdout_sink=output_sink(output),
        )
    )

    assert result.exit_code == 0
    assert output.getvalue() == "hello\n"
