"""Experiment service errors."""

from __future__ import annotations


class ExperimentError(RuntimeError):
    """A requested experiment is missing or invalid."""


class ExperimentNotFoundError(ExperimentError):
    """A requested enumeration experiment does not exist."""
