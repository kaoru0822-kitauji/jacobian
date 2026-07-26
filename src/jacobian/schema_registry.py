"""Operator-owned, content-addressed JSON Schema registry."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError
from pydantic import BaseModel

from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.store import ArtifactStore, StoreError


class SchemaRegistryError(RuntimeError):
    """Schema registration or resolution failed."""


class SchemaValidationError(SchemaRegistryError):
    """A payload does not satisfy its registered schema."""

    def __init__(
        self,
        message: str,
        *,
        path: str,
        required_field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.path = path
        self.required_field = required_field


@lru_cache(maxsize=128)
def _model_schema_bytes(model: type[BaseModel]) -> bytes:
    """Generate one canonical JSON Schema per Pydantic model and process."""

    return canonicalize_json(model.model_json_schema())


def model_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return a fresh copy of a cached Pydantic model JSON Schema."""

    return cast(dict[str, Any], loads_strict_json(_model_schema_bytes(model)))


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


@lru_cache(maxsize=128)
def _validated_schema(canonical_schema: bytes) -> Draft202012Validator:
    """Validate and compile one exact schema definition per process.

    Kernel construction registers the same contract schemas repeatedly across
    isolated stores, especially in tests. The canonical bytes are the cache
    key, so a changed schema cannot reuse an older validation result or
    validator. The returned validator is read-only during validation.
    """

    normalized = loads_strict_json(canonical_schema)
    _reject_external_references(normalized)
    try:
        Draft202012Validator.check_schema(normalized)
    except SchemaError as exc:
        raise SchemaRegistryError("invalid Draft 2020-12 JSON Schema") from exc
    return Draft202012Validator(normalized, format_checker=FormatChecker())


class SchemaRegistry:
    """Store and apply closed local JSON Schemas used by artifact contracts."""

    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    def register(self, *, name: str, version: str, schema: dict[str, Any]) -> str:
        """Register a schema after rejecting unsupported external references."""

        canonical_schema = canonicalize_json(schema)
        normalized = loads_strict_json(canonical_schema)
        _validated_schema(canonical_schema)
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
        validator = _validated_schema(canonicalize_json(schema))
        errors = sorted(
            validator.iter_errors(normalized),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
        if errors:
            first: ValidationError = errors[0]
            location = "/".join(str(part) for part in first.absolute_path) or "$"
            required_field = None
            if (
                first.validator == "required"
                and isinstance(first.validator_value, list)
                and isinstance(first.instance, dict)
            ):
                required_field = next(
                    (
                        field
                        for field in first.validator_value
                        if isinstance(field, str) and field not in first.instance
                    ),
                    None,
                )
            raise SchemaValidationError(
                f"{location}: {first.message}",
                path=location,
                required_field=required_field,
            )
        return normalized
