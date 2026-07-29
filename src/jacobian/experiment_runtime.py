"""Shared runtime primitives for durable experiment services."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from types import TracebackType
from typing import Literal


class _ClosingConnection(sqlite3.Connection):
    """SQLite connection whose context manager also releases the handle."""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        try:
            super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()
        return False


def open_experiment_database(path: str | Path) -> sqlite3.Connection:
    """Open the shared SQLite store with the experiment safety defaults."""

    connection = sqlite3.connect(path, timeout=30, factory=_ClosingConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def new_experiment_uri() -> str:
    """Return a new opaque experiment identity."""

    return f"experiment://{uuid.uuid4().hex}"
