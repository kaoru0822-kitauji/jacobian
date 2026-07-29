"""Cheap, suite-wide pytest conventions.

The root conftest is imported while pytest is collecting every test.  It must
therefore stay deliberately boring: no runtime construction, provider probes,
database connections, portfolio imports, or implementation modules belong
here.  Resource-owning fixtures live in the conftest below the tier that owns
the resource.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def isolated_state(tmp_path: Path) -> Path:
    """Return a fresh mutable state directory owned by one test."""

    state = tmp_path / "state"
    state.mkdir()
    return state


@pytest.fixture(scope="session")
def repository_root() -> Path:
    """Return the checkout root without importing application code."""

    return Path(__file__).resolve().parent.parent
