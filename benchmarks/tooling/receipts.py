"""Canonical serialization helpers for provenance-bound benchmark receipts."""

from __future__ import annotations

import hashlib
import json


def canonical_json(value: object) -> bytes:
    """Serialize receipt content exactly once for producers and consumers."""

    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest_bytes(value: bytes) -> str:
    """Return the repository's tagged SHA-256 representation."""

    return "sha256:" + hashlib.sha256(value).hexdigest()


def receipt_digest(value: object) -> str:
    """Digest canonical receipt content."""

    return digest_bytes(canonical_json(value))


__all__ = ["canonical_json", "digest_bytes", "receipt_digest"]
