from __future__ import annotations

from types import SimpleNamespace

from tools import check_benchmark_static


def test_static_commands_scan_benchmarks_without_execution_commands() -> None:
    commands = check_benchmark_static._commands()

    assert [label for label, _ in commands] == ["Ruff lint", "Ruff format", "mypy"]
    assert any(
        "benchmarks" in argument for _, command in commands[:2] for argument in command
    )
    assert all(
        argument not in {"pytest", "harbor", "oracle", "model"}
        for _, command in commands
        for argument in command
    )


def test_static_gate_stops_and_fails_closed_on_a_failed_check(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(command, *, cwd, check):
        calls.append(command)
        assert cwd == check_benchmark_static.ROOT
        assert check is False
        return SimpleNamespace(returncode=9)

    monkeypatch.setattr(check_benchmark_static.subprocess, "run", fake_run)

    assert check_benchmark_static.main() == 9
    assert len(calls) == 1
