"""Typed declarations for operator-authorized checker implementations."""

from __future__ import annotations

from dataclasses import dataclass

from jacobian.contracts.capabilities import CapabilityProviderRuntime
from jacobian.contracts.checkers import EvidenceKind
from jacobian.contracts.results import ContractModel


@dataclass(frozen=True, slots=True)
class ExactReplayCheckerDeclaration:
    """Domain-owned declaration of an independently replayable exact result."""

    capability_id: str
    request_model: type[ContractModel]
    function: str
    format_id: str

    def __post_init__(self) -> None:
        for field, value in {
            "capability_id": self.capability_id,
            "function": self.function,
            "format_id": self.format_id,
        }.items():
            if not value.strip():
                raise ValueError(
                    f"exact replay checker declaration {field} must not be empty"
                )


@dataclass(frozen=True, slots=True)
class CheckerOperation:
    """One independently executable checker and its compatibility scope."""

    name: str
    entrypoint: str
    evidence_kind: EvidenceKind
    format_id: str
    format_version: str
    claim_schema_uris: tuple[str, ...]
    semantics_uris: tuple[str, ...]
    candidate_schema_uris: tuple[str, ...]
    reason: str
    target_schema_uris: tuple[str, ...] = ()
    target_semantics_uris: tuple[str, ...] = ()
    provider_runtime: CapabilityProviderRuntime | None = None

    def __post_init__(self) -> None:
        required_text = {
            "name": self.name,
            "entrypoint": self.entrypoint,
            "format_id": self.format_id,
            "format_version": self.format_version,
            "reason": self.reason,
        }
        for field, value in required_text.items():
            if not value.strip():
                raise ValueError(f"checker operation {field} must not be empty")
        if not self.claim_schema_uris:
            raise ValueError("checker operation must declare a claim schema")
        if not self.semantics_uris:
            raise ValueError("checker operation must declare semantics")


@dataclass(frozen=True, slots=True)
class InstalledChecker:
    """Authorization result for one checker operation."""

    operation: CheckerOperation
    checker_id: str | None

    @property
    def authorized(self) -> bool:
        return self.checker_id is not None

    def require_checker_id(self) -> str:
        if self.checker_id is None:
            raise ValueError("checker operation is not authorized")
        return self.checker_id
