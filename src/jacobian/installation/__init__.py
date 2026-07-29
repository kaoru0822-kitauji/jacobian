"""Shared capability-installation contracts."""

from jacobian.installation.context import InstallationContext
from jacobian.installation.result import InstallationDiagnostic, InstallationResult

__all__ = [
    "InstallationContext",
    "InstallationDiagnostic",
    "InstallationResult",
]
