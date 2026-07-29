"""Ownership and lifecycle for one Jacobian application runtime."""

from __future__ import annotations

from pathlib import Path

from jacobian.capabilities import CapabilityAdapter
from jacobian.implementation import cached_package_digests
from jacobian.installation.context import InstallationContext
from jacobian.runtime.bootstrap import bootstrap_services
from jacobian.runtime.config import RuntimeOptions
from jacobian.runtime.services import build_application_services


class RuntimeClosedError(RuntimeError):
    """An operation requires a live Jacobian runtime."""


class JacobianRuntime:
    """Own the explicit service graph and installed portfolio for one store."""

    def __init__(self, root: str | Path, options: RuntimeOptions) -> None:
        self._closed = False
        self.core = bootstrap_services(root, options)
        try:
            from jacobian.portfolio.assembler import PortfolioAssembler

            self.services = build_application_services(self.core)
            installation = self._installation_context(options)
            with (
                self.core.checkers.policy_transaction(),
                self.core.store.transaction(),
                cached_package_digests(),
            ):
                self.portfolio = PortfolioAssembler(installation).install(
                    self.services,
                    capability_adapter_entrypoints=(
                        options.capability_adapter_entrypoints
                    ),
                )
        except BaseException:
            self.core.close()
            self._closed = True
            raise

    def _installation_context(self, options: RuntimeOptions) -> InstallationContext:
        excluded = options.capability_exclusions

        def register(adapter: CapabilityAdapter) -> None:
            if adapter.descriptor.capability_id not in excluded:
                self.core.capabilities.register(adapter)

        return InstallationContext(
            store=self.core.store,
            schemas=self.core.schemas,
            artifacts=self.core.artifacts,
            capabilities=self.core.capabilities,
            checkers=self.core.checkers,
            verification=self.services.verification,
            operations=self.core.operations,
            checker_authority=options.checker_authority,
            register_capability=register,
        )

    def close(self) -> None:
        """Release every runtime-owned resource."""

        if self._closed:
            return
        self.core.close()
        self._closed = True

    def __enter__(self) -> JacobianRuntime:
        if self._closed:
            raise RuntimeClosedError("Jacobian runtime is closed")
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


__all__ = ["JacobianRuntime", "RuntimeClosedError"]
