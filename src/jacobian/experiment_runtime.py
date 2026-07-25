"""Shared runtime primitives for durable experiment services."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path


def open_experiment_database(path: str | Path) -> sqlite3.Connection:
    """Open the shared SQLite store with the experiment safety defaults."""

    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def new_experiment_uri() -> str:
    """Return a new opaque experiment identity."""

    return f"experiment://{uuid.uuid4().hex}"
