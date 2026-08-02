"""Pinned Harbor task digest and provenance calculation."""

from __future__ import annotations

from pathlib import Path


class HarborDigestError(ValueError):
    """The pinned Harbor runtime cannot calculate a task digest."""


def task_digest(task_dir: Path) -> str:
    """Return Harbor's native checksum for one task directory.

    The import is intentionally lazy: registry and topology checks remain
    usable without Harbor, while every digest caller gets the same Task model
    and therefore the same checksum semantics.
    """

    try:
        from harbor.models.task.task import Task
    except (ImportError, ModuleNotFoundError) as exc:
        raise HarborDigestError(
            "Harbor is required to compute task digests; use the pinned Harbor runner"
        ) from exc
    return str(Task(task_dir, disable_verification=True).checksum)


__all__ = ["HarborDigestError", "task_digest"]
