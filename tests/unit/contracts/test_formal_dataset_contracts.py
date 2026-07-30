from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.formal_datasets import (
    FormalDatasetEnvironment,
    FormalDatasetMaterializeRequest,
)


def _request() -> dict[str, object]:
    return {
        "dataset_revision": "3a5dceb842b916345a4d7bb7dc4c1dbd4b98aa",
        "sample_id": "mathd_algebra_1",
        "source_url": "https://github.com/facebookresearch/miniF2F",
        "row": {
            "dataset_id": "MINIF2F",
            "name": "mathd_algebra_1",
            "split": "test",
            "formal_statement": "theorem mathd_algebra_1 : True := by trivial",
            "informal_statement": "A fixture statement.",
        },
        "environment": {
            "lean_version": "4.31.0",
            "project_revision": "fixture-project",
        },
    }


def test_request_dispatches_to_minif2f_contract() -> None:
    request = FormalDatasetMaterializeRequest.model_validate(_request())

    assert request.row.dataset_id == "MINIF2F"
    assert request.row.name == request.sample_id


def test_request_rejects_sample_identity_mismatch() -> None:
    payload = _request()
    payload["sample_id"] = "another-row"

    with pytest.raises(ValidationError, match="sample_id"):
        FormalDatasetMaterializeRequest.model_validate(payload)


def test_request_rejects_unregistered_dataset() -> None:
    payload = _request()
    assert isinstance(payload["row"], dict)
    payload["row"]["dataset_id"] = "UNKNOWN"

    with pytest.raises(ValidationError):
        FormalDatasetMaterializeRequest.model_validate(payload)


def test_environment_rejects_duplicate_replay_bindings() -> None:
    with pytest.raises(ValidationError, match="imports must be unique"):
        FormalDatasetEnvironment(
            lean_version="4.31.0",
            project_revision="fixture",
            imports=("Mathlib", "Mathlib"),
        )

    with pytest.raises(ValidationError, match="project file paths must be unique"):
        FormalDatasetEnvironment(
            lean_version="4.31.0",
            project_revision="fixture",
            project_files=(
                {"path": "lakefile.toml", "digest": "sha256:" + "a" * 64},
                {"path": "lakefile.toml", "digest": "sha256:" + "b" * 64},
            ),
        )


@pytest.mark.parametrize(
    "path",
    (
        "lake/./lakefile.toml",
        "lake//lakefile.toml",
        "./lakefile.toml",
        "lake/",
    ),
)
def test_environment_rejects_aliased_project_paths(path: str) -> None:
    with pytest.raises(ValidationError, match="canonical NFC and relative"):
        FormalDatasetEnvironment(
            lean_version="4.31.0",
            project_revision="fixture",
            project_files=({"path": path, "digest": "sha256:" + "a" * 64},),
        )


def test_environment_rejects_non_nfc_and_oversized_items() -> None:
    with pytest.raises(ValidationError, match="canonical NFC"):
        FormalDatasetEnvironment(
            lean_version="4.31.0",
            project_revision="fixture",
            project_files=(
                {"path": "Cafe\u0301.lean", "digest": "sha256:" + "a" * 64},
            ),
        )
    with pytest.raises(ValidationError):
        FormalDatasetEnvironment(
            lean_version="4.31.0",
            project_revision="fixture",
            imports=("I" * 2_001,),
        )
    with pytest.raises(ValidationError):
        FormalDatasetEnvironment(
            lean_version="4.31.0",
            project_revision="fixture",
            theorem_context=("T" * 2_001,),
        )


def test_request_rejects_non_nfc_or_blank_formal_source() -> None:
    non_nfc = _request()
    assert isinstance(non_nfc["row"], dict)
    non_nfc["row"]["formal_statement"] = 'theorem t : "e\u0301" = "é" := by rfl'
    with pytest.raises(ValidationError, match="NFC-normalized"):
        FormalDatasetMaterializeRequest.model_validate(non_nfc)

    blank = _request()
    assert isinstance(blank["row"], dict)
    blank["row"]["formal_statement"] = " \n\t"
    with pytest.raises(ValidationError, match="formal_statement must not be blank"):
        FormalDatasetMaterializeRequest.model_validate(blank)


def test_environment_rejects_unicode_equivalent_replay_entries() -> None:
    with pytest.raises(ValidationError, match="NFC-normalized"):
        FormalDatasetEnvironment(
            lean_version="4.31.0",
            project_revision="fixture",
            imports=("Café", "Cafe\u0301"),
        )
    with pytest.raises(ValidationError, match="NFC-normalized"):
        FormalDatasetEnvironment(
            lean_version="4.31.0",
            project_revision="fixture",
            theorem_context=("Café", "Cafe\u0301"),
        )


@pytest.mark.parametrize(
    ("container", "field"),
    (
        ("request", "dataset_revision"),
        ("request", "source_url"),
        ("environment", "project_revision"),
        ("environment", "namespace"),
    ),
)
def test_request_rejects_non_nfc_scalar_provenance(
    container: str,
    field: str,
) -> None:
    payload = _request()
    target = payload if container == "request" else payload["environment"]
    assert isinstance(target, dict)
    target[field] = "Revision-Cafe\u0301"

    with pytest.raises(ValidationError, match="NFC-normalized"):
        FormalDatasetMaterializeRequest.model_validate(payload)
