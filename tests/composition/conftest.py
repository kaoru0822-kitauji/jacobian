"""Explicitly expensive complete-runtime fixtures.

These names make complete materialization and attachment visible at every call
site.  The session templates are immutable; every runtime object and state
directory remains function-scoped and test-owned.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from filelock import FileLock

from jacobian.runtime import CheckerAuthorityMode, create_runtime
from jacobian.runtime.model import JacobianRuntime
from tests.support.services import DomainTestServices, open_domain_services
from tests.support.state import (
    copy_template,
    publish_template,
    quiesce_sqlite_template,
    worker_template_target,
)


def _template_target(
    tmp_path_factory: pytest.TempPathFactory,
    request: pytest.FixtureRequest,
    name: str,
) -> tuple[Path, FileLock | None]:
    shared = worker_template_target(tmp_path_factory, request, name)
    if shared is not None:
        return shared
    base = tmp_path_factory.getbasetemp()
    target = Path(base).parent / f"{name}-{Path(base).name}"
    return target, None


@pytest.fixture(scope="session")
def complete_portfolio_template(
    tmp_path_factory: pytest.TempPathFactory,
    request: pytest.FixtureRequest,
) -> Path:
    """Publish one immutable fully materialized portfolio snapshot."""

    target, lock = _template_target(
        tmp_path_factory,
        request,
        "complete-portfolio-template",
    )

    def build(staging: Path) -> None:
        runtime = create_runtime(staging)
        runtime.close()
        quiesce_sqlite_template(staging)

    return publish_template(target, build, lock=lock)


@pytest.fixture(scope="session")
def authorized_portfolio_template(
    tmp_path_factory: pytest.TempPathFactory,
    request: pytest.FixtureRequest,
) -> Path:
    """Publish one immutable snapshot with bundled checker authority."""

    target, lock = _template_target(
        tmp_path_factory,
        request,
        "authorized-portfolio-template",
    )

    def build(staging: Path) -> None:
        runtime = create_runtime(
            staging,
            checker_authority=CheckerAuthorityMode.INSTALL_BUNDLED,
        )
        runtime.close()
        quiesce_sqlite_template(staging)

    return publish_template(target, build, lock=lock)


@pytest.fixture
def fresh_complete_runtime(
    tmp_path: Path,
) -> Iterator[JacobianRuntime]:
    """Materialize a complete runtime from an empty test-owned state root."""

    runtime = create_runtime(tmp_path / "state")
    try:
        yield runtime
    finally:
        runtime.close()


@pytest.fixture
def attached_complete_runtime(
    tmp_path: Path,
    complete_portfolio_template: Path,
) -> Iterator[JacobianRuntime]:
    """Attach a complete runtime to a private copy of its immutable template."""

    state = copy_template(complete_portfolio_template, tmp_path / "state")
    runtime = create_runtime(state)
    try:
        yield runtime
    finally:
        runtime.close()


@pytest.fixture
def authorized_complete_runtime(
    tmp_path: Path,
    authorized_portfolio_template: Path,
) -> Iterator[JacobianRuntime]:
    """Attach a runtime to a private, already-authorized portfolio snapshot."""

    state = copy_template(authorized_portfolio_template, tmp_path / "state")
    runtime = create_runtime(
        state,
        checker_authority=CheckerAuthorityMode.HYDRATE_EXISTING,
    )
    try:
        yield runtime
    finally:
        runtime.close()


@pytest.fixture
def capability_core_services(tmp_path: Path) -> Iterator[DomainTestServices]:
    """Open production core/application seams for service-level composition tests."""

    with open_domain_services(tmp_path / "state") as services:
        yield services
