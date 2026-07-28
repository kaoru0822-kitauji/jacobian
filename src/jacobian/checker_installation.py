"""Install checker declarations through the operator-owned registry."""

from __future__ import annotations

from jacobian.checker_operations import CheckerOperation, InstalledChecker
from jacobian.registry import CheckerRegistry


class CheckerInstaller:
    """Translate typed checker operations into registry authorizations."""

    def __init__(
        self,
        registry: CheckerRegistry,
        *,
        bind_existing: bool | None = None,
    ) -> None:
        self.registry = registry
        self.bind_existing = (
            registry.bind_existing_when_omitted
            if bind_existing is None
            else bind_existing
        )

    def install(
        self,
        operation: CheckerOperation,
        *,
        authorize: bool,
    ) -> InstalledChecker:
        if authorize:
            registration = self.registry.authorize(
                name=operation.name,
                entrypoint=operation.entrypoint,
                evidence_kind=operation.evidence_kind,
                format_id=operation.format_id,
                format_version=operation.format_version,
                claim_schema_uris=operation.claim_schema_uris,
                semantics_uris=operation.semantics_uris,
                candidate_schema_uris=operation.candidate_schema_uris,
                target_schema_uris=operation.target_schema_uris,
                target_semantics_uris=operation.target_semantics_uris,
                provider_runtime=operation.provider_runtime,
                reason=operation.reason,
            )
            return InstalledChecker(
                operation=operation,
                checker_id=registration.checker_id,
            )
        if self.bind_existing:
            return InstalledChecker(
                operation=operation,
                checker_id=self.registry.bind_existing(
                    name=operation.name,
                    entrypoint=operation.entrypoint,
                    evidence_kind=operation.evidence_kind,
                    format_id=operation.format_id,
                    format_version=operation.format_version,
                    claim_schema_uris=operation.claim_schema_uris,
                    semantics_uris=operation.semantics_uris,
                    candidate_schema_uris=operation.candidate_schema_uris,
                    target_schema_uris=operation.target_schema_uris,
                    target_semantics_uris=operation.target_semantics_uris,
                    provider_runtime=operation.provider_runtime,
                ),
            )
        return InstalledChecker(operation=operation, checker_id=None)
