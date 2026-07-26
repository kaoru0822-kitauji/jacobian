from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from jacobian.schema_registry import (
    SchemaRegistry,
    SchemaRegistryError,
    SchemaValidationError,
    model_schema,
)
from jacobian.store import ArtifactStore


class _CachedSchemaModel(BaseModel):
    value: int


@pytest.mark.contract
def test_cached_model_schema_returns_independent_copies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = model_schema(_CachedSchemaModel)
    first["title"] = "mutated"

    def unexpected_regeneration() -> dict[str, object]:
        pytest.fail("cached schema was regenerated")

    monkeypatch.setattr(
        _CachedSchemaModel,
        "model_json_schema",
        unexpected_regeneration,
    )
    second = model_schema(_CachedSchemaModel)

    assert second["title"] == "_CachedSchemaModel"


@pytest.mark.contract
def test_external_dynamic_reference_is_rejected(tmp_path: Path) -> None:
    registry = SchemaRegistry(ArtifactStore(tmp_path))

    with pytest.raises(SchemaRegistryError):
        registry.register(
            name="external-dynamic-ref",
            version="1",
            schema={"$dynamicRef": "https://example.test/schema"},
        )


@pytest.mark.contract
def test_schema_validator_cache_is_bound_to_canonical_schema(
    tmp_path: Path,
) -> None:
    registry = SchemaRegistry(ArtifactStore(tmp_path))
    integer_schema = registry.register(
        name="cache-binding",
        version="1",
        schema={"type": "object", "properties": {"value": {"type": "integer"}}},
    )
    string_schema = registry.register(
        name="cache-binding",
        version="2",
        schema={"type": "object", "properties": {"value": {"type": "string"}}},
    )

    registry.validate(integer_schema, {"value": 1})
    with pytest.raises(SchemaValidationError):
        registry.validate(string_schema, {"value": 1})
