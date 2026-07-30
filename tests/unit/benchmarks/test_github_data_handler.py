from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from benchmarks.jacobian_math_evals.catalog import load_sources
from benchmarks.jacobian_math_evals.handlers.github_data_rows import (
    GitHubStructuredDataHandler,
    _parse_rows,
)
from benchmarks.jacobian_math_evals.models import OracleKind, TaskReadiness

FIXTURE = Path(__file__).parent / "fixtures" / "github_structured_data.json"


def _source():
    source = next(
        source
        for source in load_sources()
        if source.host == "github.com" and source.immutable_revision
    )
    return replace(
        source,
        source_id="src-333333333333",
        canonical_url="https://github.com/example/math",
        immutable_revision="3" * 40,
        snapshot_sha256="sha256:" + "3" * 64,
    )


def test_repository_json_parser_finds_explicit_problem_solution() -> None:
    [row] = list(_parse_rows(FIXTURE.read_bytes(), ".json"))
    assert row == {"problem": "Compute 8 * 9.", "solution": "72"}


def test_repository_snapshot_produces_exact_public_task(
    tmp_path: Path,
) -> None:
    source = _source()
    snapshot = tmp_path / "structured-data-row.json"
    snapshot.write_text(
        json.dumps(
            {
                "source_id": source.source_id,
                "repository": "example/math",
                "revision": source.immutable_revision,
                "source_snapshot_sha256": source.snapshot_sha256,
                "path": "data/example.json",
                "family": "exact-answer",
                "instruction": "Solve the supplied mathematical problem",
                "input_field": "problem",
                "input": "Compute 8 * 9.",
                "target_field": "solution",
                "target": "72",
                "content_sha256": "sha256:" + hashlib.sha256(b"fixture").hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    [spec] = tuple(
        GitHubStructuredDataHandler(source.source_id).iter_specs(
            source, snapshot, full=False
        )
    )
    assert spec.expected["expected_answer"] == "72"
    assert spec.readiness == TaskReadiness.PUBLIC_DIAGNOSTIC
    assert spec.oracle_kind == OracleKind.PUBLIC_ANSWER


def test_repository_handler_rejects_cache_from_another_snapshot(
    tmp_path: Path,
) -> None:
    source = _source()
    destination = tmp_path / source.source_id / "structured-data-row.json"
    destination.parent.mkdir(parents=True)
    payload = (
        json.dumps(
            {
                "source_id": source.source_id,
                "revision": source.immutable_revision,
                "source_snapshot_sha256": "sha256:" + "0" * 64,
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()
    destination.write_bytes(payload)
    destination.with_suffix(".sha256").write_text(hashlib.sha256(payload).hexdigest())
    with pytest.raises(ValueError, match="does not match source lock"):
        GitHubStructuredDataHandler(source.source_id).acquire(
            source,
            cache_dir=tmp_path,
            offline=True,
        )
