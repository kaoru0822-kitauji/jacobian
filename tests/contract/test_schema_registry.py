from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.schema_registry import SchemaRegistry, SchemaRegistryError
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
