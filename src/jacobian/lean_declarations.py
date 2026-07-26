"""Read-only declaration discovery over pinned Lean environments."""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.contracts.capabilities import CapabilityProviderRuntime
from jacobian.contracts.lean import (
    LeanDeclarationInspectOutput,
    LeanDeclarationInspectRequest,
    LeanDeclarationRecord,
    LeanDeclarationSearchOutput,
    LeanDeclarationSearchRequest,
    LeanDeclarationSearchStopReason,
    LeanEnvironment,
)

_LOGGER = logging.getLogger(__name__)
_RESULT_PREFIX = "JACOBIAN_DECLARATION_RESULT "
_MAX_STDOUT_BYTES = 2 * 1024 * 1024
_MAX_STDERR_BYTES = 128 * 1024
_QUERY_SOURCE = Path(__file__).with_name("_lean_declaration_query.lean")
_IMPORT_TOKEN = "{{JACOBIAN_IMPORT}}"


class LeanDeclarationBackend(Protocol):
    """The process boundary needed by typed declaration discovery."""

    def environment_digest(self, environment: LeanEnvironment) -> str: ...

    def query(
        self,
        environment: LeanEnvironment,
        payload: dict[str, Any],
    ) -> dict[str, Any]: ...


class LeanDeclarationBackendError(RuntimeError):
    """A bounded backend failure safe for capability diagnostic mapping."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class LeanSubprocessDeclarationBackend:
    """Execute one generated read-only query in a validated Lean installation."""

    def __init__(
        self,
        *,
        lean_executable: Path,
        mathlib_runtime: Path | None,
        provider_runtime: CapabilityProviderRuntime,
    ) -> None:
        self.lean_executable = lean_executable
        self.mathlib_runtime = mathlib_runtime
        self.provider_runtime = provider_runtime
        self._source_template = _QUERY_SOURCE.read_text(encoding="utf-8")
        if self._source_template.count(_IMPORT_TOKEN) != 1:
            raise RuntimeError(
                "Lean declaration query source has an invalid import token"
            )

    def environment_digest(self, environment: LeanEnvironment) -> str:
        try:
            if _sha256_file(self.lean_executable) != self.provider_runtime.digest:
                raise LeanDeclarationBackendError(
                    "LEAN_ENVIRONMENT_CHANGED",
                    "The pinned Lean executable changed after capability registration.",
                )
            return self._compute_environment_digest(environment)
        except OSError as exc:
            raise LeanDeclarationBackendError(
                "LEAN_ENVIRONMENT_UNAVAILABLE",
                f"The pinned Lean {environment.value} environment is not installed.",
            ) from exc

    def query(
        self,
        environment: LeanEnvironment,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        environment_digest = self.environment_digest(environment)
        import_name = (
            "Init.Prelude" if environment is LeanEnvironment.CORE else "Mathlib"
        )
        source = self._source_template.replace(_IMPORT_TOKEN, import_name)
        with tempfile.TemporaryDirectory(prefix="jacobian-lean-query-") as directory:
            temporary_root = Path(directory)
            query_path = temporary_root / "query.json"
            query_path.write_bytes(canonicalize_json(payload))
            command, cwd, memory_mb, timeout_seconds = self._command(
                environment,
                temporary_root,
            )
            process_environment = self._process_environment(
                environment,
                temporary_root,
                query_path,
            )
            try:
                completed = subprocess.run(
                    [
                        *command,
                        "--stdin",
                        "-t",
                        "0",
                        "-T",
                        "1000000000",
                        "-M",
                        memory_mb,
                        "-j",
                        "1",
                        "--trust=0",
                    ],
                    cwd=cwd,
                    env=process_environment,
                    input=source,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise LeanDeclarationBackendError(
                    "LEAN_QUERY_TIMEOUT",
                    (
                        f"Lean declaration discovery exceeded the "
                        f"{timeout_seconds}-second {environment.value} budget."
                    ),
                ) from exc
        if len(completed.stdout.encode("utf-8")) > _MAX_STDOUT_BYTES:
            raise LeanDeclarationBackendError(
                "LEAN_QUERY_OUTPUT_LIMIT",
                "Lean declaration discovery exceeded its structured output budget.",
            )
        if len(completed.stderr.encode("utf-8")) > _MAX_STDERR_BYTES:
            raise LeanDeclarationBackendError(
                "LEAN_QUERY_OUTPUT_LIMIT",
                "Lean declaration discovery exceeded its diagnostic output budget.",
            )
        if completed.returncode != 0:
            _LOGGER.warning(
                "Lean declaration query failed: %s",
                (completed.stdout + completed.stderr).strip(),
            )
            if "declaration not found:" in completed.stderr:
                name = str(payload.get("declaration_name", "the requested name"))
                raise LeanDeclarationBackendError(
                    "LEAN_DECLARATION_NOT_FOUND",
                    f"Lean did not find the exact declaration {name!r}.",
                )
            raise LeanDeclarationBackendError(
                "LEAN_QUERY_FAILED",
                (
                    f"Lean could not complete declaration discovery in the "
                    f"{environment.value} environment."
                ),
            )
        output = _parse_query_output(completed.stdout)
        if self.environment_digest(environment) != environment_digest:
            raise LeanDeclarationBackendError(
                "LEAN_ENVIRONMENT_CHANGED",
                "The pinned Lean environment changed during declaration discovery.",
            )
        output["_environment_digest"] = environment_digest
        return output

    def _command(
        self,
        environment: LeanEnvironment,
        temporary_root: Path,
    ) -> tuple[list[str], Path, str, int]:
        if environment is LeanEnvironment.CORE:
            return [str(self.lean_executable)], temporary_root, "1024", 40
        if self.mathlib_runtime is None:
            raise LeanDeclarationBackendError(
                "LEAN_ENVIRONMENT_UNAVAILABLE",
                "The pinned Lean MATHLIB environment is not installed.",
            )
        lake = self.lean_executable.with_name(
            "lake.exe" if self.lean_executable.suffix.lower() == ".exe" else "lake"
        )
        if not lake.is_file():
            raise LeanDeclarationBackendError(
                "LEAN_ENVIRONMENT_UNAVAILABLE",
                "The pinned Lake executable for MATHLIB discovery is unavailable.",
            )
        return [str(lake), "env", "lean"], self.mathlib_runtime, "8192", 75

    def _process_environment(
        self,
        environment: LeanEnvironment,
        temporary_root: Path,
        query_path: Path,
    ) -> dict[str, str]:
        lean_bin = str(self.lean_executable.parent)
        existing_path = os.environ.get("PATH")
        path = (
            f"{lean_bin}{os.pathsep}{existing_path}"
            if existing_path is not None
            else lean_bin
        )
        runtime_home = (
            os.environ.get("HOME", str(temporary_root))
            if environment is LeanEnvironment.MATHLIB
            else str(temporary_root)
        )
        return {
            "HOME": runtime_home,
            "JACOBIAN_LEAN_QUERY_FILE": str(query_path),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": path,
        }

    def _compute_environment_digest(self, environment: LeanEnvironment) -> str:
        identity: dict[str, Any] = {
            "contract": "jacobian.lean.environment-manifest/v1",
            "environment": environment.value,
            "import_name": (
                "Init.Prelude" if environment is LeanEnvironment.CORE else "Mathlib"
            ),
            "lean_version": self.provider_runtime.version,
            "platform": self.provider_runtime.platform,
            "provider_digest": self.provider_runtime.digest,
        }
        if environment is LeanEnvironment.MATHLIB:
            if self.mathlib_runtime is None:
                raise RuntimeError("cannot identify an unavailable Mathlib environment")
            profile = self.provider_runtime.configuration.get("profiles", {}).get(
                LeanEnvironment.MATHLIB.value,
                {},
            )
            identity.update(
                {
                    "lake_manifest_digest": _sha256_file(
                        self.mathlib_runtime / "lake-manifest.json"
                    ),
                    "lean_toolchain_digest": _sha256_file(
                        self.mathlib_runtime / "lean-toolchain"
                    ),
                    "mathlib_commit": profile.get("mathlib_commit"),
                }
            )
        return "sha256:" + hashlib.sha256(canonicalize_json(identity)).hexdigest()


class LeanDeclarationService:
    """Validate backend JSON into stable typed discovery results."""

    def __init__(self, backend: LeanDeclarationBackend) -> None:
        self.backend = backend

    def search(
        self,
        query: LeanDeclarationSearchRequest,
    ) -> LeanDeclarationSearchOutput:
        type_constants = (
            list(query.type_pattern.constants) if query.type_pattern is not None else []
        )
        raw = self.backend.query(
            query.environment,
            {
                "operation": "search",
                "declaration_name": None,
                "name_contains": query.name_contains,
                "type_constants": type_constants,
                "namespace_prefixes": list(query.namespace_prefixes),
                "target_module_prefixes": (
                    ["Init"] if query.environment is LeanEnvironment.CORE else []
                ),
                "kinds": [kind.value for kind in query.kinds],
                "limit": query.result_limit,
            },
        )
        _require_operation(raw, "search")
        environment_digest = (
            raw["_environment_digest"]
            if "_environment_digest" in raw
            else self.backend.environment_digest(query.environment)
        )
        try:
            return LeanDeclarationSearchOutput(
                environment=query.environment,
                environment_digest=environment_digest,
                query=query,
                declarations=tuple(
                    LeanDeclarationRecord.model_validate(item)
                    for item in raw["declarations"]
                ),
                scanned_declarations=raw["scanned_declarations"],
                stop_reason=LeanDeclarationSearchStopReason(raw["stop_reason"]),
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise _protocol_error() from exc

    def inspect(
        self,
        query: LeanDeclarationInspectRequest,
    ) -> LeanDeclarationInspectOutput:
        raw = self.backend.query(
            query.environment,
            {
                "operation": "inspect",
                "declaration_name": query.declaration_name,
                "name_contains": None,
                "type_constants": [],
                "namespace_prefixes": [],
                "target_module_prefixes": (
                    ["Init"] if query.environment is LeanEnvironment.CORE else []
                ),
                "kinds": [],
                "limit": 1,
            },
        )
        _require_operation(raw, "inspect")
        environment_digest = (
            raw["_environment_digest"]
            if "_environment_digest" in raw
            else self.backend.environment_digest(query.environment)
        )
        try:
            return LeanDeclarationInspectOutput(
                environment=query.environment,
                environment_digest=environment_digest,
                query=query,
                declaration=LeanDeclarationRecord.model_validate(raw["declaration"]),
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise _protocol_error() from exc


def installed_lean_declaration_service(
    provider_runtime: CapabilityProviderRuntime,
) -> LeanDeclarationService:
    """Bind discovery to the same separately validated pinned runtime identity."""

    from jacobian_checkers import lean4

    lean_executable, mathlib_runtime = lean4.inspect_runtime(require_mathlib=True)
    return LeanDeclarationService(
        LeanSubprocessDeclarationBackend(
            lean_executable=lean_executable,
            mathlib_runtime=mathlib_runtime,
            provider_runtime=provider_runtime,
        )
    )


def _parse_query_output(stdout: str) -> dict[str, Any]:
    payloads = [
        line.removeprefix(_RESULT_PREFIX)
        for line in stdout.splitlines()
        if line.startswith(_RESULT_PREFIX)
    ]
    if len(payloads) != 1:
        raise _protocol_error()
    try:
        payload = loads_strict_json(payloads[0])
    except ValueError as exc:
        raise _protocol_error() from exc
    if not isinstance(payload, dict):
        raise _protocol_error()
    return payload


def _require_operation(payload: dict[str, Any], expected: str) -> None:
    if payload.get("operation") != expected:
        raise _protocol_error()


def _protocol_error() -> LeanDeclarationBackendError:
    return LeanDeclarationBackendError(
        "LEAN_QUERY_PROTOCOL_ERROR",
        "Lean declaration discovery returned malformed structured output.",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()
