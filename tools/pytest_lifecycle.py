"""Run pytest with a unique worktree-local temporary tree."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.tooling.command_runner import (  # noqa: E402
    ToolCommandRequest,
    ToolCommandStatus,
    run_tool_command,
)

BASETEMP_ROOT = ROOT / ".pytest_cache" / "basetemp"
_OUTPUT_LIMIT = 16 * 1024 * 1024
_SAFE_LABEL = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(frozen=True, slots=True)
class PytestResult:
    """Normalized outcome and lifecycle evidence for one pytest process."""

    exit_code: int
    status: str
    actual_seconds: float
    basetemp: Path
    retained: bool


def _has_basetemp(arguments: Sequence[str]) -> bool:
    return any(
        argument == "--basetemp" or argument.startswith("--basetemp=")
        for argument in arguments
    )


def _unique_basetemp(root: Path, name: str) -> Path:
    label = _SAFE_LABEL.sub("-", name).strip("-") or "pytest"
    run_root = root / ".pytest_cache" / "basetemp" / f"{label}-{uuid.uuid4().hex}"
    return run_root / "pytest"


def _stream_stdout(block: bytes) -> None:
    sys.stdout.buffer.write(block)
    sys.stdout.buffer.flush()


def _stream_stderr(block: bytes) -> None:
    sys.stderr.buffer.write(block)
    sys.stderr.buffer.flush()


def _emit_lifecycle_event(event: str, **fields: object) -> None:
    payload = {"event": event, **fields}
    print(
        f"[pytest-lifecycle] {json.dumps(payload, sort_keys=True)}",
        file=sys.stderr,
        flush=True,
    )


def _write_receipt(
    path: Path,
    *,
    name: str,
    predicted_seconds: float,
    result: PytestResult,
) -> None:
    payload = {
        "schema_version": 1,
        "name": name,
        "predicted_seconds": round(predicted_seconds, 6),
        "actual_seconds": round(result.actual_seconds, 6),
        "status": result.status,
        "exit_code": result.exit_code,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def run_pytest(
    arguments: Sequence[str],
    *,
    root: Path,
    name: str,
    environment: Mapping[str, str],
    timeout_seconds: float = 3600.0,
    retain_on_failure: bool = False,
    receipt: Path | None = None,
    predicted_seconds: float = 1.0,
) -> PytestResult:
    """Execute pytest and clean its unique temp tree unless retention is requested."""
    if _has_basetemp(arguments):
        raise ValueError("pytest basetemp is owned by tools.pytest_lifecycle")
    if predicted_seconds <= 0:
        raise ValueError("predicted_seconds must be positive")

    basetemp = _unique_basetemp(root.resolve(), name)
    basetemp.mkdir(parents=True)
    run_root = basetemp.parent
    result: PytestResult | None = None
    try:
        _emit_lifecycle_event(
            "pytest.run.started",
            name=name,
            predicted_seconds=predicted_seconds,
            timeout_seconds=timeout_seconds,
        )
        started = time.monotonic()
        tool_result = run_tool_command(
            ToolCommandRequest(
                executable=sys.executable,
                arguments=("-m", "pytest", *arguments, f"--basetemp={basetemp}"),
                environment=environment,
                cwd=str(root.resolve()),
                timeout_seconds=timeout_seconds,
                stdout_limit_bytes=_OUTPUT_LIMIT,
                stderr_limit_bytes=_OUTPUT_LIMIT,
                stdout_sink=_stream_stdout,
                stderr_sink=_stream_stderr,
            )
        )
        elapsed = time.monotonic() - started
        exited = tool_result.status is ToolCommandStatus.EXITED
        exit_code = (
            int(tool_result.exit_code)
            if exited and tool_result.exit_code is not None
            else 1
        )
        if not exited:
            diagnostic = tool_result.diagnostic or tool_result.status.value
            print(f"[{name}] {diagnostic}", file=sys.stderr)
        retained = bool(exit_code and retain_on_failure)
        result = PytestResult(
            exit_code=exit_code,
            status=tool_result.status.value,
            actual_seconds=elapsed,
            basetemp=basetemp,
            retained=retained,
        )
        _emit_lifecycle_event(
            "pytest.run.completed",
            name=name,
            status=result.status,
            exit_code=result.exit_code,
            actual_seconds=round(result.actual_seconds, 6),
        )
        if receipt is not None:
            _write_receipt(
                receipt,
                name=name,
                predicted_seconds=predicted_seconds,
                result=result,
            )
    finally:
        if result is not None and result.retained:
            print(f"[{name}] retained failed pytest tree: {run_root}", file=sys.stderr)
        else:
            shutil.rmtree(run_root, ignore_errors=True)
    assert result is not None
    return result


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default=os.environ.get("PYTEST_RUN_NAME", "pytest"))
    parser.add_argument(
        "--receipt",
        type=Path,
        default=(Path(value) if (value := os.environ.get("PYTEST_RECEIPT")) else None),
    )
    parser.add_argument(
        "--predicted-seconds",
        type=_positive_float,
        default=_positive_float(os.environ.get("PYTEST_PREDICTED_SECONDS", "1")),
    )
    parser.add_argument(
        "--retain-on-failure",
        action="store_true",
        default=os.environ.get("PYTEST_RETAIN_ON_FAILURE") == "1",
    )
    parser.add_argument("--timeout-seconds", type=_positive_float, default=3600.0)
    parser.add_argument("pytest_arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    arguments = args.pytest_arguments
    if arguments[:1] == ["--"]:
        arguments = arguments[1:]
    if not arguments:
        parser.error("pytest arguments are required after --")
    try:
        result = run_pytest(
            arguments,
            root=ROOT,
            name=args.name,
            environment=dict(os.environ),
            timeout_seconds=args.timeout_seconds,
            retain_on_failure=args.retain_on_failure,
            receipt=args.receipt,
            predicted_seconds=args.predicted_seconds,
        )
    except ValueError as exc:
        parser.error(str(exc))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["PytestResult", "main", "run_pytest"]
