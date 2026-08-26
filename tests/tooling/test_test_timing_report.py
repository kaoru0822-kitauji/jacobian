"""Behavioral coverage for the JUnit and worker timing report."""

from __future__ import annotations

import importlib.util
import sys
from io import StringIO
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).parents[2]


def _load() -> ModuleType:
    path = ROOT / "tools" / "test_timing_report.py"
    spec = importlib.util.spec_from_file_location("test_timing_report", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_report_orders_slowest_cases_and_exposes_worker_skew(tmp_path: Path) -> None:
    reporter = _load()
    junit = tmp_path / "pytest.xml"
    junit.write_text(
        """<?xml version=\"1.0\"?>
<testsuites><testsuite><testcase classname=\"math.graphs\" name=\"fast\" time=\"0.2\" />
<testcase classname=\"math.graphs\" name=\"slow\" time=\"1.5\" /></testsuite></testsuites>
""",
        encoding="utf-8",
    )
    timing = tmp_path / "timing.json"
    timing.write_text(
        """{"version": 1, "wall_seconds": 3.0, "workers": [
{"id": "gw0", "call_seconds": 1.0, "call_count": 1},
{"id": "gw1", "call_seconds": 2.0, "call_count": 1}]}""",
        encoding="utf-8",
    )

    summary = reporter.build_summary(junit=junit, timing=timing, limit=10)
    output = StringIO()
    reporter.write_summary(summary, stream=output)

    assert summary.test_count == 2
    assert summary.slowest[0].node_id == "math.graphs::slow"
    assert "call-time skew 2.00x" in output.getvalue()
    assert "Non-call wall remainder: 1.000s" in output.getvalue()


def test_junit_only_report_marks_worker_distribution_unavailable(
    tmp_path: Path,
) -> None:
    reporter = _load()
    junit = tmp_path / "pytest.xml"
    junit.write_text(
        '<testsuites><testsuite><testcase name="only" time="0.1" />'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )

    summary = reporter.build_summary(junit=junit, timing=None, limit=10)
    output = StringIO()
    reporter.write_summary(summary, stream=output)

    assert "Worker timing: unavailable" in output.getvalue()
