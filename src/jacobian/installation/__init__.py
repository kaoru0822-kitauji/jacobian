"""Shared capability-installation contracts."""

from jacobian.installation.context import (
    InstallationContext,
    create_installation_context,
)
from jacobian.installation.result import InstallationDiagnostic, InstallationResult

__all__ = [
    "InstallationContext",
    "InstallationDiagnostic",
    "InstallationResult",
    "create_installation_context",
]
