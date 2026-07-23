"""Operator-owned, content-addressed JSON Schema registry."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.store import ArtifactStore, StoreError


class SchemaRegistryError(RuntimeError):
    """Schema registration or resolution failed."""


class SchemaValidationError(SchemaRegistryError):
    """A payload does not satisfy its registered schema."""


def _reject_external_references(value: Any) -> None:
    if isinstance(value, dict):
        for keyword in ("$ref", "$dynamicRef"):
            reference = value.get(keyword)
            if isinstance(reference, str) and not reference.startswith("#"):
                raise SchemaRegistryError(
                    "v0.2 schemas cannot resolve external or network references"
                )
        for nested in value.values():
            _reject_external_references(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_external_references(nested)


class SchemaRegistry:
    """Store and apply closed local JSON Schemas used by artifact contracts."""

    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    def register(self, *, name: str, version: str, schema: dict[str, Any]) -> str:
        """Register a schema after rejecting unsupported external references."""

        normalized = loads_strict_json(canonicalize_json(schema))
        _reject_external_references(normalized)
        try:
            Draft202012Validator.check_schema(normalized)
        except SchemaError as exc:
            raise SchemaRegistryError("invalid Draft 2020-12 JSON Schema") from exc
        return self.store.register_descriptor(
            kind="schema",
            name=name,
            version=version,
            definition=normalized,
        )

    def resolve(self, schema_uri: str) -> dict[str, Any]:
        """Load a previously registered schema definition."""

        try:
            descriptor = self.store.get_descriptor(
                schema_uri,
                expected_kind="schema",
            )
        except StoreError as exc:
            raise SchemaRegistryError(f"unregistered schema: {schema_uri}") from exc
        definition = descriptor.get("definition")
        if not isinstance(definition, dict):
            raise SchemaRegistryError("schema descriptor has no object definition")
        _reject_external_references(definition)
        return definition

    def validate(self, schema_uri: str, payload: Any) -> Any:
        """Validate and canonically normalize a payload."""

        normalized = loads_strict_json(canonicalize_json(payload))
        schema = self.resolve(schema_uri)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = sorted(
            validator.iter_errors(normalized),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
        if errors:
            first: ValidationError = errors[0]
            location = "/".join(str(part) for part in first.absolute_path) or "$"
            raise SchemaValidationError(f"{location}: {first.message}")
        return normalized
