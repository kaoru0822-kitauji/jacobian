"""Narrow, explicitly owned runtime graphs for integration tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from jacobian.installation.context import InstallationContext
from jacobian.runtime.bootstrap import bootstrap_services
from jacobian.runtime.config import CheckerAuthorityMode, RuntimeOptions
from jacobian.runtime.services import CoreServices
from jacobian.verification import VerificationService


@dataclass(frozen=True, slots=True)
class CapabilityTestServices:
    """Services and installation boundary needed by capability tests."""

    core: CoreServices
    installation: InstallationContext


@contextmanager
def open_capability_test_services(
    root: Path,
    *,
    checker_authority: CheckerAuthorityMode = CheckerAuthorityMode.NONE,
) -> Iterator[CapabilityTestServices]:
    """Open a capability service graph without assembling the built-in portfolio."""

    options = RuntimeOptions(checker_authority=checker_authority)
    core = bootstrap_services(root, options)
    try:
        installation = InstallationContext(
            store=core.store,
            schemas=core.schemas,
            artifacts=core.artifacts,
            capabilities=core.capabilities,
            checkers=core.checkers,
            verification=VerificationService(core.store, core.checkers),
            operations=core.operations,
            checker_authority=options.checker_authority,
            register_capability=core.capabilities.register,
        )
        yield CapabilityTestServices(core=core, installation=installation)
    finally:
        core.close()
