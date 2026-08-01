from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from jacobian.contracts.sat import SatLratResourceLimits, canonicalize_cnf
from jacobian.eval.lrat_profile import validate_lrat_profile

_CORPUS_PATH = (
    Path(__file__).resolve().parents[3]
    / "research"
    / "evaluations"
    / "lrat-authority-v1"
    / "corpus.json"
)
_CORPUS_DIGEST = (
    "sha256:7af048de3c3f2eb9481c13d03663b280a39a0c124c55b87b0b31c42b139a1f26"
)


def _corpus() -> dict[str, Any]:
    return json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))


def test_frozen_lrat_corpus_has_a_stable_digest() -> None:
    digest = "sha256:" + hashlib.sha256(_CORPUS_PATH.read_bytes()).hexdigest()

    assert digest == _CORPUS_DIGEST


def test_frozen_lrat_corpus_covers_profile_and_checker_obligations() -> None:
    corpus = _corpus()

    assert corpus["corpus_version"] == "jacobian.lrat.authority.v1"
    assert corpus["profile"] == "jacobian.lrat.rup/v1"
    assert corpus["encoding"] == "base64"
    assert {case["category"] for case in corpus["cases"]} == {
        "valid",
        "malformed",
        "wrong-cnf-binding",
        "altered-hint",
        "unsupported",
        "resource-limit",
    }
    assert len(corpus["cases"]) >= 10


@pytest.mark.parametrize(
    "case",
    _corpus()["cases"],
    ids=lambda case: case["case_id"],
)
def test_lrat_profile_gate_matches_every_frozen_case(
    case: dict[str, Any],
) -> None:
    cnf = canonicalize_cnf(
        variable_names=tuple(case["variables"]),
        clauses=tuple(tuple(row) for row in case["clauses"]),
    )
    proof = base64.b64decode(case["proof_base64"], validate=True)
    limits = SatLratResourceLimits(**case["limits"])

    profile_error = validate_lrat_profile(cnf, proof, limits=limits)

    assert ("ACCEPTED" if profile_error is None else "REJECTED") == case[
        "expected_profile"
    ]
