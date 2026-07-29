from __future__ import annotations

from jacobian.contracts.workspaces import (
    WorkspaceOpenRequest,
    WorkspaceOpenResult,
)
from jacobian.runtime.model import JacobianRuntime


def _open(
    runtime: JacobianRuntime,
    *,
    key: str = "workspace-open-001",
) -> WorkspaceOpenResult:
    return runtime.core.workspaces.open(
        WorkspaceOpenRequest(
            idempotency_key=key,
            name="bounded conjecture",
            problem="Determine whether P(n) holds for every n in the declared scope.",
            tags=("bounded",),
        )
    )
