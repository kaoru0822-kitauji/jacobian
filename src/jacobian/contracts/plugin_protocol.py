"""Small shared metadata contract for untrusted plugin requests."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, StrictInt, StrictStr

from jacobian.contracts.results import ContractModel


class PluginRequestContext(ContractModel):
    """Protocol metadata common to all maintained plugin domains."""

    request_version: Literal["1"] | None = None
    profile: StrictStr | None = None
    seed: StrictInt | None = None
    bindings: dict[str, Any] = Field(default_factory=dict)


__all__ = ["PluginRequestContext"]
