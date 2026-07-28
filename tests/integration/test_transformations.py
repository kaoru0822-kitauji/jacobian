from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.kernel import JacobianKernel

pytestmark = pytest.mark.usefixtures("initialized_kernel_store_with_references")


@pytest.mark.subprocess
def test_matrix_representation_change_is_independently_verified(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    reference = kernel.references["matrices"]
    source = kernel.artifacts.put(
        schema_uri=reference.candidate_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={
            "rows": 2,
            "cols": 2,
            "entries": [["1", "2"], ["3", "4"]],
        },
    )

    applied = kernel.transformations.apply(
        source_uri=source.artifact_uri,
        plugin_id=reference.plugin_id,
        target_schema_uri=reference.representation_schema_uris["row_major"],
        target_semantics_uri=reference.representation_semantics_uris["row_major"],
        requested_relation="EQUIVALENT",
        wall_seconds=30,
    )

    assert applied.transformation_uri is not None
    assert applied.result.assurance.verification.value == "UNVERIFIED"
    verified = kernel.verification.verify_transformation(
        transformation_uri=applied.transformation_uri,
    )
    assert verified.conclusion.value == "TRUE"
    assert verified.assurance.verification.value == "VERIFIED"
    assert (
        verified.assurance.checker_id
        == reference.transformation_checker_ids["matrix.row_major"]
    )


def test_transformation_target_rebinding_fails_closed(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    reference = kernel.references["matrices"]
    source = kernel.artifacts.put(
        schema_uri=reference.candidate_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={"rows": 1, "cols": 1, "entries": [["1"]]},
    )
    applied = kernel.transformations.apply(
        source_uri=source.artifact_uri,
        plugin_id=reference.plugin_id,
        target_schema_uri=reference.representation_schema_uris["row_major"],
        target_semantics_uri=reference.representation_semantics_uris["row_major"],
        requested_relation="EQUIVALENT",
        wall_seconds=30,
    )
    assert applied.transformation_uri is not None
    transformation = kernel.store.get(applied.transformation_uri)
    replacement = kernel.artifacts.put(
        schema_uri=reference.representation_schema_uris["row_major"],
        semantics_uri=reference.representation_semantics_uris["row_major"],
        payload={"rows": 1, "cols": 1, "values": ["2"]},
    )
    rebound_payload = dict(transformation.payload)
    rebound_payload["target_uri"] = replacement.artifact_uri
    rebound = kernel.store.put(
        schema_uri=transformation.manifest.schema_uri,
        semantics_uri=transformation.manifest.semantics_uri,
        payload=rebound_payload,
        parents=(
            rebound_payload["claim_uri"],
            rebound_payload["source_uri"],
            replacement.artifact_uri,
        ),
        summary="adversarial target rebinding",
    )

    result = kernel.verification.verify_transformation(
        transformation_uri=rebound.artifact_uri
    )

    assert result.input.status.value == "REJECTED"
    assert result.conclusion.value == "UNKNOWN"
    assert result.assurance.verification.value == "UNVERIFIED"
    assert result.verification_record_uri is None


def test_transformation_relation_rebinding_fails_closed(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    reference = kernel.references["matrices"]
    source = kernel.artifacts.put(
        schema_uri=reference.candidate_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={"rows": 1, "cols": 2, "entries": [["1", "2"]]},
    )
    applied = kernel.transformations.apply(
        source_uri=source.artifact_uri,
        plugin_id=reference.plugin_id,
        target_schema_uri=reference.representation_schema_uris["row_major"],
        target_semantics_uri=reference.representation_semantics_uris["row_major"],
        requested_relation="EQUIVALENT",
        wall_seconds=30,
    )
    assert applied.transformation_uri is not None
    transformation = kernel.store.get(applied.transformation_uri)
    rebound_payload = dict(transformation.payload)
    rebound_payload["relation"] = "HEURISTIC"
    rebound = kernel.store.put(
        schema_uri=transformation.manifest.schema_uri,
        semantics_uri=transformation.manifest.semantics_uri,
        payload=rebound_payload,
        parents=transformation.manifest.parents,
        summary="adversarial relation rebinding",
    )

    result = kernel.verification.verify_transformation(
        transformation_uri=rebound.artifact_uri
    )

    assert result.input.status.value == "REJECTED"
    assert result.conclusion.value == "UNKNOWN"
    assert result.assurance.verification.value == "UNVERIFIED"
    assert result.verification_record_uri is None


def test_transformation_obligation_tampering_fails_closed(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    reference = kernel.references["matrices"]
    source = kernel.artifacts.put(
        schema_uri=reference.candidate_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={"rows": 1, "cols": 2, "entries": [["1", "2"]]},
    )
    applied = kernel.transformations.apply(
        source_uri=source.artifact_uri,
        plugin_id=reference.plugin_id,
        target_schema_uri=reference.representation_schema_uris["row_major"],
        target_semantics_uri=reference.representation_semantics_uris["row_major"],
        requested_relation="EQUIVALENT",
        wall_seconds=30,
    )
    assert applied.transformation_uri is not None
    transformation = kernel.store.get(applied.transformation_uri)
    tampered_payload = dict(transformation.payload)
    tampered_payload["obligation"] = {"rows": 999, "cols": 999}
    tampered = kernel.store.put(
        schema_uri=transformation.manifest.schema_uri,
        semantics_uri=transformation.manifest.semantics_uri,
        payload=tampered_payload,
        parents=transformation.manifest.parents,
        summary="adversarial obligation tampering",
    )

    result = kernel.verification.verify_transformation(
        transformation_uri=tampered.artifact_uri
    )

    assert result.input.status.value == "REJECTED"
    assert result.conclusion.value == "UNKNOWN"
    assert result.assurance.verification.value == "UNVERIFIED"
    assert result.verification_record_uri is None
