"""Shared fixtures for Harbor tooling tests.

One fixture resource is provided:

* ``synthetic_harbor_root`` — isolated filesystem root and deterministic profile.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.tooling.harbor_suite_support import patch_harbor_root


@pytest.fixture
def synthetic_harbor_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect harbor_suite.ROOT to tmp_path and install a synthetic profile."""
    patch_harbor_root(monkeypatch, tmp_path)
