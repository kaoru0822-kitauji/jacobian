"""A fail-closed checker useful as an unconfigured default."""

from __future__ import annotations

from typing import Any


def check(_request: dict[str, Any]) -> dict[str, Any]:
    return {
        "accepted": False,
        "conclusion": "UNKNOWN",
        "arithmetic": "SYMBOLIC",
        "method": "CHECKED_CERTIFICATE",
        "coverage": "NOT_APPLICABLE",
        "detail": "reject-all checker does not verify mathematical evidence",
    }
