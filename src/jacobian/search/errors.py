"""Search service errors."""

from __future__ import annotations


class SearchError(RuntimeError):
    """A requested search experiment is missing or invalid."""


class SearchCorruptionError(SearchError):
    """A persisted search record cannot be reconstructed safely."""

    def __init__(self, corruption: object) -> None:
        self.corruption = corruption
        super().__init__(str(corruption))


class _SearchBudgetExhaustedError(SearchError):
    """The durable wall-clock budget was exhausted between checkpoints."""
