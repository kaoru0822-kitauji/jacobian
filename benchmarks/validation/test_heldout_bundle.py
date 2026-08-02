from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest
from benchmarks.tooling.harbor_suite import HarborSuiteError
from benchmarks.tooling.heldout_bundle import _safe_extract, validate_manifest


def _manifest() -> dict:
    tasks = [
        {
            "id": f"held-out-{index}",
            "family": "family-a" if index < 3 else "family-b",
            "digest": "sha256:" + "a" * 64,
            "verifier_path": f"dataset/held-out-{index}/tests/verifier.py",
            "verifier_digest": "sha256:" + "b" * 64,
            "oracle_path": f"dataset/held-out-{index}/solution/submission.json",
            "oracle_digest": "sha256:" + "c" * 64,
        }
        for index in range(5)
    ]
    return {
        "schema_version": "1",
        "bundle_id": "capability-held-out-v1",
        "bundle_version": "1.0.0",
        "archive": {
            "uri": "s3://private-bucket/bundle.tar.gz",
            "sha256": "sha256:" + "d" * 64,
        },
        "dataset": {
            "id": "capability-held-out-v1",
            "path": "dataset",
            "manifest_digest": "sha256:" + "e" * 64,
            "minimum_independent_families": 2,
        },
        "tasks": tasks,
        "conditions": [
            {
                "id": "C1",
                "role": "PRIMARY_CONTROL",
                "image": "registry.invalid/c1@sha256:" + "1" * 64,
                "catalog_digest": "sha256:" + "2" * 64,
                "policy_digest": "sha256:" + "3" * 64,
            },
            {
                "id": "C2",
                "role": "PRIMARY_TREATMENT",
                "image": "registry.invalid/c2@sha256:" + "4" * 64,
                "catalog_digest": "sha256:" + "5" * 64,
                "policy_digest": "sha256:" + "6" * 64,
            },
        ],
        "experiment": {
            "model": "model",
            "prompt_digest": "sha256:" + "7" * 64,
            "reasoning_effort": "high",
            "randomization_seed": 104729,
            "max_tokens": 100000,
            "max_cost_usd": 100.0,
            "stages": {
                "pilot": {
                    "task_ids": [item["id"] for item in tasks[:3]],
                    "repetitions": 3,
                },
                "decision": {
                    "task_ids": [item["id"] for item in tasks],
                    "repetitions": 5,
                },
            },
        },
    }


def _write(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_valid_manifest_freezes_c1_c2_and_budget_ladder(tmp_path: Path) -> None:
    manifest = validate_manifest(_write(tmp_path, _manifest()))

    assert manifest["experiment"]["stages"]["pilot"]["repetitions"] == 3


def test_manifest_rejects_unknown_stage_task(tmp_path: Path) -> None:
    value = _manifest()
    value["experiment"]["stages"]["pilot"]["task_ids"][0] = "unknown"

    with pytest.raises(HarborSuiteError, match="unknown task ids"):
        validate_manifest(_write(tmp_path, value))


def test_manifest_rejects_non_digest_pinned_image(tmp_path: Path) -> None:
    value = _manifest()
    value["conditions"][0]["image"] = "registry.invalid/c1:latest"

    with pytest.raises(HarborSuiteError, match="held-out manifest is invalid"):
        validate_manifest(_write(tmp_path, value))


def test_private_archive_rejects_workspace_escape(tmp_path: Path) -> None:
    source = tmp_path / "secret.txt"
    source.write_text("oracle", encoding="utf-8")
    archive = tmp_path / "bundle.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(source, arcname="../oracle.txt")
    output = tmp_path / "output"
    output.mkdir()

    with pytest.raises(HarborSuiteError, match="escapes output"):
        _safe_extract(archive, output)
