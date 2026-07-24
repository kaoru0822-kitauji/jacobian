"""Authentication and tenant routing for remote MCP transports."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp.server.auth.provider import AccessToken

from jacobian.kernel import JacobianKernel

_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True, slots=True)
class StaticTokenGrant:
    tenant_id: str
    token: str
    scopes: tuple[str, ...] = ("jacobian:use",)

    def __post_init__(self) -> None:
        if not _TENANT_PATTERN.fullmatch(self.tenant_id):
            raise ValueError("tenant_id has an invalid format")
        if len(self.token) < 32:
            raise ValueError("remote bearer tokens must contain at least 32 characters")
        if not self.scopes:
            raise ValueError("a remote token grant requires at least one scope")


class StaticTokenVerifier:
    """Verify operator-provisioned opaque bearer tokens without logging them."""

    def __init__(self, grants: tuple[StaticTokenGrant, ...]) -> None:
        if not grants:
            raise ValueError("at least one token grant is required")
        if len({grant.tenant_id for grant in grants}) != len(grants):
            raise ValueError("tenant IDs in the token file must be unique")
        if len({grant.token for grant in grants}) != len(grants):
            raise ValueError("bearer tokens in the token file must be unique")
        self._grants = grants

    async def verify_token(self, token: str) -> AccessToken | None:
        for grant in self._grants:
            if hmac.compare_digest(token, grant.token):
                return AccessToken(
                    token=token,
                    client_id=f"jacobian-tenant:{grant.tenant_id}",
                    scopes=list(grant.scopes),
                    subject=grant.tenant_id,
                )
        return None


class TenantKernelRouter:
    """Create one isolated kernel root per authenticated subject."""

    def __init__(
        self,
        root: str | Path,
        *,
        install_references: bool = True,
        allow_anonymous: bool = False,
        capability_adapter_entrypoints: tuple[str, ...] = (),
    ) -> None:
        self.root = Path(root)
        self.install_references = install_references
        self.allow_anonymous = allow_anonymous
        self.capability_adapter_entrypoints = capability_adapter_entrypoints
        self._kernels: dict[str, JacobianKernel] = {}
        self._lock = threading.Lock()

    def kernel_for(self, subject: str | None) -> JacobianKernel:
        tenant = subject
        if tenant is None:
            if not self.allow_anonymous:
                raise PermissionError("authenticated tenant subject is required")
            tenant = "anonymous"
        if not _TENANT_PATTERN.fullmatch(tenant):
            raise PermissionError("authenticated tenant subject is invalid")
        tenant_key = hashlib.sha256(tenant.encode("utf-8")).hexdigest()
        with self._lock:
            kernel = self._kernels.get(tenant_key)
            if kernel is None:
                kernel = JacobianKernel(
                    self.root / "tenants" / tenant_key,
                    install_references=self.install_references,
                    capability_adapter_entrypoints=(
                        self.capability_adapter_entrypoints
                    ),
                )
                self._kernels[tenant_key] = kernel
            return kernel


def load_static_token_file(path: str | Path) -> tuple[StaticTokenGrant, ...]:
    """Load a strict JSON token file intended to be mounted as a secret."""

    selected = Path(path)
    try:
        payload: Any = json.loads(selected.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("cannot read the remote auth token file") from exc
    if not isinstance(payload, dict) or set(payload) != {"tokens"}:
        raise ValueError("token file must contain only a tokens array")
    records = payload["tokens"]
    if not isinstance(records, list):
        raise ValueError("token file tokens must be an array")
    grants: list[StaticTokenGrant] = []
    for record in records:
        if not isinstance(record, dict) or not set(record) <= {
            "tenant_id",
            "token",
            "scopes",
        }:
            raise ValueError("token grants contain unsupported fields")
        tenant_id = record.get("tenant_id")
        token = record.get("token")
        scopes = record.get("scopes", ["jacobian:use"])
        if (
            not isinstance(tenant_id, str)
            or not isinstance(token, str)
            or not isinstance(scopes, list)
            or not all(isinstance(scope, str) and scope for scope in scopes)
        ):
            raise ValueError("token grant fields have invalid types")
        grants.append(
            StaticTokenGrant(
                tenant_id=tenant_id,
                token=token,
                scopes=tuple(scopes),
            )
        )
    return tuple(grants)
