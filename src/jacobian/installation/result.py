"""Shared typed results from capability installation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InstallationDiagnostic:
    """One inspectable omission or non-fatal installation observation."""

    code: str
    component_id: str
    stage: str
    message: str


@dataclass(frozen=True, slots=True)
class InstallationResult[InstalledT]:
    """Installed value plus non-conclusive diagnostics."""

    installed: InstalledT
    diagnostics: tuple[InstallationDiagnostic, ...]
