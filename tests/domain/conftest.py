"""Fixtures for domain-owned capability tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.support.services import DomainTestServices, open_domain_services


@pytest.fixture
def domain_services(tmp_path: Path) -> Iterator[DomainTestServices]:
    """Open services and an installation context, with no built-in portfolio."""

    with open_domain_services(tmp_path / "state") as services:
        yield services
