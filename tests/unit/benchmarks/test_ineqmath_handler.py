from __future__ import annotations

from pathlib import Path

import pytest
from benchmarks.jacobian_math_evals.catalog import load_sources
from benchmarks.jacobian_math_evals.handlers.ineqmath import (
    SOURCE_ID,
    IneqMathHandler,
)
from benchmarks.jacobian_math_evals.models import OracleKind, TaskReadiness

FIXTURE = Path(__file__).parent / "fixtures" / "ineqmath_dev_row.json"


def _source():
    return next(source for source in load_sources() if source.source_id == SOURCE_ID)


def test_ineqmath_fixture_produces_real_public_exact_answer_spec() -> None:
    [spec] = list(IneqMathHandler().iter_specs(_source(), FIXTURE, full=False))
    assert spec.task_id == "ineqmath-dev-000"
    assert spec.family == "exact-answer"
    assert spec.scored is False
    assert spec.readiness == TaskReadiness.PUBLIC_DIAGNOSTIC
    assert spec.oracle_kind == OracleKind.PUBLIC_ANSWER
    assert spec.instance["problem"].startswith("Let x > 0")
    assert spec.expected["expected_answer"] == "$C = 2$"
    assert spec.expected["snapshot_sha256"].startswith("sha256:")


def test_ineqmath_offline_acquisition_fails_when_snapshot_missing(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError, match="offline IneqMath snapshot missing"):
        IneqMathHandler().acquire(_source(), cache_dir=tmp_path, offline=True)


def test_ineqmath_rejects_malformed_or_wrong_split(tmp_path: Path) -> None:
    malformed = tmp_path / "bad.json"
    malformed.write_text(
        '[{"data_id":"1","problem":"p","answer":"a","type":"bound",'
        '"data_split":"test"}]'
    )
    with pytest.raises(ValueError, match="is not from dev"):
        list(IneqMathHandler().iter_specs(_source(), malformed, full=False))
