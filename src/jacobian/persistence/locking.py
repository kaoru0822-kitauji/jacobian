"""Cross-platform process locking retained for one persistence lifetime."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock


class PersistenceLock:
    """Own one reentrant cross-process lock file for a persistent resource."""

    def __init__(self, path: Path) -> None:
        self.path = path
        # Retain the FileLock object for the full owner lifetime. FileLock is
        # reentrant, and retaining it prevents garbage collection from
        # releasing an acquisition before the protected operation completes.
        self._lock = FileLock(path)

    @contextmanager
    def hold(self) -> Iterator[None]:
        """Hold the lock until the protected persistence operation completes."""

        with self._lock:
            yield
