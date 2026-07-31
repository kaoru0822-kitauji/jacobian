"""Experiment service errors."""

from __future__ import annotations


class ExperimentError(RuntimeError):
    """A requested experiment is missing or invalid."""


class ExperimentCorruptionError(ExperimentError):
    """A persisted experiment snapshot cannot be reconstructed safely."""

    def __init__(self, corruption: object) -> None:
        self.corruption = corruption
        super().__init__(str(corruption))


class ExperimentNotFoundError(ExperimentError):
    """A requested enumeration experiment does not exist."""
