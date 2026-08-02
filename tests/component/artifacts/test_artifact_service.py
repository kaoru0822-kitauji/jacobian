from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.artifacts import ArtifactService, ArtifactValidationError
from jacobian.schema_registry import SchemaRegistry
from jacobian.storage.repository import ArtifactRepository


def test_artifact_put_validates_against_registered_json_schema(
    tmp_path: Path,
) -> None:
    store = ArtifactRepository(tmp_path)
    schemas = SchemaRegistry(store)
    schema_uri = schemas.register(
        name="example.strict-integer",
        version="1",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
        },
    )
    semantics_uri = store.register_descriptor(
        kind="semantics",
        name="example.strict-integer",
        version="1",
        definition={"description": "one integer"},
    )
    service = ArtifactService(store, schemas)

    with pytest.raises(ArtifactValidationError) as raised:
        service.put(
            schema_uri=schema_uri,
            semantics_uri=semantics_uri,
            payload={"value": "1"},
        )
    assert str(raised.value) == (
        "The artifact payload does not match its schema. Check the reference "
        "contract and retry with matching input."
    )
    assert '"1"' not in str(raised.value)

    artifact = service.put(
        schema_uri=schema_uri,
        semantics_uri=semantics_uri,
        payload={"value": 1},
    )
    assert store.get(artifact.artifact_uri).payload == {"value": 1}


def test_artifact_put_distinguishes_duplicate_parents_from_missing_descriptors(
    tmp_path: Path,
) -> None:
    store = ArtifactRepository(tmp_path)
    schemas = SchemaRegistry(store)
    schema_uri = schemas.register(
        name="example.parented-integer",
        version="1",
        schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
        },
    )
    semantics_uri = store.register_descriptor(
        kind="semantics",
        name="example.parented-integer",
        version="1",
        definition={},
    )
    parent = store.put(
        schema_uri=schema_uri,
        semantics_uri=semantics_uri,
        payload={"value": 1},
    )
    service = ArtifactService(store, schemas)

    with pytest.raises(
        ArtifactValidationError,
        match="Artifact parents must be unique",
    ):
        service.put(
            schema_uri=schema_uri,
            semantics_uri=semantics_uri,
            payload={"value": 2},
            parents=(parent.artifact_uri, parent.artifact_uri),
        )
