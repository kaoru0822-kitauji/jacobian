"""Search service errors."""

from __future__ import annotations


class SearchError(RuntimeError):
    """A requested search experiment is missing or invalid."""


class _SearchBudgetExhaustedError(SearchError):
    """The durable wall-clock budget was exhausted between checkpoints."""
