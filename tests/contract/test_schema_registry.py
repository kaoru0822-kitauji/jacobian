from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.schema_registry import (
    SchemaRegistry,
    SchemaRegistryError,
    SchemaValidationError,
)
from jacobian.store import ArtifactStore


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
