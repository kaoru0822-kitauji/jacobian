from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from benchmarks.jacobian_math_evals.verifier_runtime import score_submission

TASK_ID = "exact-001"
SOURCE_ID = "src-111111111111"


def _expected(**updates: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "task_id": TASK_ID,
        "source_ids": [SOURCE_ID],
        "expected_answer": "42",
        "maximum_assurance": "UNVERIFIED",
        "required_scope_terms": [TASK_ID, SOURCE_ID],
    }
    value.update(updates)
    return value


def _write_submission(workspace: Path, **updates: Any) -> None:
    evidence = workspace / "evidence" / "answer.txt"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("6 * 7 = 42\n")
    value: dict[str, Any] = {
        "task_id": TASK_ID,
        "source_ids": [SOURCE_ID],
        "answer": "42",
        "claimed_assurance": "UNVERIFIED",
        "evidence": [
            {
                "path": "evidence/answer.txt",
                "sha256": "sha256:" + hashlib.sha256(evidence.read_bytes()).hexdigest(),
            }
        ],
        "scope": f"{TASK_ID} {SOURCE_ID}",
        "completeness": "COMPLETE",
        "limitations": [],
        "execution_status": "COMPLETED",
    }
    value.update(updates)
    (workspace / "submission.json").write_text(json.dumps(value))


def test_known_good_submission_receives_full_reward(tmp_path: Path) -> None:
    _write_submission(tmp_path)
    scores = score_submission(tmp_path, _expected())
    assert scores.reward == pytest.approx(1.0)


@pytest.mark.parametrize("execution_status", ["TIMEOUT", "CANCELLED", "ERROR"])
def test_non_completed_execution_is_non_conclusion(
    tmp_path: Path,
    execution_status: str,
) -> None:
    _write_submission(tmp_path, execution_status=execution_status)
    assert score_submission(tmp_path, _expected()).reward == 0


def test_empty_output_scores_zero(tmp_path: Path) -> None:
    scores = score_submission(tmp_path, _expected())
    assert scores == type(scores)(0.0, 0.0, 0.0, 0.0, False)


def test_wrong_answer_forces_aggregate_zero(tmp_path: Path) -> None:
    _write_submission(tmp_path, answer="41")
    scores = score_submission(tmp_path, _expected())
    assert scores.correctness == 0
    assert scores.reward == 0


def test_forged_evidence_digest_loses_evidence_reward(tmp_path: Path) -> None:
    _write_submission(
        tmp_path,
        evidence=[
            {
                "path": "evidence/answer.txt",
                "sha256": "sha256:" + "0" * 64,
            }
        ],
    )
    scores = score_submission(tmp_path, _expected())
    assert scores.correctness == 1
    assert scores.evidence_validity == 0
    assert scores.reward == pytest.approx(0.9)


def test_mismatched_statement_forces_zero(tmp_path: Path) -> None:
    wanted = "sha256:" + "1" * 64
    _write_submission(tmp_path, claim_digest="sha256:" + "2" * 64)
    assert score_submission(tmp_path, _expected(claim_digest=wanted)).reward == 0


def test_incomplete_enumeration_forces_zero(tmp_path: Path) -> None:
    _write_submission(
        tmp_path,
        completeness="PARTIAL",
        enumeration_complete=False,
    )
    assert score_submission(tmp_path, _expected(requires_complete=True)).reward == 0


def test_false_verified_claim_forces_zero(tmp_path: Path) -> None:
    _write_submission(tmp_path, claimed_assurance="VERIFIED")
    scores = score_submission(tmp_path, _expected())
    assert scores.false_certification is True
    assert scores.reward == 0


def test_wrong_task_or_source_binding_forces_zero(tmp_path: Path) -> None:
    _write_submission(tmp_path, task_id="altered", source_ids=["src-222222222222"])
    assert score_submission(tmp_path, _expected()).reward == 0


def test_alternative_valid_answer_passes(tmp_path: Path) -> None:
    _write_submission(tmp_path, answer="6·7")
    scores = score_submission(
        tmp_path,
        _expected(accepted_answers=["42", "6·7"]),
    )
    assert scores.reward == pytest.approx(1.0)


def test_unlisted_square_counterexample_passes_semantic_checker(
    tmp_path: Path,
) -> None:
    _write_submission(tmp_path, answer='{"x":17,"y":-17}')
    scores = score_submission(
        tmp_path,
        _expected(
            validator="square-counterexample",
            validator_instance={
                "claim": "x^2 = y^2 implies x = y",
            },
        ),
    )
    assert scores.correctness == 1


def test_wrong_counterexample_witness_fails_semantic_checker(
    tmp_path: Path,
) -> None:
    _write_submission(tmp_path, answer='{"x":3,"y":2}')
    scores = score_submission(
        tmp_path,
        _expected(
            validator="square-counterexample",
            validator_instance={"exponent": 2},
        ),
    )
    assert scores.reward == 0


@pytest.mark.parametrize(
    ("answer", "correct"),
    [
        ('["p","p -> q","q"]', 1),
        ('["p -> q","p","q"]', 1),
        ('["p","q"]', 0),
        ('["p","p -> q","r"]', 0),
    ],
)
def test_proof_replay_checks_each_line(
    tmp_path: Path,
    answer: str,
    correct: int,
) -> None:
    _write_submission(tmp_path, answer=answer)
    scores = score_submission(
        tmp_path,
        _expected(
            validator="modus-ponens-proof",
            validator_instance={
                "premises": ["p", "p -> q"],
                "goal": "q",
            },
        ),
    )
    assert scores.correctness == correct


def test_polynomial_checker_recomputes_answer(tmp_path: Path) -> None:
    _write_submission(tmp_path, answer="121")
    expected = _expected(
        validator="polynomial-evaluation",
        validator_instance={
            "coefficients_descending": [2, 0, -3, 5],
            "x": 4,
        },
    )
    assert score_submission(tmp_path, expected).correctness == 1
    _write_submission(tmp_path, answer="120")
    assert score_submission(tmp_path, expected).correctness == 0
