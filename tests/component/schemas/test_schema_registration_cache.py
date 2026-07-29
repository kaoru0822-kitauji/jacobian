from __future__ import annotations

from pathlib import Path

import pytest

import jacobian.schema_registry as schema_registry
from jacobian.schema_registry import SchemaRegistry, SchemaRegistryError
from jacobian.store import ArtifactStore


def test_existing_descriptor_skips_meta_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ArtifactStore(tmp_path)
    first = SchemaRegistry(store)
    schema = {"type": "object", "properties": {"value": {"type": "integer"}}}
    uri = first.register(name="component.cache", version="1", schema=schema)

    calls = 0
    original = schema_registry._validated_schema

    def count_validation(canonical_schema: bytes):
        nonlocal calls
        calls += 1
        return original(canonical_schema)

    monkeypatch.setattr(schema_registry, "_validated_schema", count_validation)
    second = SchemaRegistry(store)
    assert second.register(name="component.cache", version="1", schema=schema) == uri
    assert calls == 0
    store.close()


def test_new_invalid_duplicate_definition_still_validates(
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path)
    registry = SchemaRegistry(store)
    registry.register(
        name="component.invalid-duplicate",
        version="1",
        schema={"type": "object"},
    )

    with pytest.raises(SchemaRegistryError, match="invalid Draft"):
        registry.register(
            name="component.invalid-duplicate",
            version="1",
            schema={"type": 17},
        )
    store.close()
