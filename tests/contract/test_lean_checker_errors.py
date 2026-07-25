from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from jacobian_checkers.lean4 import (
    LEAN_TOOLCHAIN,
    _elan_home,
    _lean_command,
    _lean_rejection,
    _LeanSetupError,
    _run_lean,
    _validate_lean,
)


def test_lean_rejection_keeps_repair_context_without_local_details() -> None:
    detail = _lean_rejection(
        "/tmp/jacobian-lean-secret/Main.lean:7:12: error: unexpected token "
        "provider=hidden /private/toolchain/cache"
    )

    assert detail == (
        "Lean rejected the proof at line 7, column 12: unexpected token "
        "<local-path>. Correct the proof body and retry."
    )
    assert "jacobian-lean-secret" not in detail
    assert "provider=hidden" not in detail
    assert "/private" not in detail


def test_lean_rejection_has_a_generic_recovery_for_unknown_output() -> None:
    assert _lean_rejection("unstructured local compiler output") == (
        "Lean rejected the proof. Check the statement and proof body, then retry."
    )


@pytest.mark.parametrize(
    "diagnostic",
    [
        'Main.lean:7:12: error: failed at "/tmp/private path/file.lean"',
        "Main.lean:7:12: error: failed at /tmp/private path/file.lean",
        r"Main.lean:7:12: error: failed at C:\Users\Alice Smith\x.lean",
        r"Main.lean:7:12: error: failed at \\server\private\file.lean",
        "Main.lean:7:12: error: failed at ~/private/file.lean",
        "Main.lean:7:12: error: provider: secret unexpected token",
        "Main.lean:7:12: error: internal_id = secret unexpected token",
    ],
)
def test_lean_rejection_removes_independent_local_diagnostics(
    diagnostic: str,
) -> None:
    detail = _lean_rejection(diagnostic)

    assert "private" not in detail
    assert "secret" not in detail
    assert "provider" not in detail
    assert "internal_id" not in detail


def test_elan_command_selects_the_pinned_toolchain_without_a_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "jacobian_checkers.lean4.shutil.which",
        lambda name: "/opt/elan/bin/elan" if name == "elan" else None,
    )

    assert _lean_command("lean") == (
        "/opt/elan/bin/elan",
        "run",
        LEAN_TOOLCHAIN,
        "lean",
    )


def test_system_elan_uses_the_original_user_toolchain_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ELAN_HOME", raising=False)
    monkeypatch.setenv("HOME", "/home/jacobian")

    assert _elan_home(("/usr/bin/elan", "run", LEAN_TOOLCHAIN, "lean")) == (
        "/home/jacobian/.elan"
    )


def test_mathlib_validates_the_exact_lake_compiler_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validated: list[tuple[tuple[str, ...], Path | None]] = []
    monkeypatch.setattr(
        "jacobian_checkers.lean4._mathlib_runtime",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "jacobian_checkers.lean4._lean_command",
        lambda name: (f"/usr/bin/{name}",),
    )
    monkeypatch.setattr(
        "jacobian_checkers.lean4._validate_lean",
        lambda command, *, cwd=None: validated.append((command, cwd)),
    )
    monkeypatch.setattr(
        "jacobian_checkers.lean4.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    _run_lean("", environment_name="MATHLIB")

    assert validated == [(("/usr/bin/lake", "env", "lean"), tmp_path)]


def test_missing_pinned_toolchain_names_the_install_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*args: object, **kwargs: object) -> object:
        raise subprocess.CalledProcessError(1, ("elan", "run"))

    monkeypatch.setattr("jacobian_checkers.lean4.subprocess.run", unavailable)

    with pytest.raises(_LeanSetupError) as raised:
        _validate_lean(("/opt/elan/bin/elan", "run", LEAN_TOOLCHAIN, "lean"))

    assert str(raised.value) == (
        "The pinned Lean 4.31.0 toolchain is unavailable. Install it with "
        "`elan toolchain install leanprover/lean4:v4.31.0`, then retry."
    )
