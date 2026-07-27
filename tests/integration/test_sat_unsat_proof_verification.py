from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

import pytest

import jacobian_checkers.sat
from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityInstallTier,
    CapabilityMode,
    CapabilityProviderAvailability,
    CapabilityProviderDigestKind,
    CapabilityProviderRuntime,
    CapabilityRequest,
)
from jacobian.contracts.evidence import CertificateEnvelope
from jacobian.contracts.results import ExecutionStatus
from jacobian.contracts.sat import SatResourceBudget
from jacobian.contracts.verification import VerificationRecord
from jacobian.kernel import JacobianKernel
from jacobian.provider_runtime import drat_trim_provider_runtime
from jacobian.verification import CheckerExecutionError, _environment_digest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("initialized_kernel_store_with_references"),
]


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _fake_drat_trim(tmp_path: Path, body: str) -> Path:
    executable = tmp_path / "drat-trim"
    executable.write_text(
        (
            "#!/usr/bin/python3\n"
            "import sys\n"
            "if '-h' in sys.argv:\n"
            "    print('usage: drat-trim [INPUT] [<PROOF>] [<option> ...]')\n"
            "    raise SystemExit(0)\n"
            f"{body}\n"
        ),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    manifest = executable.with_name(executable.name + ".jacobian-runtime.json")
    manifest.write_text(
        (
            "{\n"
            '  "runtime_manifest_version": "1",\n'
            '  "provider": "drat-trim",\n'
            '  "release_tag": "v05.22.2023",\n'
            '  "source_repository": '
            '"https://github.com/marijnheule/drat-trim",\n'
            '  "source_commit": '
            '"2e5e29cb0019d5cfd547d4208dca1b3ec290349f",\n'
            f'  "executable_sha256": "{_sha256_file(executable)}"\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    return executable


def _producer() -> CapabilityProviderRuntime:
    return CapabilityProviderRuntime(
        provider="cadical",
        availability=CapabilityProviderAvailability.AVAILABLE,
        version="3.0.1",
        digest="sha256:" + "d" * 64,
        digest_kind=CapabilityProviderDigestKind.EXECUTABLE,
        platform="linux-x86_64",
        install_tier=CapabilityInstallTier.T2,
        license_id="MIT",
    )


def _kernel_with_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    executable: Path,
    *,
    install_references: bool = True,
) -> JacobianKernel:
    runtime = drat_trim_provider_runtime(executable)
    assert runtime.availability is CapabilityProviderAvailability.AVAILABLE
    monkeypatch.setattr(
        "jacobian.kernel.drat_trim_provider_runtime",
        lambda *_args, **_kwargs: runtime,
    )
    return JacobianKernel(
        tmp_path / "store",
        install_references=install_references,
    )


@pytest.mark.parametrize(
    "attack",
    ["missing_provenance", "wrong_release", "digest_mismatch"],
)
def test_drat_trim_runtime_requires_exact_operator_provenance(
    tmp_path: Path,
    attack: str,
) -> None:
    executable = _fake_drat_trim(
        tmp_path,
        "print('s VERIFIED')\nraise SystemExit(0)",
    )
    manifest = executable.with_name(executable.name + ".jacobian-runtime.json")
    if attack == "missing_provenance":
        manifest.unlink()
    elif attack == "wrong_release":
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace(
                '"release_tag": "v05.22.2023"',
                '"release_tag": "untrusted"',
            ),
            encoding="utf-8",
        )
    else:
        executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        executable.chmod(0o755)

    runtime = drat_trim_provider_runtime(executable)

    assert runtime.availability is CapabilityProviderAvailability.UNAVAILABLE
    assert runtime.version is None
    assert runtime.digest is None
    assert runtime.diagnostic is not None


def _proof(kernel: JacobianKernel) -> tuple[str, str]:
    cnf = kernel.sat.put_cnf(
        variable_names=("x", "y"),
        clauses=((1, 2), (-1, 2), (1, -2), (-1, -2)),
    )
    proof = kernel.sat.put_proof(
        cnf_uri=cnf.artifact_uri,
        proof=b"-1 0\n0\n",
        producer=_producer(),
        resource_budget=SatResourceBudget(wall_seconds=5),
    )
    return cnf.artifact_uri, proof.artifact_uri


def _verify(kernel: JacobianKernel, proof_uri: str):
    return kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="sat.unsat_proof.verify",
            mode=CapabilityMode.VERIFY,
            input={"proof_uri": proof_uri},
        )
    )


@pytest.mark.subprocess
def test_unsat_proof_is_verified_by_authorized_external_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = _fake_drat_trim(
        tmp_path,
        "print('s VERIFIED')\nraise SystemExit(0)",
    )
    kernel = _kernel_with_runtime(tmp_path, monkeypatch, executable)
    cnf_uri, proof_uri = _proof(kernel)
    monkeypatch.setattr(
        jacobian_checkers.sat,
        "check_unsat_proof",
        lambda _request: {
            "accepted": False,
            "conclusion": "UNKNOWN",
            "arithmetic": "EXACT_INTEGER",
            "method": "CHECKED_CERTIFICATE",
            "coverage": "NOT_APPLICABLE",
            "detail": "parent-process monkeypatch",
        },
    )

    result = _verify(kernel, proof_uri)

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert result.output["status"] == "VERIFIED_UNSAT"
    assert result.output["conclusion"] == "TRUE"
    assert result.output["cnf_uri"] == cnf_uri
    assert result.output["proof_uri"] == proof_uri
    certificate_uri = result.output["certificate_uri"]
    certificate = CertificateEnvelope.model_validate(
        kernel.store.get(certificate_uri).payload
    )
    assert certificate.certificate_type == "sat.unsat-proof"
    assert certificate.payload == {
        "cnf_uri": cnf_uri,
        "proof_uri": proof_uri,
    }
    record_uri = result.output["verification_record_uri"]
    assert record_uri is not None
    record_artifact = kernel.store.get(record_uri)
    record = VerificationRecord.model_validate(record_artifact.payload)
    assert record.checker_id == kernel.sat_unsat_proof_checker.checker_id
    assert record.evidence_uri == certificate_uri
    checker = kernel.checkers.require_active(record.checker_id)
    assert checker.provider_runtime == kernel.drat_trim_runtime
    assert record.environment_digest == _environment_digest(
        checker.executable_digest,
        checker.provider_runtime,
    )
    assert set(record_artifact.manifest.parents) == {
        cnf_uri,
        proof_uri,
        certificate_uri,
    }


def test_rejected_proof_never_establishes_sat_or_unsat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = _fake_drat_trim(
        tmp_path,
        "print('s NOT VERIFIED')\nraise SystemExit(1)",
    )
    kernel = _kernel_with_runtime(tmp_path, monkeypatch, executable)
    _cnf_uri, proof_uri = _proof(kernel)

    result = _verify(kernel, proof_uri)

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.output["status"] == "REJECTED"
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["verification_record_uri"] is None
    assert result.assurance.verification_record_uri is None


def test_proof_verify_requires_runtime_and_operator_authorization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = _fake_drat_trim(
        tmp_path,
        "print('s VERIFIED')\nraise SystemExit(0)",
    )
    without_references = _kernel_with_runtime(
        tmp_path / "without-references",
        monkeypatch,
        executable,
        install_references=False,
    )
    unavailable = drat_trim_provider_runtime(tmp_path / "missing")
    monkeypatch.setattr(
        "jacobian.kernel.drat_trim_provider_runtime",
        lambda *_args, **_kwargs: unavailable,
    )
    without_runtime = JacobianKernel(
        tmp_path / "without-runtime",
        install_references=True,
    )

    assert without_references.sat_unsat_proof_checker.checker_id is None
    assert without_runtime.sat_unsat_proof_checker.checker_id is None
    for kernel in (without_references, without_runtime):
        assert "sat.unsat_proof.verify" not in {
            descriptor.capability_id
            for descriptor in kernel.capabilities.catalog().capabilities
        }


@pytest.mark.parametrize(
    ("exception", "expected_status", "expected_output_status"),
    [
        (
            subprocess.TimeoutExpired(cmd=("drat-trim",), timeout=1),
            ExecutionStatus.TIMEOUT,
            "TIMEOUT",
        ),
        (
            CheckerExecutionError("deliberate checker crash"),
            ExecutionStatus.ERROR,
            "ERROR",
        ),
    ],
)
def test_checker_operational_failure_never_creates_a_conclusion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
    expected_status: ExecutionStatus,
    expected_output_status: str,
) -> None:
    executable = _fake_drat_trim(
        tmp_path,
        "print('s VERIFIED')\nraise SystemExit(0)",
    )
    kernel = _kernel_with_runtime(tmp_path, monkeypatch, executable)
    _cnf_uri, proof_uri = _proof(kernel)

    def fail(**_kwargs: Any):
        raise exception

    monkeypatch.setattr(kernel.verification, "_run_checker", fail)
    result = _verify(kernel, proof_uri)

    assert result.execution.status is expected_status
    assert result.assurance.level is not CapabilityAssuranceLevel.VERIFIED
    assert result.output["status"] == expected_output_status
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["verification_record_uri"] is None


def test_runtime_replacement_after_authorization_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = _fake_drat_trim(
        tmp_path,
        "print('s VERIFIED')\nraise SystemExit(0)",
    )
    kernel = _kernel_with_runtime(tmp_path, monkeypatch, executable)
    _cnf_uri, proof_uri = _proof(kernel)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    result = _verify(kernel, proof_uri)

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.assurance.level is not CapabilityAssuranceLevel.VERIFIED
    assert result.output["status"] == "ERROR"
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["verification_record_uri"] is None
