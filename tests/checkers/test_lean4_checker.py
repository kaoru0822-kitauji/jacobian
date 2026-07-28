from __future__ import annotations

import subprocess
from copy import deepcopy
from typing import Any

import pytest

from jacobian_checkers.lean4 import (
    LEAN_COMMIT,
    LEAN_VERSION,
    check_kernel_certificate,
)


def _request() -> dict[str, Any]:
    bindings = {
        "claim_digest": "sha256:" + "a" * 64,
        "semantics_digest": "sha256:" + "b" * 64,
        "candidate_digest": "sha256:" + "c" * 64,
        "scope_digest": None,
        "encoding_digest": None,
    }
    statement = "True"
    proof = "by trivial"
    return {
        "request_version": "1",
        "claim": {
            "payload": {
                "statement": statement,
                "environment": "CORE",
                "allowed_axioms": [],
            }
        },
        "candidate": {
            "payload": {
                "statement": statement,
                "proof": proof,
                "environment": "CORE",
            }
        },
        "certificate": {
            "payload": {
                "certificate_type": "lean4.kernel",
                "format_version": "1",
                "bindings": deepcopy(bindings),
                "payload": {
                    "statement": statement,
                    "proof": proof,
                    "environment": "CORE",
                    "allowed_axioms": [],
                    "declaration_name": "jacobian_theorem",
                    "lean_version": LEAN_VERSION,
                    "lean_commit": LEAN_COMMIT,
                    "import_name": None,
                    "mathlib_commit": None,
                },
            }
        },
        "expected_bindings": bindings,
    }


def test_lean_checker_accepts_exact_bound_core_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "jacobian_checkers.lean4._run_lean",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=("lean",),
            returncode=0,
            stdout="'jacobian_theorem' does not depend on any axioms",
            stderr="",
        ),
    )

    decision = check_kernel_certificate(_request())

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"
    assert decision["method"] == "CHECKED_CERTIFICATE"


@pytest.mark.parametrize("mutation", ["bindings", "format", "forbidden_proof"])
def test_lean_checker_rejects_unbound_or_unsupported_certificates(
    mutation: str,
) -> None:
    request = _request()
    certificate = request["certificate"]["payload"]
    if mutation == "bindings":
        certificate["bindings"]["candidate_digest"] = "sha256:" + "9" * 64
    elif mutation == "format":
        certificate["format_version"] = "2"
    else:
        certificate["payload"]["proof"] = "by sorry"
        request["candidate"]["payload"]["proof"] = "by sorry"

    decision = check_kernel_certificate(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_lean_checker_timeout_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timed_out(*_args: object, **_kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd=("lean",), timeout=1)

    monkeypatch.setattr("jacobian_checkers.lean4._run_lean", timed_out)

    decision = check_kernel_certificate(_request())

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"
