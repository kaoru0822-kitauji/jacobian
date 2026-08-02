"""Errors shared by capability registration and invocation boundaries."""

from __future__ import annotations

from jacobian.contracts.capabilities import CapabilityDiagnostic


class CapabilityError(RuntimeError):
    """A capability descriptor, request, or assurance boundary is invalid."""


class PayloadValidationError(CapabilityError):
    """Structured descriptor-schema failure safe for public diagnostics."""

    def __init__(
        self,
        message: str,
        *,
        path: str,
        actual_type: str,
        expected: str,
    ) -> None:
        super().__init__(message)
        self.path = path
        self.actual_type = actual_type
        self.expected = expected


class CapabilityDiscoveryCursorError(ValueError):
    """A continuation cursor does not belong to the filtered result."""


class CapabilityInvocationError(RuntimeError):
    """An expected adapter failure that is safe to return to a model."""

    def __init__(self, diagnostic: CapabilityDiagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


__all__ = [
    "CapabilityDiscoveryCursorError",
    "CapabilityError",
    "CapabilityInvocationError",
    "PayloadValidationError",
]
