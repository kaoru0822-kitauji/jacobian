from __future__ import annotations

from pathlib import Path
from typing import Self

import pytest
from pydantic import BaseModel, model_validator

from jacobian.schema_registry import (
    SchemaRegistry,
    SchemaRegistryError,
    SchemaValidationError,
    model_schema,
)
from jacobian.store import ArtifactStore


class _CachedSchemaModel(BaseModel):
    value: int


class _OrderedPair(BaseModel):
    first: int
    second: int

    @model_validator(mode="after")
    def require_order(self) -> Self:
        if self.first >= self.second:
            raise ValueError("pair must be ordered")
        return self


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


@pytest.mark.contract
def test_model_backed_schema_applies_cross_field_contracts(
    tmp_path: Path,
) -> None:
    registry = SchemaRegistry(ArtifactStore(tmp_path))
    schema_uri = registry.register_model(
        name="ordered-pair",
        version="1",
        model=_OrderedPair,
    )

    assert registry.validate(schema_uri, {"first": 1, "second": 2}) == {
        "first": 1,
        "second": 2,
    }
    with pytest.raises(SchemaValidationError, match="pair must be ordered"):
        registry.validate(schema_uri, {"first": 2, "second": 1})
