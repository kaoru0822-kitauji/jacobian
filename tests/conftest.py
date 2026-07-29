"""Suite-wide pytest conventions."""

import os
import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from filelock import FileLock

from jacobian.runtime import CheckerAuthorityMode, create_runtime
from jacobian.runtime.bootstrap import bootstrap_services
from jacobian.runtime.config import RuntimeOptions
from jacobian.runtime.model import JacobianRuntime
from tests.helpers.runtime import (
    CapabilityTestServices,
    open_capability_test_services,
)


def _freeze_runtime_store(root: Path) -> None:
    """Checkpoint the template database and remove its volatile WAL files."""

    database = root / "metadata.sqlite3"
    connection = sqlite3.connect(database, timeout=30)
    try:
        checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if checkpoint is None or checkpoint[0] != 0:
            raise RuntimeError(
                f"could not checkpoint runtime store template: {checkpoint!r}"
            )
        journal_mode = connection.execute("PRAGMA journal_mode = DELETE").fetchone()
        if journal_mode is None or journal_mode[0].casefold() != "delete":
            raise RuntimeError(
                "could not switch runtime store template to a stable journal mode"
            )
    finally:
        connection.close()

    volatile_paths = (
        database.with_name(f"{database.name}-wal"),
        database.with_name(f"{database.name}-shm"),
    )
    remaining = [path.name for path in volatile_paths if path.exists()]
    if remaining:
        raise RuntimeError(
            f"runtime store template still has volatile SQLite files: {remaining}"
        )


def _shared_worker_template(
    tmp_path_factory: pytest.TempPathFactory,
    request: pytest.FixtureRequest,
    name: str,
) -> tuple[Path, FileLock] | None:
    """Return one xdist-run-scoped template path and its construction lock."""

    worker = getattr(request.config, "workerinput", None)
    if not isinstance(worker, dict):
        return None
    run_id = worker.get("testrunuid")
    if not isinstance(run_id, str) or not run_id:
        raise RuntimeError("xdist worker did not provide a test-run identity")
    root = tmp_path_factory.getbasetemp().parent / f"{name}-{run_id}"
    return root, FileLock(root.with_suffix(".lock"))


@pytest.fixture(scope="session")
def core_services_store_template(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Build only the capability-independent service descriptors once."""

    template = tmp_path_factory.mktemp("core-services-store-template")
    core = bootstrap_services(template, RuntimeOptions())
    core.close()
    _freeze_runtime_store(template)
    return template


@pytest.fixture
def initialized_core_services_store(
    tmp_path: Path,
    core_services_store_template: Path,
) -> None:
    """Seed a test root without assembling the mathematical portfolio."""

    shutil.copytree(core_services_store_template, tmp_path, dirs_exist_ok=True)


@pytest.fixture(scope="session")
def runtime_store_template(
    tmp_path_factory: pytest.TempPathFactory,
    request: pytest.FixtureRequest,
) -> Path:
    """Build immutable core descriptors once per test run."""

    shared = _shared_worker_template(
        tmp_path_factory,
        request,
        "runtime-store-template",
    )
    if shared is None:
        template = tmp_path_factory.mktemp("runtime-store-template")
        runtime = create_runtime(template)
        runtime.close()
        _freeze_runtime_store(template)
        return template

    template, lock = shared
    ready = template / ".ready"
    with lock:
        if not ready.exists():
            if template.exists():
                raise RuntimeError(
                    f"incomplete shared runtime template exists at {template}"
                )
            runtime = create_runtime(template)
            runtime.close()
            _freeze_runtime_store(template)
            ready.touch()
    return template


@pytest.fixture(scope="session")
def runtime_store_template_with_references(
    tmp_path_factory: pytest.TempPathFactory,
    request: pytest.FixtureRequest,
    runtime_store_template: Path,
) -> Path:
    """Build one test-run store with authorized references installed."""

    shared = _shared_worker_template(
        tmp_path_factory,
        request,
        "runtime-store-template-with-references",
    )
    if shared is None:
        template = tmp_path_factory.mktemp("runtime-store-template-with-references")
        shutil.copytree(runtime_store_template, template, dirs_exist_ok=True)
        runtime = create_runtime(
            template,
            checker_authority=CheckerAuthorityMode.INSTALL_BUNDLED,
        )
        runtime.close()
        _freeze_runtime_store(template)
        return template

    template, lock = shared
    ready = template / ".ready"
    with lock:
        if not ready.exists():
            if template.exists():
                raise RuntimeError(
                    f"incomplete shared reference template exists at {template}"
                )
            shutil.copytree(runtime_store_template, template)
            runtime = create_runtime(
                template,
                checker_authority=CheckerAuthorityMode.INSTALL_BUNDLED,
            )
            runtime.close()
            _freeze_runtime_store(template)
            ready.touch()
    return template


@pytest.fixture
def initialized_runtime_store(
    tmp_path: Path,
    runtime_store_template: Path,
) -> None:
    """Seed an isolated test root with the process's core descriptor snapshot."""

    shutil.copytree(runtime_store_template, tmp_path, dirs_exist_ok=True)


@pytest.fixture
def initialized_runtime_store_with_references(
    tmp_path: Path,
    runtime_store_template_with_references: Path,
) -> None:
    """Seed an isolated test root that already includes authorized references."""

    shutil.copytree(
        runtime_store_template_with_references,
        tmp_path,
        dirs_exist_ok=True,
    )


@pytest.fixture
def runtime(
    tmp_path: Path, initialized_runtime_store: None
) -> Iterator[JacobianRuntime]:
    """Attach a runtime to a per-test copy of the core descriptor snapshot."""

    _ = initialized_runtime_store
    runtime = create_runtime(tmp_path)
    yield runtime
    runtime.close()


@pytest.fixture
def runtime_with_references(
    tmp_path: Path,
    initialized_runtime_store_with_references: None,
) -> Iterator[JacobianRuntime]:
    """Attach a runtime to a per-test copy that already has authorized references."""

    _ = initialized_runtime_store_with_references
    runtime = create_runtime(
        tmp_path,
        checker_authority=CheckerAuthorityMode.HYDRATE_EXISTING,
    )
    yield runtime
    runtime.close()


@pytest.fixture
def complete_runtime_with_references(
    runtime_with_references: JacobianRuntime,
) -> JacobianRuntime:
    """Name the expensive, fully assembled runtime explicitly at call sites."""

    return runtime_with_references


@pytest.fixture
def capability_core_services(
    tmp_path: Path,
    initialized_core_services_store: None,
) -> Iterator[CapabilityTestServices]:
    """Open only the services required by capability-service integration tests."""

    _ = initialized_core_services_store
    with open_capability_test_services(tmp_path) as services:
        yield services


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Reject unsafe parallel Lean execution on controllers and xdist workers."""

    workers = config.getoption("numprocesses", default=None)
    under_xdist = hasattr(config, "workerinput") or bool(
        os.environ.get("PYTEST_XDIST_WORKER")
    )
    parallel = under_xdist or workers not in (None, 0, "0")
    if not parallel:
        return
    lean_items = [
        item.nodeid for item in items if item.get_closest_marker("lean_runtime")
    ]
    if not lean_items:
        return
    sample = ", ".join(lean_items[:3])
    message = (
        "Lean runtime tests cannot run under pytest-xdist. "
        "Use `make test` for the non-Lean suite or `make test-lean` "
        f"for serial Lean validation. Selected Lean tests include: {sample}"
    )
    if under_xdist:
        # UsageError on workers only kills the worker; exit so the controller fails closed.
        pytest.exit(message, returncode=4)
    raise pytest.UsageError(message)
