from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.artifacts import ArtifactService
from jacobian.capabilities import CapabilityInvocationError
from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityRequest,
)
from jacobian.formal_datasets import install_formal_dataset_capability
from jacobian.schema_registry import SchemaRegistry
from jacobian.store import ArtifactStore
from jacobian_checkers.lean4 import LEAN_VERSION, MATHLIB_COMMIT


def _adapter(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    schemas = SchemaRegistry(store)
    artifacts = ArtifactService(store, schemas)
    adapter, _ = install_formal_dataset_capability(store, schemas, artifacts)
    return adapter


def _environment() -> dict[str, object]:
    return {
        "lean_version": LEAN_VERSION,
        "project_revision": "project-commit-123",
        "mathlib_revision": MATHLIB_COMMIT,
        "imports": ["Mathlib"],
        "namespace": "MiniF2F",
        "theorem_context": ["open Real"],
        "project_files": [
            {"path": "lean-toolchain", "digest": "sha256:" + "a" * 64},
            {"path": "lake-manifest.json", "digest": "sha256:" + "b" * 64},
        ],
    }


def _minif2f_request() -> dict[str, object]:
    return {
        "dataset_revision": "3a5dceb842b916345a4d7bb7dc4c1dbd4b98aa",
        "sample_id": "mathd_algebra_1",
        "source_url": (
            "https://huggingface.co/datasets/Tonic/MiniF2F/"
            "resolve/3a5dceb842b916345a4d7bb7dc4c1dbd4b98aa"
        ),
        "row": {
            "dataset_id": "MINIF2F",
            "name": "mathd_algebra_1",
            "split": "test",
            "header": "import Mathlib  \r\n",
            "formal_statement": (
                "theorem mathd_algebra_1 : (1 : Nat) = 1 := by  \r\n  rfl  "
            ),
            "informal_statement": "One equals one.  ",
            "informal_proof": "This is reflexive.  ",
        },
        "environment": _environment(),
    }


def _proofnet_request() -> dict[str, object]:
    return {
        "dataset_revision": "proofnet-fixture-revision",
        "sample_id": "analysis_1",
        "source_url": "https://github.com/zhangir-azerbayev/ProofNet",
        "row": {
            "dataset_id": "PROOFNET",
            "name": "analysis_1",
            "split": "test",
            "header": "import Mathlib\n",
            "formal_statement": "theorem analysis_1 : True := by trivial",
            "informal_statement": "A fixture undergraduate theorem.",
            "informal_proof": "The fixture is immediate.",
        },
        "environment": _environment(),
    }


@pytest.mark.parametrize("payload_factory", [_minif2f_request, _proofnet_request])
def test_supported_row_materializes_deterministically(
    tmp_path: Path,
    payload_factory,
) -> None:
    adapter = _adapter(tmp_path)
    payload = payload_factory()

    first = adapter.invoke(
        CapabilityRequest(
            capability_id="dataset.formal.materialize",
            input=payload,
        )
    )
    second = adapter.invoke(
        CapabilityRequest(
            capability_id="dataset.formal.materialize",
            input=payload,
        )
    )

    assert first.output == second.output
    assert first.output["artifact_uri"] == second.output["artifact_uri"]
    assert first.output["row_digest"].startswith("sha256:")
    assert first.output["normalized_source_digest"].startswith("sha256:")
    assert first.output["environment_digest"].startswith("sha256:")
    assert first.output["execution_status"] == "NOT_EXECUTED"
    assert first.output["assurance"] == "UNVERIFIED"
    assert first.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert first.output["normalized_source"].endswith("\n")


def test_materialization_preserves_environment_and_preprocessing(
    tmp_path: Path,
) -> None:
    adapter = _adapter(tmp_path)

    result = adapter.invoke(
        CapabilityRequest(
            capability_id="dataset.formal.materialize",
            input=_minif2f_request(),
        )
    )

    assert result.output["normalized_source"] == (
        "import Mathlib\ntheorem mathd_algebra_1 : (1 : Nat) = 1 := by\n  rfl\n"
    )
    assert result.output["environment"] == _environment()
    assert [item["operation"] for item in result.output["preprocessing"]] == [
        "NORMALIZE_NEWLINES",
        "TRIM_TRAILING_WHITESPACE",
        "ENSURE_FINAL_NEWLINE",
    ]
    assert [item["code"] for item in result.output["diagnostics"]] == [
        "EXECUTION_NOT_REQUESTED"
    ]


def test_incompatible_environment_has_explicit_diagnostics(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    payload = _proofnet_request()
    assert isinstance(payload["environment"], dict)
    payload["environment"] = {
        **payload["environment"],
        "lean_version": "3.51.1",
        "mathlib_revision": "legacy-mathlib-revision",
        "project_files": [],
    }

    result = adapter.invoke(
        CapabilityRequest(
            capability_id="dataset.formal.materialize",
            input=payload,
        )
    )

    assert {item["code"] for item in result.output["diagnostics"]} == {
        "EXECUTION_NOT_REQUESTED",
        "LEAN_VERSION_NOT_PINNED_RUNTIME",
        "MATHLIB_REVISION_NOT_PINNED_RUNTIME",
        "PROJECT_FILES_UNDECLARED",
    }


def test_expected_row_digest_rejects_changed_content(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    payload = _minif2f_request()
    payload["expected_row_digest"] = "sha256:" + "0" * 64

    with pytest.raises(CapabilityInvocationError) as exc_info:
        adapter.invoke(
            CapabilityRequest(
                capability_id="dataset.formal.materialize",
                input=payload,
            )
        )

    assert exc_info.value.diagnostic.code == "FORMAL_DATASET_ROW_DIGEST_MISMATCH"


def test_artifact_tampering_is_detected_by_store(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    result = adapter.invoke(
        CapabilityRequest(
            capability_id="dataset.formal.materialize",
            input=_proofnet_request(),
        )
    )
    stored = adapter.store.get(result.output["artifact_uri"])

    assert stored.payload["row_digest"] == result.output["row_digest"]
    assert stored.payload["environment_digest"] == result.output["environment_digest"]
