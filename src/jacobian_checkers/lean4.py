"""Independent checker for pinned core and mathlib Lean certificates."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

LEAN_VERSION = "4.31.0"
LEAN_COMMIT = "68218e876d2a38b1985b8590fff244a83c321783"
MATHLIB_COMMIT = "fabf563a7c95a166b8d7b6efca11c8b4dc9d911f"
MATHLIB_AXIOMS = frozenset({"Classical.choice", "Quot.sound", "propext"})
_FORBIDDEN = re.compile(
    r"\b(?:admit|axiom|elab|import|macro|native_decide|opaque|run_tac|"
    r"set_option|sorry|syntax|unsafe)\b|#",
    re.IGNORECASE,
)
_AXIOMS = re.compile(r"'jacobian_theorem' depends on axioms: \[([^\]]*)\]")


def _reject(detail: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "conclusion": "UNKNOWN",
        "arithmetic": "SYMBOLIC",
        "method": "CHECKED_CERTIFICATE",
        "coverage": "NOT_APPLICABLE",
        "detail": detail,
    }


def _text(value: object, *, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if len(value) > limit or "\x00" in value:
        raise ValueError(f"{name} exceeds its accepted source boundary")
    if _FORBIDDEN.search(value):
        raise ValueError(f"{name} contains a forbidden Lean command")
    return value


def _source(statement: str, proof: str, import_name: str | None) -> str:
    if "\n" in statement or "\r" in statement or ":=" in statement:
        raise ValueError("statement must be one Lean expression")
    if proof.strip().splitlines()[0].strip() == "by":
        raise ValueError("proof must omit the leading `by`")
    indented_proof = "\n".join(f"  {line}" for line in proof.splitlines())
    lines = [
        *([f"import {import_name}"] if import_name is not None else []),
        *(
            (
                "set_option autoImplicit false",
                "set_option warningAsError true",
                f"theorem jacobian_theorem : {statement} := by",
                indented_proof,
                "#print axioms jacobian_theorem",
                "",
            )
        ),
    ]
    return "\n".join(lines)


def _elan_executable(name: str) -> str:
    launcher = shutil.which(name)
    if launcher is None:
        raise RuntimeError(f"the pinned {name} executable is unavailable")
    elan = shutil.which("elan")
    if elan is None:
        return launcher
    executable = subprocess.run(
        [elan, "which", name],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    ).stdout.strip()
    if not Path(executable).is_file():
        raise RuntimeError(f"elan returned an invalid {name} executable")
    return executable


def _validate_lean(executable: str) -> None:
    if (
        subprocess.run(
            [executable, "-V"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        != LEAN_VERSION
    ):
        raise RuntimeError("the installed Lean version is not authorized")
    if (
        subprocess.run(
            [executable, "-g"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        != LEAN_COMMIT
    ):
        raise RuntimeError("the installed Lean commit is not authorized")


def _validate_package_checkout(
    packages_directory: Path,
    package: dict[str, Any],
) -> None:
    name = package.get("name")
    revision = package.get("rev")
    if (
        package.get("type") != "git"
        or not isinstance(name, str)
        or not name
        or Path(name).name != name
        or not isinstance(revision, str)
        or re.fullmatch(r"[0-9a-f]{40}", revision) is None
    ):
        raise RuntimeError("the mathlib manifest contains an invalid package")
    checkout = packages_directory / name
    actual_revision = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    ).stdout.strip()
    if actual_revision != revision:
        raise RuntimeError(f"the installed {name} commit is not authorized")
    tracked_changes = subprocess.run(
        [
            "git",
            "-C",
            str(checkout),
            "status",
            "--porcelain",
            "--untracked-files=no",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    ).stdout.strip()
    if tracked_changes:
        raise RuntimeError(f"the installed {name} source has tracked modifications")


def _mathlib_runtime() -> Path:
    configured = os.environ.get("JACOBIAN_LEAN_RUNTIME")
    runtime = (
        Path(configured)
        if configured is not None
        else Path(__file__).resolve().parents[2] / "lean"
    )
    manifest_path = runtime / "lake-manifest.json"
    toolchain_path = runtime / "lean-toolchain"
    if not manifest_path.is_file() or not toolchain_path.is_file():
        raise RuntimeError("the pinned mathlib runtime is unavailable")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packages = manifest.get("packages")
    if manifest.get("packagesDir") != ".lake/packages" or not isinstance(
        packages, list
    ):
        raise RuntimeError("the mathlib manifest is malformed")
    revisions = {
        package.get("name"): package.get("rev")
        for package in packages
        if isinstance(package, dict)
    }
    if revisions.get("mathlib") != MATHLIB_COMMIT:
        raise RuntimeError("the installed mathlib commit is not authorized")
    packages_directory = runtime / ".lake" / "packages"
    for package in packages:
        if not isinstance(package, dict):
            raise RuntimeError("the mathlib manifest contains an invalid package")
        _validate_package_checkout(packages_directory, package)
    if (
        toolchain_path.read_text(encoding="utf-8").strip()
        != f"leanprover/lean4:v{LEAN_VERSION}"
    ):
        raise RuntimeError("the mathlib runtime requests another Lean toolchain")
    return runtime


def _run_lean(
    source: str,
    *,
    environment_name: str,
) -> subprocess.CompletedProcess[str]:
    executable = _elan_executable("lean")
    _validate_lean(executable)
    if environment_name == "CORE":
        command = [executable]
        memory_mb = "1024"
        timeout_seconds = 25
        cwd_context = tempfile.TemporaryDirectory(prefix="jacobian-lean-")
        cwd = Path(cwd_context.name)
        process_environment = {
            "HOME": cwd_context.name,
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": str(Path(executable).parent),
        }
    elif environment_name == "MATHLIB":
        runtime = _mathlib_runtime()
        lake = _elan_executable("lake")
        command = [lake, "env", "lean"]
        memory_mb = "8192"
        timeout_seconds = 90
        cwd_context = tempfile.TemporaryDirectory(prefix="jacobian-lean-home-")
        cwd = runtime
        process_environment = {
            "HOME": os.environ.get("HOME", cwd_context.name),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": os.environ.get("PATH", str(Path(executable).parent)),
        }
    else:
        raise ValueError("unknown Lean environment")
    with cwd_context:
        return subprocess.run(
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


def _reported_axioms(diagnostics: str) -> frozenset[str]:
    if "'jacobian_theorem' does not depend on any axioms" in diagnostics:
        return frozenset()
    match = _AXIOMS.search(diagnostics)
    if match is None:
        raise ValueError("Lean did not report the theorem trust base")
    return frozenset(item.strip() for item in match.group(1).split(",") if item.strip())


def _profile(
    environment_name: object,
) -> tuple[str | None, str | None, frozenset[str]]:
    if environment_name == "CORE":
        return None, None, frozenset()
    if environment_name == "MATHLIB":
        return "Mathlib", MATHLIB_COMMIT, MATHLIB_AXIOMS
    raise ValueError("unknown Lean environment")


def check_kernel_certificate(request: dict[str, Any]) -> dict[str, Any]:
    """Compile the exact bound proposition under its authorized trust profile."""

    try:
        if request.get("request_version") != "1":
            return _reject("unsupported request version")
        certificate = request["certificate"]["payload"]
        if certificate.get("certificate_type") != "lean4.kernel":
            return _reject("unexpected certificate format")
        if certificate.get("format_version") != "1":
            return _reject("unsupported certificate format version")
        if certificate.get("bindings") != request["expected_bindings"]:
            return _reject("certificate bindings do not match the request")
        payload = certificate["payload"]
        claim = request["claim"]["payload"]
        candidate = request["candidate"]["payload"]
        environment_name = payload.get("environment")
        import_name, mathlib_commit, allowed_axioms = _profile(environment_name)
        statement = _text(payload.get("statement"), name="statement", limit=2_000)
        proof = _text(payload.get("proof"), name="proof", limit=20_000)
        if (
            claim.get("statement") != statement
            or candidate.get("statement") != statement
            or candidate.get("proof") != proof
        ):
            return _reject("claim, candidate, and certificate source differ")
        if (
            claim.get("environment") != environment_name
            or candidate.get("environment") != environment_name
        ):
            return _reject("claim, candidate, and certificate profiles differ")
        expected_axioms = sorted(allowed_axioms)
        if (
            sorted(claim.get("allowed_axioms", [])) != expected_axioms
            or sorted(payload.get("allowed_axioms", [])) != expected_axioms
        ):
            return _reject("certificate requests an unauthorized Lean trust base")
        if payload.get("declaration_name") != "jacobian_theorem":
            return _reject("unexpected Lean declaration name")
        if (
            payload.get("lean_version") != LEAN_VERSION
            or payload.get("lean_commit") != LEAN_COMMIT
            or payload.get("import_name") != import_name
            or payload.get("mathlib_commit") != mathlib_commit
        ):
            return _reject("certificate requests another Lean runtime")
        completed = _run_lean(
            _source(statement, proof, import_name),
            environment_name=environment_name,
        )
        diagnostics = (completed.stdout + completed.stderr).strip()
        if completed.returncode != 0:
            return _reject("Lean rejected the proof: " + diagnostics[:2_000])
        reported_axioms = _reported_axioms(diagnostics)
        if not reported_axioms.issubset(allowed_axioms):
            return _reject("Lean proof has an unapproved trust base")
        trust_base = (
            ", ".join(sorted(reported_axioms)) if reported_axioms else "no axioms"
        )
        return {
            "accepted": True,
            "conclusion": "TRUE",
            "arithmetic": "SYMBOLIC",
            "method": "CHECKED_CERTIFICATE",
            "coverage": "NOT_APPLICABLE",
            "detail": (
                f"Lean {LEAN_VERSION} kernel accepted the exact proposition "
                f"under {environment_name} with {trust_base}"
            ),
        }
    except (
        KeyError,
        OSError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ) as exc:
        return _reject(str(exc))
