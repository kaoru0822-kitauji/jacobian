from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from benchmarks.jacobian_math_evals.catalog import load_sources
from benchmarks.jacobian_math_evals.handlers.huggingface_rows import (
    HuggingFaceExactAnswerHandler,
    UnsupportedDatasetSchemaError,
)
from benchmarks.jacobian_math_evals.handlers.registry import HANDLERS
from benchmarks.jacobian_math_evals.models import (
    OracleKind,
    TaskReadiness,
)

FIXTURE = Path(__file__).parent / "fixtures" / "hf_exact_answer_first_rows.json"


def _source():
    source = next(
        source
        for source in load_sources()
        if source.host == "huggingface.co" and source.access_state.value == "public"
    )
    return replace(
        source,
        source_id="src-111111111111",
        canonical_url="https://huggingface.co/datasets/example/math",
        configurations=("default",),
        splits=("default/dev",),
    )


def test_hf_scalar_question_answer_row_becomes_public_diagnostic() -> None:
    source = _source()
    handler = HuggingFaceExactAnswerHandler(source.source_id)
    [spec] = list(handler.iter_specs(source, FIXTURE, full=False))
    assert spec.task_id == "hf-111111111111-000007"
    assert spec.instance["problem"] == "Compute 6 * 7."
    assert spec.expected["expected_answer"] == "42"
    assert spec.readiness == TaskReadiness.PUBLIC_DIAGNOSTIC
    assert spec.oracle_kind == OracleKind.PUBLIC_ANSWER
    assert spec.scored is False


def test_probe_registers_only_schema_supported_hf_sources() -> None:
    hf_ids = {
        handler.source_id
        for handler in HANDLERS
        if type(handler) is HuggingFaceExactAnswerHandler
    }
    assert hf_ids == {
        "src-bfe4104f95fe",
        "src-cf3efb96d254",
        "src-2c507204d602",
        "src-8505da174187",
        "src-ddb417aba592",
        "src-15029beb0a1c",
        "src-1665a144a01e",
        "src-31d5ef657014",
        "src-e48c58681d3d",
        "src-910db4b973e5",
        "src-d2436de6e56e",
        "src-4e6c2b70defd",
        "src-38b31ef3be7d",
        "src-2eac08ad4866",
        "src-cf45ed72bfc7",
        "src-713d26bbe375",
    }


def test_hf_handler_rejects_rows_without_deterministic_answer(
    tmp_path: Path,
) -> None:
    source = _source()
    snapshot = tmp_path / "rows.json"
    snapshot.write_text(
        '{"dataset":"example/math","config":"default","split":"dev",'
        '"rows":[{"row_idx":0,"row":{"problem":"Prove P."}}]}'
    )
    with pytest.raises(
        UnsupportedDatasetSchemaError,
        match="no row has scalar problem and answer fields",
    ):
        list(
            HuggingFaceExactAnswerHandler(source.source_id).iter_specs(
                source, snapshot, full=False
            )
        )


def test_hf_handler_offline_missing_snapshot_fails_closed(
    tmp_path: Path,
) -> None:
    source = _source()
    with pytest.raises(
        FileNotFoundError, match="offline Dataset Viewer snapshot missing"
    ):
        HuggingFaceExactAnswerHandler(source.source_id).acquire(
            source, cache_dir=tmp_path, offline=True
        )


def _write_digest_bound_json(path: Path, value: object) -> None:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    path.with_suffix(".sha256").write_text(hashlib.sha256(payload).hexdigest())


def test_hf_handler_rejects_cache_not_bound_to_source_lock(tmp_path: Path) -> None:
    source = replace(
        _source(),
        snapshot_sha256="sha256:" + "0" * 64,
    )
    snapshot = tmp_path / source.source_id / "default--dev.json"
    _write_digest_bound_json(snapshot, json.loads(FIXTURE.read_text()))

    with pytest.raises(ValueError, match="does not match source lock"):
        HuggingFaceExactAnswerHandler(source.source_id).acquire(
            source,
            cache_dir=tmp_path,
            offline=True,
        )


def test_hf_full_offline_stream_replays_every_manifest_row(
    tmp_path: Path,
) -> None:
    source = _source()
    full_dir = tmp_path / source.source_id / "full" / "default--dev"
    _write_digest_bound_json(
        full_dir / "manifest.json",
        {
            "dataset": "example/math",
            "config": "default",
            "split": "dev",
            "source_revision": source.immutable_revision,
            "source_snapshot_sha256": source.snapshot_sha256,
            "num_rows": 2,
            "page_size": 100,
        },
    )
    _write_digest_bound_json(
        full_dir / "000000000000.json",
        {
            "dataset": "example/math",
            "config": "default",
            "split": "dev",
            "source_revision": source.immutable_revision,
            "source_snapshot_sha256": source.snapshot_sha256,
            "offset": 0,
            "rows": [
                {"row_idx": 0, "row": {"problem": "1+1", "answer": "2"}},
                {"row_idx": 1, "row": {"problem": "2+2", "answer": "4"}},
            ],
        },
    )
    specs = list(
        HuggingFaceExactAnswerHandler(source.source_id).iter_full_specs(
            source,
            cache_dir=tmp_path,
            offline=True,
        )
    )
    assert [spec.task_id for spec in specs] == [
        "hf-111111111111-000000",
        "hf-111111111111-000001",
    ]


def test_hf_full_offline_rejects_page_from_another_revision(
    tmp_path: Path,
) -> None:
    source = _source()
    full_dir = tmp_path / source.source_id / "full" / "default--dev"
    _write_digest_bound_json(
        full_dir / "manifest.json",
        {
            "dataset": "example/math",
            "config": "default",
            "split": "dev",
            "source_revision": source.immutable_revision,
            "source_snapshot_sha256": source.snapshot_sha256,
            "num_rows": 1,
            "page_size": 100,
        },
    )
    _write_digest_bound_json(
        full_dir / "000000000000.json",
        {
            "dataset": "example/math",
            "config": "default",
            "split": "dev",
            "source_revision": "stale",
            "source_snapshot_sha256": source.snapshot_sha256,
            "offset": 0,
            "rows": [{"row_idx": 0, "row": {"problem": "1+1", "answer": "2"}}],
        },
    )
    with pytest.raises(ValueError, match="page identity mismatch"):
        list(
            HuggingFaceExactAnswerHandler(source.source_id).iter_full_specs(
                source,
                cache_dir=tmp_path,
                offline=True,
            )
        )


def test_hf_full_offline_requires_complete_snapshot(tmp_path: Path) -> None:
    source = _source()
    with pytest.raises(
        FileNotFoundError,
        match="offline full snapshot manifest missing",
    ):
        list(
            HuggingFaceExactAnswerHandler(source.source_id).iter_full_specs(
                source,
                cache_dir=tmp_path,
                offline=True,
            )
        )
