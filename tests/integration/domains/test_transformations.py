from __future__ import annotations

import pytest

from jacobian.runtime.model import JacobianRuntime


@pytest.fixture
def runtime(runtime_with_references: JacobianRuntime) -> JacobianRuntime:
    return runtime_with_references


@pytest.mark.subprocess
def test_matrix_representation_change_is_independently_verified(
    runtime,
) -> None:
    reference = runtime.portfolio.references["matrices"]
    source = runtime.core.artifacts.put(
        schema_uri=reference.candidate_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={
            "rows": 2,
            "cols": 2,
            "entries": [["1", "2"], ["3", "4"]],
        },
    )

    applied = runtime.services.transformations.apply(
        source_uri=source.artifact_uri,
        plugin_id=reference.plugin_id,
        target_schema_uri=reference.representation_schema_uris["row_major"],
        target_semantics_uri=reference.representation_semantics_uris["row_major"],
        requested_relation="EQUIVALENT",
        wall_seconds=30,
    )

    assert applied.transformation_uri is not None
    assert applied.result.assurance.verification.value == "UNVERIFIED"
    verified = runtime.services.verification.verify_transformation(
        transformation_uri=applied.transformation_uri,
    )
    assert verified.conclusion.value == "TRUE"
    assert verified.assurance.verification.value == "VERIFIED"
    assert (
        verified.assurance.checker_id
        == reference.transformation_checker_ids["matrix.row_major"]
    )


def test_transformation_target_rebinding_fails_closed(runtime) -> None:
    reference = runtime.portfolio.references["matrices"]
    source = runtime.core.artifacts.put(
        schema_uri=reference.candidate_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={"rows": 1, "cols": 1, "entries": [["1"]]},
    )
    applied = runtime.services.transformations.apply(
        source_uri=source.artifact_uri,
        plugin_id=reference.plugin_id,
        target_schema_uri=reference.representation_schema_uris["row_major"],
        target_semantics_uri=reference.representation_semantics_uris["row_major"],
        requested_relation="EQUIVALENT",
        wall_seconds=30,
    )
    assert applied.transformation_uri is not None
    transformation = runtime.core.store.get(applied.transformation_uri)
    replacement = runtime.core.artifacts.put(
        schema_uri=reference.representation_schema_uris["row_major"],
        semantics_uri=reference.representation_semantics_uris["row_major"],
        payload={"rows": 1, "cols": 1, "values": ["2"]},
    )
    rebound_payload = dict(transformation.payload)
    rebound_payload["target_uri"] = replacement.artifact_uri
    rebound = runtime.core.store.put(
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

    result = runtime.services.verification.verify_transformation(
        transformation_uri=rebound.artifact_uri
    )

    assert result.input.status.value == "REJECTED"
    assert result.conclusion.value == "UNKNOWN"
    assert result.assurance.verification.value == "UNVERIFIED"
    assert result.verification_record_uri is None


def test_transformation_relation_rebinding_fails_closed(runtime) -> None:
    reference = runtime.portfolio.references["matrices"]
    source = runtime.core.artifacts.put(
        schema_uri=reference.candidate_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={"rows": 1, "cols": 2, "entries": [["1", "2"]]},
    )
    applied = runtime.services.transformations.apply(
        source_uri=source.artifact_uri,
        plugin_id=reference.plugin_id,
        target_schema_uri=reference.representation_schema_uris["row_major"],
        target_semantics_uri=reference.representation_semantics_uris["row_major"],
        requested_relation="EQUIVALENT",
        wall_seconds=30,
    )
    assert applied.transformation_uri is not None
    transformation = runtime.core.store.get(applied.transformation_uri)
    rebound_payload = dict(transformation.payload)
    rebound_payload["relation"] = "HEURISTIC"
    rebound = runtime.core.store.put(
        schema_uri=transformation.manifest.schema_uri,
        semantics_uri=transformation.manifest.semantics_uri,
        payload=rebound_payload,
        parents=transformation.manifest.parents,
        summary="adversarial relation rebinding",
    )

    result = runtime.services.verification.verify_transformation(
        transformation_uri=rebound.artifact_uri
    )

    assert result.input.status.value == "REJECTED"
    assert result.conclusion.value == "UNKNOWN"
    assert result.assurance.verification.value == "UNVERIFIED"
    assert result.verification_record_uri is None


def test_transformation_obligation_tampering_fails_closed(
    runtime,
) -> None:
    reference = runtime.portfolio.references["matrices"]
    source = runtime.core.artifacts.put(
        schema_uri=reference.candidate_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={"rows": 1, "cols": 2, "entries": [["1", "2"]]},
    )
    applied = runtime.services.transformations.apply(
        source_uri=source.artifact_uri,
        plugin_id=reference.plugin_id,
        target_schema_uri=reference.representation_schema_uris["row_major"],
        target_semantics_uri=reference.representation_semantics_uris["row_major"],
        requested_relation="EQUIVALENT",
        wall_seconds=30,
    )
    assert applied.transformation_uri is not None
    transformation = runtime.core.store.get(applied.transformation_uri)
    tampered_payload = dict(transformation.payload)
    tampered_payload["obligation"] = {"rows": 999, "cols": 999}
    tampered = runtime.core.store.put(
        schema_uri=transformation.manifest.schema_uri,
        semantics_uri=transformation.manifest.semantics_uri,
        payload=tampered_payload,
        parents=transformation.manifest.parents,
        summary="adversarial obligation tampering",
    )

    result = runtime.services.verification.verify_transformation(
        transformation_uri=tampered.artifact_uri
    )

    assert result.input.status.value == "REJECTED"
    assert result.conclusion.value == "UNKNOWN"
    assert result.assurance.verification.value == "UNVERIFIED"
    assert result.verification_record_uri is None
