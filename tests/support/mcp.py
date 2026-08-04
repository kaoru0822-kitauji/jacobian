"""Legacy MCP server fixture for tests unrelated to reasoning enforcement."""

from __future__ import annotations

from typing import Any

from jacobian.adapters.mcp.server import create_server as _create_server


def create_legacy_server(*args: Any, **kwargs: Any) -> Any:
    kwargs.setdefault("reasoning_log_mode", "OFF")
    return _create_server(*args, **kwargs)


__all__ = ["create_legacy_server"]
