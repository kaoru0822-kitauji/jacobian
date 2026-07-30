"""Shared contracts for source acquisition and extraction handlers."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from ..models import SourceRecord, TaskSpec


class SourceHandler(Protocol):
    """Acquire one pinned source and yield validated task specifications."""

    source_id: str

    def acquire(
        self,
        source: SourceRecord,
        *,
        cache_dir: Path,
        offline: bool,
    ) -> Path: ...

    def iter_specs(
        self,
        source: SourceRecord,
        snapshot: Path,
        *,
        full: bool,
    ) -> Iterator[TaskSpec]: ...
