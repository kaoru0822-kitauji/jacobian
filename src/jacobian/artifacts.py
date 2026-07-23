"""Validated public artifact operations."""

from __future__ import annotations

from typing import Any

from jacobian.contracts.artifacts import ArtifactPutResult
from jacobian.schema_registry import SchemaRegistry, SchemaRegistryError
from jacobian.store import ArtifactStore, StoreError


class ArtifactValidationError(ValueError):
    """Artifact input failed schema, semantics, or canonical validation."""


class ArtifactService:
    """Validate domain payloads before committing immutable artifacts."""

    def __init__(self, store: ArtifactStore, schemas: SchemaRegistry) -> None:
        self.store = store
        self.schemas = schemas

    def put(
        self,
        *,
        schema_uri: str,
        semantics_uri: str,
        payload: Any,
        parents: tuple[str, ...] | list[str] = (),
        summary: str = "",
    ) -> ArtifactPutResult:
        """Validate and store one artifact under its schema and semantics."""

        try:
            normalized = self.schemas.validate(schema_uri, payload)
            self.store.get_descriptor(
                semantics_uri,
                expected_kind="semantics",
            )
            return self.store.put(
                schema_uri=schema_uri,
                semantics_uri=semantics_uri,
                payload=normalized,
                parents=parents,
                summary=summary,
            )
        except (SchemaRegistryError, StoreError, ValueError) as exc:
            raise ArtifactValidationError(str(exc)) from exc
