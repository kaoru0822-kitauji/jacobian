"""Shared typing contracts for grouped atomic capability registrations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from jacobian.atomic_capabilities import AtomicServiceAdapter


class AdapterFactory(Protocol):
    def __call__(self, **kwargs: Any) -> AtomicServiceAdapter: ...


class SchemaBuilder(Protocol):
    def __call__(
        self,
        properties: dict[str, Any],
        *,
        required: tuple[str, ...],
    ) -> dict[str, Any]: ...
