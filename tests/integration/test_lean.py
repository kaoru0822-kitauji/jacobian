from __future__ import annotations

import asyncio
import json
import shutil
import threading
from pathlib import Path

import pytest

from jacobian.adapters.mcp.server import ToolProfile, create_server
from jacobian.contracts.checkers import CheckerDecision
from jacobian.contracts.lean import LeanEnvironment
from jacobian.contracts.results import (
    Arithmetic,
    Conclusion,
    Coverage,
    InputStatus,
    Method,
    Verification,
)
from jacobian.kernel import JacobianKernel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MATHLIB_OLEAN = (
    PROJECT_ROOT
    / "lean"
    / ".lake"
    / "packages"
    / "mathlib"
    / ".lake"
    / "build"
    / "lib"
    / "lean"
    / "Mathlib.olean"
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external_backend,
    pytest.mark.skipif(shutil.which("lean") is None, reason="Lean is not installed"),
]


@pytest.mark.skipif(
    not MATHLIB_OLEAN.is_file(),
    reason="the pinned mathlib runtime has not been built",
)
def test_mathlib_sqrt_two_proof_creates_bound_verification_record(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    assert kernel.lean is not None
    assert kernel.lean_checkers[LeanEnvironment.MATHLIB].checker_timeout_seconds == 105

    verified = kernel.lean.verify(
        environment=LeanEnvironment.MATHLIB,
        statement="Irrational (Real.sqrt 2)",
        proof="exact irrational_sqrt_two",
    )

    assert verified.result.conclusion is Conclusion.TRUE
    assert verified.result.assurance.verification is Verification.VERIFIED
    certificate = kernel.store.get(verified.certificate_uri)
    assert certificate.payload["payload"]["environment"] == "MATHLIB"
    assert certificate.payload["payload"]["allowed_axioms"] == [
        "Classical.choice",
        "Quot.sound",
        "propext",
    ]
    assert certificate.payload["payload"]["mathlib_commit"] == (
        "fabf563a7c95a166b8d7b6efca11c8b4dc9d911f"
    )


def test_core_lean_induction_proof_creates_bound_verification_record(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    assert kernel.lean is not None

    verified = kernel.lean.verify(
        statement="∀ n : Nat, n + 0 = n",
        proof=(
            "intro n\n"
            "induction n with\n"
            "| zero => rfl\n"
            "| succ n ih => exact congrArg Nat.succ ih"
        ),
    )

    assert verified.result.conclusion is Conclusion.TRUE
    assert verified.result.assurance.verification is Verification.VERIFIED
    assert verified.result.verification_record_uri is not None
    record = kernel.store.get(verified.result.verification_record_uri)
    certificate = kernel.store.get(verified.certificate_uri)
    assert record.payload["evidence_uri"] == verified.certificate_uri
    assert record.payload["bindings"] == certificate.payload["bindings"]
    assert set(certificate.manifest.parents) == {
        verified.claim_uri,
        verified.candidate_uri,
    }


def test_core_lean_tool_runs_through_compact_mcp_profile(tmp_path: Path) -> None:
    async def scenario() -> None:
        from mcp import Client

        async with Client(
            create_server(tmp_path, tool_profile=ToolProfile.VERIFICATION),
            raise_exceptions=True,
        ) as client:
            response = await client.call_tool(
                "lean.verify",
                {
                    "statement": "∀ n : Nat, n + 0 = n",
                    "proof": (
                        "intro n\n"
                        "induction n with\n"
                        "| zero => rfl\n"
                        "| succ n ih => exact congrArg Nat.succ ih"
                    ),
                },
            )
            assert response.is_error is False
            assert response.structured_content is None
            payload = json.loads(response.content[0].text)
            assert payload["result"]["conclusion"] == "TRUE"
            assert payload["result"]["assurance"]["verification"] == "VERIFIED"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "proof",
    [
        "sorry",
        "native_decide",
        "run_tac exact q(true)",
        "exact Nat.succ.inj",
    ],
)
def test_core_lean_rejects_untrusted_or_invalid_proofs(
    tmp_path: Path,
    proof: str,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    assert kernel.lean is not None

    rejected = kernel.lean.verify(
        statement="∀ n : Nat, n + 0 = n",
        proof=proof,
    )

    assert rejected.result.input.status is InputStatus.REJECTED
    assert rejected.result.conclusion is Conclusion.UNKNOWN
    assert rejected.result.assurance.verification is Verification.UNVERIFIED
    assert rejected.result.verification_record_uri is None


def test_lean_reuses_only_an_exact_active_checker_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    assert kernel.lean is not None
    calls = 0

    def accept(**_: object) -> CheckerDecision:
        nonlocal calls
        calls += 1
        return CheckerDecision(
            accepted=True,
            conclusion=Conclusion.TRUE,
            arithmetic=Arithmetic.SYMBOLIC,
            method=Method.CHECKED_CERTIFICATE,
            coverage=Coverage.NOT_APPLICABLE,
            detail="accepted by test checker",
        )

    def unexpected_selector(**_: object) -> object:
        raise AssertionError("Lean must use its explicitly installed checker")

    monkeypatch.setattr(kernel.verification, "_run_checker", accept)
    monkeypatch.setattr(kernel.checkers, "select_compatible", unexpected_selector)
    first = kernel.lean.verify(statement="1 + 1 = 2", proof="rfl")
    repeated = kernel.lean.verify(statement="1 + 1 = 2", proof="rfl")
    changed = kernel.lean.verify(statement="2 + 2 = 4", proof="rfl")

    assert calls == 2
    assert first.cache_hit is False
    assert repeated.cache_hit is True
    assert repeated.result.verification_record_uri == (
        first.result.verification_record_uri
    )
    assert changed.cache_hit is False


def test_lean_cache_does_not_reuse_a_revoked_checker_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    assert kernel.lean is not None
    monkeypatch.setattr(
        kernel.verification,
        "_run_checker",
        lambda **_: CheckerDecision(
            accepted=True,
            conclusion=Conclusion.TRUE,
            arithmetic=Arithmetic.SYMBOLIC,
            method=Method.CHECKED_CERTIFICATE,
            coverage=Coverage.NOT_APPLICABLE,
            detail="accepted by test checker",
        ),
    )
    first = kernel.lean.verify(statement="1 + 1 = 2", proof="rfl")
    checker_id = kernel.lean_checkers[LeanEnvironment.CORE].checker_id
    kernel.checkers.revoke(checker_id, reason="cache trust-boundary test")

    repeated = kernel.lean.verify(statement="1 + 1 = 2", proof="rfl")

    assert first.result.assurance.verification is Verification.VERIFIED
    assert repeated.cache_hit is False
    assert repeated.result.assurance.verification is Verification.UNVERIFIED


def test_mathlib_warmup_starts_only_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    assert kernel.lean is not None
    warmed = threading.Event()
    monkeypatch.setattr(kernel.lean, "_warm_mathlib", warmed.set)

    assert kernel.lean.start_mathlib_warmup() is True
    assert warmed.wait(timeout=2)
    assert kernel.lean.start_mathlib_warmup() is False
