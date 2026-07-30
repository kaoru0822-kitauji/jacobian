"""Workspace service errors."""

from __future__ import annotations


class WorkspaceError(RuntimeError):
    """Base error for invalid or unavailable workspace operations."""


class WorkspaceNotFoundError(WorkspaceError):
    """The requested workspace, branch, revision, or item does not exist."""


class WorkspaceConflictError(WorkspaceError):
    """A write is based on a branch revision that is no longer current."""


class WorkspaceIdempotencyError(WorkspaceError):
    """An idempotency key was already accepted for another request."""


class WorkspaceReferenceError(WorkspaceError):
    """A workspace entry cites a missing or incompatible explicit reference."""
