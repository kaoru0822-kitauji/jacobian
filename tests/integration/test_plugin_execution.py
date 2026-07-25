from __future__ import annotations

import os
import py_compile
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
    assert result.detail == (
        "The plugin changed after it was registered. "
        "Reload Jacobian to register the current plugin version, then retry."
    )


@pytest.mark.integration
def test_plugin_executor_does_not_expose_untrusted_exception_text() -> None:
    result = PluginExecutor().run(
        entrypoint="tests.fixtures.plugin_functions:propose_declared_failure",
        request={},
        timeout_seconds=30,
    )

    assert result.status.value == "ERROR"
    assert result.output is None
    assert result.detail == (
        "The plugin stopped before returning a result. Retry once; "
        "if it happens again, inspect the local plugin log."
    )
    assert "fixture" not in result.detail


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
    assert result.detail == (
        "The plugin did not finish within the allowed time. "
        "Retry with a larger time budget or a smaller request."
    )


@pytest.mark.integration
def test_plugin_unreadable_response_explains_recovery() -> None:
    result = PluginExecutor().run(
        entrypoint="tests.fixtures.plugin_functions:exit_without_response",
        request={},
        timeout_seconds=30,
    )

    assert result.status.value == "ERROR"
    assert result.output is None
    assert result.detail == (
        "The plugin returned an unreadable response. Retry once; "
        "if it happens again, inspect the local plugin log."
    )


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
    assert result.detail == (
        "The plugin produced too many diagnostics. Retry with a smaller request "
        "and inspect the local plugin log if the limit is reached again."
    )


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


@pytest.mark.integration
def test_plugin_success_still_kills_detached_descendants(tmp_path: Path) -> None:
    marker = tmp_path / "detached-descendant-survived"

    result = PluginExecutor().run(
        entrypoint=("tests.fixtures.plugin_functions:spawn_detached_child_then_return"),
        request={"marker": str(marker)},
        timeout_seconds=5,
    )
    time.sleep(1.2)

    assert result.status.value == "COMPLETED"
    assert not marker.exists()


@pytest.mark.integration
def test_plugin_worker_rejects_bytecode_modules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "bytecode_plugin"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "entry.py").write_text(
        "from .helper import VALUE\ndef run(_request):\n    return {'value': VALUE}\n",
        encoding="utf-8",
    )
    helper = package / "helper.py"
    helper.write_text("VALUE = 7\n", encoding="utf-8")
    py_compile.compile(
        str(helper),
        cfile=str(package / "helper.pyc"),
        doraise=True,
    )
    helper.unlink()
    monkeypatch.syspath_prepend(str(tmp_path))
    existing_path = os.environ.get("PYTHONPATH")
    monkeypatch.setenv(
        "PYTHONPATH",
        str(tmp_path) if not existing_path else f"{tmp_path}:{existing_path}",
    )

    result = PluginExecutor().run(
        entrypoint="bytecode_plugin.entry:run",
        request={},
        timeout_seconds=5,
    )

    assert result.status.value == "ERROR"
    assert result.detail == (
        "The plugin stopped before returning a result. Retry once; "
        "if it happens again, inspect the local plugin log."
    )
