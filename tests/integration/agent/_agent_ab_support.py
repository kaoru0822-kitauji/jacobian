from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from jacobian.contracts.capabilities import (
    CapabilityInstallTier,
    CapabilityProviderAvailability,
    CapabilityProviderDigestKind,
    CapabilityProviderRuntime,
)
from jacobian.runtime import CheckerAuthorityMode, create_runtime
from jacobian.runtime.model import JacobianRuntime


def _runtime_from_template(
    tmp_path: Path,
    template: Path,
    *,
    name: str = "state",
    checker_authority: CheckerAuthorityMode = CheckerAuthorityMode.INSTALL_BUNDLED,
) -> tuple[Path, JacobianRuntime]:
    """Copy the reference store template into a sibling state directory."""

    state_dir = tmp_path / name
    shutil.copytree(template, state_dir)
    return state_dir, create_runtime(
        state_dir,
        checker_authority=checker_authority,
    )


def _report(
    *,
    assurance: str,
    verification_record_uri: str | None,
) -> dict[str, Any]:
    return {
        "case_id": "ERDOS-STRAUS-AB-001",
        "conclusion": "TRUE",
        "checked_count": 119,
        "first_failure": None,
        "assurance": assurance,
        "verification_record_uri": verification_record_uri,
        "limitations": ["finite interval only"],
        "feedback": {
            "reasoning_focus": ["bounded interpretation"],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }


def _lean_proof_case() -> dict[str, Any]:
    return {
        "case_id": "LEAN-PRIVATE-TEST-001",
        "version": "1",
        "task_type": "lean_proof",
        "prompt": "Prove the exact private test proposition.",
        "statement": "∀ n : Nat, Nat.gcd n 0 = n",
        "environment": "MATHLIB",
    }


def _write_private_case(tmp_path: Path) -> Path:
    path = tmp_path / "private-case.json"
    path.write_text(json.dumps(_lean_proof_case()), encoding="utf-8")
    return path


def _sat_producer() -> CapabilityProviderRuntime:
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


def _smt_producer() -> CapabilityProviderRuntime:
    return CapabilityProviderRuntime(
        provider="cvc5",
        availability=CapabilityProviderAvailability.AVAILABLE,
        version="1.3.4",
        digest="sha256:" + "d" * 64,
        digest_kind=CapabilityProviderDigestKind.PYTHON_DISTRIBUTION_RECORD,
        platform="linux-x86_64",
        install_tier=CapabilityInstallTier.T1,
        license_id="BSD-3-Clause",
        features=("alethe-proof-production",),
        configuration={
            "profile": "jacobian.smtlib2.qf-unsat/v1",
            "proof_format": "cvc5.alethe/1.3.4",
        },
    )


def _install_fake_carcara(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    executable = tmp_path / "carcara"
    executable.write_text(
        (
            "#!/usr/bin/python3\n"
            "import sys\n"
            "if '--version' in sys.argv:\n"
            "    print('carcara 1.1.0 [git master 394edbb]')\n"
            "elif sys.argv[1:] == ['check', '--help']:\n"
            "    print('--strict-parsing --parse-hole-args '\n"
            "          '--allow-int-real-subtyping --expand-let-bindings')\n"
            "else:\n"
            "    print('valid')\n"
        ),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    digest = "sha256:" + hashlib.sha256(executable.read_bytes()).hexdigest()
    executable.with_name("carcara.jacobian-runtime.json").write_text(
        json.dumps(
            {
                "runtime_manifest_version": "1",
                "provider": "carcara",
                "version": "1.1.0",
                "source_repository": "https://github.com/ufmg-smite/carcara",
                "source_commit": "394edbb15ba95c47893f1d821fddde7e016af178",
                "compatible_cvc5_version": "1.3.4",
                "executable_sha256": digest,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")


def _sat_report(
    *,
    case_id: str,
    cnf_uri: str,
    assignment_uri: str | None,
    record_uri: str | None,
    assurance: str,
    final_verification: str,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "status": "SATISFIABLE",
        "conclusion": "TRUE",
        "assurance": assurance,
        "final_verification": final_verification,
        "evidence_kind": "ASSIGNMENT",
        "assignment": {"a": False, "b": True},
        "cnf_uri": cnf_uri,
        "evidence_uri": assignment_uri,
        "verification_record_uri": record_uri,
        "limitations": ["exact supplied CNF only"],
        "feedback": {
            "reasoning_focus": ["distinguish model production from verification"],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }


def _linear_case() -> dict[str, Any]:
    return {
        "case_id": "LINEAR-PRIVATE-TEST-001",
        "version": "1",
        "task_type": "linear_rational_solution",
        "prompt": "Find one exact solution of the supplied rational system.",
        "system": {
            "variables": ["u", "v"],
            "coefficients": {
                "entries": [
                    [
                        {"num": "2", "den": "1"},
                        {"num": "1", "den": "1"},
                    ],
                    [
                        {"num": "1", "den": "1"},
                        {"num": "-1", "den": "1"},
                    ],
                ]
            },
            "rhs": [
                {"num": "5", "den": "1"},
                {"num": "1", "den": "1"},
            ],
        },
    }


def _linear_report(
    *,
    system_uri: str | None,
    solution_uri: str | None,
    record_uri: str | None,
    assurance: str,
    final_verification: str,
) -> dict[str, Any]:
    return {
        "case_id": "LINEAR-PRIVATE-TEST-001",
        "status": "SOLUTION_FOUND",
        "conclusion": "TRUE",
        "solution": [
            {"num": "2", "den": "1"},
            {"num": "1", "den": "1"},
        ],
        "assurance": assurance,
        "final_verification": final_verification,
        "system_uri": system_uri,
        "solution_uri": solution_uri,
        "verification_record_uri": record_uri,
        "limitations": ["one exact vector; no uniqueness claim"],
        "feedback": {
            "reasoning_focus": ["preserve exact variable order"],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }


def _hnf_case() -> dict[str, Any]:
    return {
        "case_id": "HNF-PRIVATE-TEST-001",
        "version": "1",
        "task_type": "matrix_hermite_normal_form",
        "prompt": "Compute the exact row Hermite normal form.",
        "matrix": {
            "entries": [
                ["0", "2", "4"],
                ["0", "6", "8"],
            ]
        },
    }


def _hnf_report(
    *,
    matrix_uri: str | None,
    normal_form_uri: str | None,
    record_uri: str | None,
    assurance: str,
    final_verification: str,
) -> dict[str, Any]:
    return {
        "case_id": "HNF-PRIVATE-TEST-001",
        "status": "NORMAL_FORM_PRODUCED",
        "conclusion": "TRUE",
        "normal_form": [["0", "2", "0"], ["0", "0", "4"]],
        "transformation": [["-2", "1"], ["3", "-1"]],
        "assurance": assurance,
        "final_verification": final_verification,
        "matrix_uri": matrix_uri,
        "normal_form_uri": normal_form_uri,
        "verification_record_uri": record_uri,
        "limitations": ["the exact supplied integer matrix only"],
        "feedback": {
            "reasoning_focus": ["preserve row-HNF and transform conventions"],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }


def _polynomial_normalization_case() -> dict[str, Any]:
    return {
        "case_id": "POLY-NORMALIZE-PRIVATE-TEST-001",
        "version": "1",
        "task_type": "polynomial_expression_normalization",
        "prompt": "Normalize the exact supplied typed polynomial expression.",
        "expression": {
            "variables": ["x", "y"],
            "expression": {
                "kind": "multiply",
                "operands": [
                    {
                        "kind": "add",
                        "operands": [
                            {"kind": "variable", "name": "x"},
                            {"kind": "variable", "name": "y"},
                        ],
                    },
                    {
                        "kind": "add",
                        "operands": [
                            {"kind": "variable", "name": "x"},
                            {
                                "kind": "negate",
                                "operand": {"kind": "variable", "name": "y"},
                            },
                        ],
                    },
                ],
            },
        },
        "expected_normalized": {
            "terms": [
                {
                    "coefficient": {"num": "1", "den": "1"},
                    "exponents": [2, 0],
                },
                {
                    "coefficient": {"num": "-1", "den": "1"},
                    "exponents": [0, 2],
                },
            ]
        },
    }


def _polynomial_normalization_report(
    *,
    expression_uri: str | None,
    normalization_uri: str | None,
    record_uri: str | None,
    assurance: str,
    final_verification: str,
) -> dict[str, Any]:
    return {
        "case_id": "POLY-NORMALIZE-PRIVATE-TEST-001",
        "status": "NORMALIZATION_PRODUCED",
        "conclusion": "TRUE",
        "variables": ["x", "y"],
        "normalized": {
            "terms": [
                {
                    "coefficient": {"num": "1", "den": "1"},
                    "exponents": [2, 0],
                },
                {
                    "coefficient": {"num": "-1", "den": "1"},
                    "exponents": [0, 2],
                },
            ]
        },
        "assurance": assurance,
        "final_verification": final_verification,
        "expression_uri": expression_uri,
        "normalization_uri": normalization_uri,
        "verification_record_uri": record_uri,
        "limitations": ["the exact supplied QQ-polynomial expression only"],
        "feedback": {
            "reasoning_focus": ["preserve the declared variable order"],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }
