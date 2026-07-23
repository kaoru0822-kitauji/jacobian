from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.artifacts import ArtifactService, ArtifactValidationError
from jacobian.schema_registry import SchemaRegistry
from jacobian.store import ArtifactStore


@pytest.mark.integration
@pytest.mark.contract
def test_artifact_put_validates_against_registered_json_schema(
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path)
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

    with pytest.raises(ArtifactValidationError):
        service.put(
            schema_uri=schema_uri,
            semantics_uri=semantics_uri,
            payload={"value": "1"},
        )

    artifact = service.put(
        schema_uri=schema_uri,
        semantics_uri=semantics_uri,
        payload={"value": 1},
    )
    assert store.get(artifact.artifact_uri).payload == {"value": 1}
