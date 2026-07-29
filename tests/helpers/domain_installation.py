"""Explicit domain-bundle installation for focused integration tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from jacobian.installation.context import InstallationContext
from jacobian.operation_installation import InstalledDomainBundle
from jacobian.operations import DomainBundle
from jacobian.runtime.config import CheckerAuthorityMode
from jacobian.runtime.services import CoreServices
from tests.helpers.runtime import open_capability_test_services


@dataclass(frozen=True, slots=True)
class DomainTestServices:
    """Core services plus the explicitly installed domain bundles."""

    core: CoreServices
    installation: InstallationContext
    domains: dict[str, InstalledDomainBundle]


@contextmanager
def open_domain_test_services(
    root: Path,
    *bundles: DomainBundle,
    checker_authority: CheckerAuthorityMode = CheckerAuthorityMode.NONE,
) -> Iterator[DomainTestServices]:
    """Open core services and install only the requested domain bundles."""

    with open_capability_test_services(
        root,
        checker_authority=checker_authority,
    ) as services:
        installation = services.installation
        installed: dict[str, InstalledDomainBundle] = {}
        for bundle in bundles:
            if bundle.domain_id in installed:
                raise ValueError(
                    f"domain bundle {bundle.domain_id!r} was requested more than once"
                )
            domain = installation.operations.install(bundle)
            installed[bundle.domain_id] = domain
            for adapter in domain.adapters:
                installation.register_capability(adapter)
        yield DomainTestServices(
            core=services.core,
            installation=installation,
            domains=installed,
        )
