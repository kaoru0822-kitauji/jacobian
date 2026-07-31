"""Fail-closed reconstruction of typed models from persisted JSON."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ValidationError

from jacobian.canonical import (
    CanonicalizationError,
    canonicalize_json,
    loads_strict_json,
)


class PersistenceCorruptionCode(StrEnum):
    """Stable classifications for invalid persisted model bytes."""

    INVALID_UTF8 = "INVALID_UTF8"
    INVALID_JSON = "INVALID_JSON"
    NON_CANONICAL_JSON = "NON_CANONICAL_JSON"
    INVALID_MODEL = "INVALID_MODEL"


class PersistenceCorruptionError(RuntimeError):
    """A persisted record cannot be reconstructed without guessing."""

    def __init__(
        self,
        *,
        record_kind: str,
        record_id: str,
        field: str,
        failure_code: PersistenceCorruptionCode,
    ) -> None:
        self.record_kind = record_kind
        self.record_id = record_id
        self.field = field
        self.failure_code = failure_code
        super().__init__(
            f"persisted {record_kind} {record_id} field {field} is invalid "
            f"({failure_code.value})"
        )


def decode_persisted_model[ModelT: BaseModel](
    model_type: type[ModelT],
    encoded: str | bytes | bytearray,
    *,
    record_kind: str,
    record_id: str,
    field: str,
) -> ModelT:
    """Decode canonical JSON and reconstruct one contract model.

    The context is supplied by the owning persistence adapter. Raw row values
    never enter the exception or diagnostic, and no repair or partial recovery
    is attempted.
    """

    raw = encoded.encode("utf-8") if isinstance(encoded, str) else bytes(encoded)
    try:
        payload = loads_strict_json(raw)
    except CanonicalizationError as exc:
        message = str(exc)
        code = (
            PersistenceCorruptionCode.INVALID_UTF8
            if "valid UTF-8" in message
            else PersistenceCorruptionCode.INVALID_JSON
        )
        raise PersistenceCorruptionError(
            record_kind=record_kind,
            record_id=record_id,
            field=field,
            failure_code=code,
        ) from exc

    try:
        canonical = canonicalize_json(payload)
    except CanonicalizationError as exc:
        raise PersistenceCorruptionError(
            record_kind=record_kind,
            record_id=record_id,
            field=field,
            failure_code=PersistenceCorruptionCode.INVALID_JSON,
        ) from exc
    if canonical != raw:
        raise PersistenceCorruptionError(
            record_kind=record_kind,
            record_id=record_id,
            field=field,
            failure_code=PersistenceCorruptionCode.NON_CANONICAL_JSON,
        )

    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        raise PersistenceCorruptionError(
            record_kind=record_kind,
            record_id=record_id,
            field=field,
            failure_code=PersistenceCorruptionCode.INVALID_MODEL,
        ) from exc


__all__ = [
    "PersistenceCorruptionCode",
    "PersistenceCorruptionError",
    "decode_persisted_model",
]
