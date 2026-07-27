"""Deterministic pytest collection partitions for CI."""

from __future__ import annotations

import hashlib
from typing import Protocol

import pytest


class _NodeItem(Protocol):
    @property
    def nodeid(self) -> str: ...


def shard_for_node(nodeid: str, shard_count: int) -> int:
    """Map a pytest node ID to a stable zero-based shard."""

    digest = hashlib.sha256(nodeid.encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big") % shard_count


def partition_items[ItemT: _NodeItem](
    items: list[ItemT],
    *,
    shard_count: int,
    shard_index: int,
) -> tuple[list[ItemT], list[ItemT]]:
    """Return selected and deselected items for one stable shard."""

    selected: list[ItemT] = []
    deselected: list[ItemT] = []
    for item in items:
        destination = (
            selected
            if shard_for_node(item.nodeid, shard_count) == shard_index
            else deselected
        )
        destination.append(item)
    return selected, deselected


def validate_shard(shard_count: int, shard_index: int) -> None:
    """Reject invalid shard coordinates before changing collection."""

    if shard_count < 1:
        raise pytest.UsageError("--jacobian-shard-count must be at least 1")
    if not 0 <= shard_index < shard_count:
        raise pytest.UsageError(
            "--jacobian-shard-index must be between 0 and shard count - 1"
        )
