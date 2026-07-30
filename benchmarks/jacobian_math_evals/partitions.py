"""Deterministic source-family partitions for contamination control."""

from __future__ import annotations

import hashlib
import re

from .models import SourceRecord, Split

FAMILY_ALIASES = (
    "minif2f",
    "putnambench",
    "proofnet",
    "ineqmath",
    "mathlibpr",
    "leantree",
    "reprover",
    "countermath",
    "leancat",
    "lean-workbook",
    "numinamath",
    "fate",
    "erdos90",
    "jacobian",
)


def source_family_key(source: SourceRecord) -> str:
    text = " ".join(
        (
            source.canonical_url,
            source.conjecture_name,
            source.artifacts,
        )
    ).lower()
    compact = re.sub(r"[^a-z0-9]+", "", text)
    for alias in FAMILY_ALIASES:
        if alias.replace("-", "") in compact:
            return alias
    host_path = re.sub(
        r"^https?://",
        "",
        source.canonical_url.rstrip("/").lower(),
    )
    return re.sub(r"[^a-z0-9]+", "-", host_path).strip("-")


def source_family_split(source: SourceRecord) -> Split:
    digest = hashlib.sha256(source_family_key(source).encode()).digest()
    bucket = int.from_bytes(digest[:4], "big") % 10
    if bucket < 6:
        return Split.TRAIN
    if bucket < 8:
        return Split.DEV
    return Split.TEST
