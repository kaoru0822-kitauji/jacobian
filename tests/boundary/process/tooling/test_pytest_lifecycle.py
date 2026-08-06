from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.tooling.command_runner import (
    ToolCommandRequest,
    ToolCommandResult,
    ToolCommandStatus,
)
from tools import pytest_lifecycle


def _tool_result(exit_code: int) -> ToolCommandResult:
    return ToolCommandResult(
        status=ToolCommandStatus.EXITED,
        exit_code=exit_code,
        stdout=b"",
        stderr=b"",
    )


def test_success_uses_unique_worktree_basetemp_and_cleans_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: list[tuple[str, ...]] = []

    def run(request: object) -> ToolCommandResult:
        observed.append(request.arguments)  # type: ignore[attr-defined]
        basetemp_argument = next(
            argument
            for argument in request.arguments  # type: ignore[attr-defined]
            if argument.startswith("--basetemp=")
        )
        basetemp = Path(basetemp_argument.split("=", 1)[1])
        (basetemp.parent / "session-template").mkdir()
        return _tool_result(0)

    monkeypatch.setattr(pytest_lifecycle, "run_tool_command", run)

    first = pytest_lifecycle.run_pytest(
        ["tests/unit/test_one.py"],
        root=tmp_path,
        name="unit",
        environment={},
    )
    second = pytest_lifecycle.run_pytest(
        ["tests/unit/test_one.py"],
        root=tmp_path,
        name="unit",
        environment={},
    )

    assert first.basetemp != second.basetemp
    assert first.basetemp.is_relative_to(tmp_path / ".pytest_cache" / "basetemp")
    assert first.basetemp.name == "pytest"
    assert not first.basetemp.exists()
    assert not first.basetemp.parent.exists()
    assert not second.basetemp.exists()
    assert any(argument.startswith("--basetemp=") for argument in observed[0])


def test_failure_cleanup_is_default_and_retention_is_opt_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        pytest_lifecycle, "run_tool_command", lambda request: _tool_result(1)
    )

    cleaned = pytest_lifecycle.run_pytest(
        ["test_bad.py"], root=tmp_path, name="clean", environment={}
    )
    retained = pytest_lifecycle.run_pytest(
        ["test_bad.py"],
        root=tmp_path,
        name="retain",
        environment={},
        retain_on_failure=True,
    )

    assert not cleaned.basetemp.exists()
    assert retained.retained is True
    assert retained.basetemp.is_dir()


def test_receipt_records_prediction_and_actual_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        pytest_lifecycle, "run_tool_command", lambda request: _tool_result(0)
    )
    receipt = tmp_path / "evidence" / "pytest-receipt.json"

    pytest_lifecycle.run_pytest(
        ["test_ok.py"],
        root=tmp_path,
        name="host-validation/full-1-of-4",
        environment={},
        receipt=receipt,
        predicted_seconds=180.0,
    )

    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["name"] == "host-validation/full-1-of-4"
    assert payload["predicted_seconds"] == 180.0
    assert payload["actual_seconds"] >= 0
    assert payload["exit_code"] == 0


def test_explicit_basetemp_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="owned"):
        pytest_lifecycle.run_pytest(
            ["--basetemp=/tmp/shared"],
            root=tmp_path,
            name="unsafe",
            environment={},
        )


def test_run_streams_output_once_and_emits_lifecycle_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    def run(request: ToolCommandRequest) -> ToolCommandResult:
        assert request.stdout_sink is not None
        assert request.stderr_sink is not None
        request.stdout_sink(b"live output\n")
        request.stderr_sink(b"live warning\n")
        return ToolCommandResult(
            status=ToolCommandStatus.EXITED,
            exit_code=0,
            stdout=b"live output\n",
            stderr=b"live warning\n",
        )

    monkeypatch.setattr(pytest_lifecycle, "run_tool_command", run)

    pytest_lifecycle.run_pytest(
        ["test_ok.py"],
        root=tmp_path,
        name="process/shard-1",
        environment={},
        predicted_seconds=12.0,
    )

    captured = capfd.readouterr()
    assert captured.out == "live output\n"
    assert captured.err.count("live warning") == 1
    events = [
        json.loads(line.removeprefix("[pytest-lifecycle] "))
        for line in captured.err.splitlines()
        if line.startswith("[pytest-lifecycle] ")
    ]
    assert events[0] == {
        "event": "pytest.run.started",
        "name": "process/shard-1",
        "predicted_seconds": 12.0,
        "timeout_seconds": 3600.0,
    }
    assert events[1]["event"] == "pytest.run.completed"
    assert events[1]["name"] == "process/shard-1"
    assert events[1]["status"] == "EXITED"
    assert events[1]["exit_code"] == 0
    assert events[1]["actual_seconds"] >= 0
