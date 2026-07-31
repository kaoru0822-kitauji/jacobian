from __future__ import annotations

import pytest
from pydantic import StrictInt

from jacobian.canonical import canonicalize_json
from jacobian.contracts.results import ContractModel
from jacobian.persistence import (
    PersistenceCorruptionCode,
    PersistenceCorruptionError,
    decode_persisted_model,
)


class _PersistedRecord(ContractModel):
    value: StrictInt


def _decode(encoded: str | bytes) -> _PersistedRecord:
    return decode_persisted_model(
        _PersistedRecord,
        encoded,
        record_kind="test_record",
        record_id="record://one",
        field="payload_json",
    )


def test_decode_persisted_model_accepts_canonical_model() -> None:
    encoded = canonicalize_json({"value": 7})

    assert _decode(encoded).value == 7


@pytest.mark.parametrize(
    ("encoded", "code"),
    (
        (b'{"value":1,"value":2}', PersistenceCorruptionCode.INVALID_JSON),
        (b"{\xff", PersistenceCorruptionCode.INVALID_UTF8),
        (b'{"value": 1}', PersistenceCorruptionCode.NON_CANONICAL_JSON),
        (b'{"other":1}', PersistenceCorruptionCode.INVALID_MODEL),
    ),
)
def test_decode_persisted_model_classifies_corruption(
    encoded: bytes,
    code: PersistenceCorruptionCode,
) -> None:
    with pytest.raises(PersistenceCorruptionError) as raised:
        _decode(encoded)

    error = raised.value
    assert error.failure_code == code
    assert error.record_kind == "test_record"
    assert error.record_id == "record://one"
    assert "value" not in str(error)
