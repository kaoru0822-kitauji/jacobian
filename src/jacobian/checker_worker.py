"""Minimal subprocess dispatcher for operator-authorized checker entrypoints."""

from __future__ import annotations

import contextlib
import importlib
import sys
from collections.abc import Callable
from typing import Any, cast

from jacobian.canonical import canonicalize_json, loads_strict_json
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


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: python -m jacobian.checker_worker module:function expected-digest",
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
        install_source_only_importer(sys.argv[1])
        with contextlib.redirect_stdout(sys.stderr):
            checker = _resolve(sys.argv[1])
            response = checker(request)
        measured_after = package_source_digest(sys.argv[1])
        if measured_after != measured_before:
            error_code = "SOURCE_CHANGED"
            raise ValueError("checker source changed during execution")
        sys.stdout.buffer.write(
            canonicalize_json(
                {
                    "decision": response,
                    "measured_checker_digest": measured_after,
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
