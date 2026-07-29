from __future__ import annotations

from typing import Any

print("module import diagnostic")


def echo(request: dict[str, Any]) -> dict[str, Any]:
    return {"seen": request}
