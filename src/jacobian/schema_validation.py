"""Process-wide reuse for exact operator-installed JSON Schema checks."""

from __future__ import annotations

from functools import lru_cache

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from jacobian.canonical import loads_strict_json

_META_SCHEMA_VALIDATOR = Draft202012Validator(
    schema=Draft202012Validator.META_SCHEMA,
    format_checker=Draft202012Validator.FORMAT_CHECKER,
)


@lru_cache(maxsize=1024)
def check_draft202012_schema(canonical_schema: bytes) -> None:
    """Check one canonical schema once per process and bounded working set."""

    schema = loads_strict_json(canonical_schema)
    for error in _META_SCHEMA_VALIDATOR.iter_errors(schema):
        raise SchemaError.create_from(error)
