"""Resolve the Linux Codex executable that Harbor mounts into task containers."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

_ELF_MAGIC = b"\x7fELF"
_CODE_MODE_HOST = "codex-code-mode-host"


def _is_linux_executable(path: Path) -> bool:
    if not path.is_file() or not os.access(path, os.X_OK):
        return False
    try:
        with path.open("rb") as stream:
            return stream.read(len(_ELF_MAGIC)) == _ELF_MAGIC
    except OSError:
        return False


def _npm_payload_candidates(launcher: Path) -> tuple[Path, ...]:
    if launcher.name != "codex.js" or launcher.parent.name != "bin":
        return ()
    package = launcher.parent.parent
    roots = (package / "node_modules" / "@openai", package.parent)
    matches = {
        path.resolve()
        for root in roots
        for path in root.glob("codex-linux-*/vendor/*/bin/codex")
        if _is_linux_executable(path)
    }
    return tuple(sorted(matches))


def resolve_codex_binary(candidate: Path) -> Path:
    """Resolve a native Linux Codex binary from a binary or npm launcher path."""
    try:
        resolved = candidate.expanduser().resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"Codex executable does not exist: {candidate}") from exc
    if not os.access(resolved, os.X_OK):
        raise ValueError(f"Codex executable is not executable: {resolved}")
    if _is_linux_executable(resolved):
        return resolved

    payloads = _npm_payload_candidates(resolved)
    if len(payloads) == 1:
        return payloads[0]
    if len(payloads) > 1:
        rendered = ", ".join(str(path) for path in payloads)
        raise ValueError(
            "multiple Linux standalone Codex binaries found; set "
            f"JACOBIAN_EVAL_CODEX_BINARY explicitly: {rendered}"
        )
    raise ValueError(
        "JACOBIAN_EVAL_CODEX_BINARY must resolve to a Linux standalone Codex "
        f"binary; no native npm payload was found for {resolved}"
    )


def resolve_codex_code_mode_host(candidate: Path) -> Path:
    """Resolve the Code Mode host packaged beside a standalone Codex binary."""
    binary = resolve_codex_binary(candidate)
    host = binary.with_name(_CODE_MODE_HOST)
    if _is_linux_executable(host):
        return host
    raise ValueError(
        "Codex standalone runtime is incomplete; expected executable Code Mode "
        f"host beside {binary}: {host}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--code-mode-host", action="store_true")
    args = parser.parse_args()
    try:
        resolved = (
            resolve_codex_code_mode_host(args.candidate)
            if args.code_mode_host
            else resolve_codex_binary(args.candidate)
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(resolved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
