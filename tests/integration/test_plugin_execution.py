from __future__ import annotations

import time
from pathlib import Path

import pytest

from jacobian.plugin_execution import PluginExecutor


@pytest.mark.integration
def test_plugin_executor_returns_only_canonical_result() -> None:
    result = PluginExecutor().run(
        entrypoint="tests.fixtures.plugin_functions:echo",
        request={"candidate": {"value": 3}},
        timeout_seconds=30,
    )

    assert result.status.value == "COMPLETED"
    assert result.output == {"seen": {"candidate": {"value": 3}}}
    assert "untrusted plugin diagnostic" in result.diagnostics


@pytest.mark.integration
def test_plugin_executor_rejects_changed_implementation_digest() -> None:
    result = PluginExecutor().run(
        entrypoint="tests.fixtures.plugin_functions:echo",
        implementation_digest="sha256:" + "0" * 64,
        request={"candidate": {"value": 3}},
        timeout_seconds=30,
    )

    assert result.status.value == "ERROR"
    assert result.output is None
    assert "resolved digest" in (result.detail or "")


@pytest.mark.integration
def test_module_import_diagnostics_do_not_corrupt_worker_protocol() -> None:
    result = PluginExecutor().run(
        entrypoint="tests.fixtures.noisy_module:echo",
        request={"value": 7},
        timeout_seconds=30,
    )

    assert result.status.value == "COMPLETED"
    assert result.output == {"seen": {"value": 7}}
    assert "module import diagnostic" in result.diagnostics


@pytest.mark.integration
def test_plugin_timeout_has_no_mathematical_output() -> None:
    result = PluginExecutor().run(
        entrypoint="tests.fixtures.plugin_functions:wait_forever",
        request={},
        timeout_seconds=1,
    )

    assert result.status.value == "TIMEOUT"
    assert result.output is None


@pytest.mark.integration
def test_plugin_diagnostic_limit_fails_closed() -> None:
    start = time.monotonic()
    result = PluginExecutor(max_diagnostic_bytes=32).run(
        entrypoint="tests.fixtures.plugin_functions:emit_large_diagnostic",
        request={},
        timeout_seconds=30,
    )

    assert time.monotonic() - start < 10
    assert result.status.value == "ERROR"
    assert result.output is None
    assert result.detail == "plugin diagnostics exceed the configured limit"


@pytest.mark.integration
def test_plugin_timeout_kills_descendant_processes(tmp_path: Path) -> None:
    marker = tmp_path / "descendant-survived"

    result = PluginExecutor().run(
        entrypoint="tests.fixtures.plugin_functions:spawn_delayed_child",
        request={"marker": str(marker)},
        timeout_seconds=0.2,
    )
    time.sleep(1.2)

    assert result.status.value == "TIMEOUT"
    assert not marker.exists()


@pytest.mark.integration
def test_plugin_deadline_covers_descendant_held_output_pipes(tmp_path: Path) -> None:
    marker = tmp_path / "pipe-holder-survived"
    start = time.monotonic()

    result = PluginExecutor().run(
        entrypoint="tests.fixtures.plugin_functions:spawn_child_then_return",
        request={"marker": str(marker)},
        timeout_seconds=0.2,
    )
    elapsed = time.monotonic() - start
    time.sleep(1.2)

    assert elapsed < 1
    assert result.status.value == "TIMEOUT"
    assert result.output is None
    assert not marker.exists()
