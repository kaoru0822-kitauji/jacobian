"""Behavioral tests for the shared provider-spike utility helpers."""

from __future__ import annotations

import hashlib
import json

from benchmarks.tooling.spike_utils import (
    canonical_json,
    sha256_bytes,
)


def test_sha256_bytes_matches_reference_implementation() -> None:
    payload = b"provider-spike-fixture"

    assert sha256_bytes(payload) == f"sha256:{hashlib.sha256(payload).hexdigest()}"


def test_sha256_bytes_prefixes_with_scheme() -> None:
    assert sha256_bytes(b"").startswith("sha256:")


def test_sha256_bytes_is_deterministic() -> None:
    assert sha256_bytes(b"abc") == sha256_bytes(b"abc")


def test_sha256_bytes_distinguishes_inputs() -> None:
    assert sha256_bytes(b"abc") != sha256_bytes(b"abd")


def test_canonical_json_sorts_keys() -> None:
    payload = {"b": 2, "a": 1}

    assert json.loads(canonical_json(payload)) == {"a": 1, "b": 2}


def test_canonical_json_uses_compact_separators() -> None:
    payload = {"a": 1, "b": 2}

    assert canonical_json(payload) == b'{"a":1,"b":2}\n'


def test_canonical_json_ensures_ascii() -> None:
    payload = {"key": "\u00e9"}

    assert canonical_json(payload) == b'{"key":"\\u00e9"}\n'


def test_canonical_json_appends_trailing_newline() -> None:
    assert canonical_json({"a": 1}).endswith(b"\n")


def test_canonical_json_is_deterministic_across_key_orders() -> None:
    assert canonical_json({"a": 1, "b": 2}) == canonical_json({"b": 2, "a": 1})


def test_canonical_json_encodes_nested_structures() -> None:
    payload = {"outer": {"inner": [3, 2, 1]}}

    assert canonical_json(payload) == b'{"outer":{"inner":[3,2,1]}}\n'
