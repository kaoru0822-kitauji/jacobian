"""Minimal subprocess dispatcher for operator-authorized checker entrypoints."""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.contracts.capabilities import (
    CapabilityProviderAvailability,
    CapabilityProviderDigestKind,
    CapabilityProviderRuntime,
)
from jacobian.implementation import (
    install_source_only_importer,
    package_source_digest,
)


def _resolve(entrypoint: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    module_name, separator, function_name = entrypoint.partition(":")
    if not separator:
        raise ValueError("checker entrypoint must be module:function")
    module = importlib.import_module(module_name)
    function = getattr(module, function_name)
    if not callable(function):
        raise TypeError("checker entrypoint is not callable")
    return cast(Callable[[dict[str, Any]], dict[str, Any]], function)


def _measure_runtime(
    encoded: str | None,
) -> tuple[CapabilityProviderRuntime | None, str | None]:
    os.environ.pop("JACOBIAN_CHECKER_EXECUTABLE", None)
    os.environ.pop("JACOBIAN_CHECKER_RUNTIME_DIGEST", None)
    if encoded is None:
        return None, None
    runtime = CapabilityProviderRuntime.model_validate(loads_strict_json(encoded))
    executable = runtime.configuration.get("executable")
    if (
        runtime.availability is not CapabilityProviderAvailability.AVAILABLE
        or runtime.digest_kind is not CapabilityProviderDigestKind.EXECUTABLE
        or runtime.digest is None
        or not isinstance(executable, str)
    ):
        raise ValueError("checker runtime identity is incomplete")
    path = Path(executable).resolve(strict=True)
    if str(path) != executable:
        raise ValueError("checker runtime path is not exact")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    measured = "sha256:" + digest.hexdigest()
    if measured != runtime.digest:
        raise ValueError("checker runtime differs from its authorized digest")
    os.environ["JACOBIAN_CHECKER_EXECUTABLE"] = str(path)
    os.environ["JACOBIAN_CHECKER_RUNTIME_DIGEST"] = measured
    return runtime, measured


def main() -> int:
    if len(sys.argv) not in {3, 4}:
        print(
            "usage: python -m jacobian.checker_worker "
            "module:function expected-digest [provider-runtime-json]",
            file=sys.stderr,
        )
        return 2
    error_code = "EXECUTION_FAILED"
    try:
        request = loads_strict_json(sys.stdin.buffer.read())
        measured_before = package_source_digest(sys.argv[1])
        if measured_before != sys.argv[2]:
            error_code = "SOURCE_CHANGED"
            raise ValueError("checker source differs from its authorized digest")
        runtime, runtime_digest_before = _measure_runtime(
            sys.argv[3] if len(sys.argv) == 4 else None
        )
        install_source_only_importer(sys.argv[1])
        with contextlib.redirect_stdout(sys.stderr):
            checker = _resolve(sys.argv[1])
            response = checker(request)
        measured_after = package_source_digest(sys.argv[1])
        if measured_after != measured_before:
            error_code = "SOURCE_CHANGED"
            raise ValueError("checker source changed during execution")
        _, runtime_digest_after = _measure_runtime(
            canonicalize_json(runtime.model_dump(mode="json")).decode("utf-8")
            if runtime is not None
            else None
        )
        if runtime_digest_after != runtime_digest_before:
            error_code = "SOURCE_CHANGED"
            raise ValueError("checker runtime changed during execution")
        sys.stdout.buffer.write(
            canonicalize_json(
                {
                    "decision": response,
                    "measured_checker_digest": measured_after,
                    "measured_runtime_digest": runtime_digest_after,
                }
            )
        )
        sys.stdout.buffer.write(b"\n")
        return 0
    except Exception as exc:  # checker isolation turns all failures into ERROR
        error = {
            "error": type(exc).__name__,
            "error_code": error_code,
            "detail": str(exc),
        }
        sys.stdout.buffer.write(canonicalize_json(error))
        sys.stdout.buffer.write(b"\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
