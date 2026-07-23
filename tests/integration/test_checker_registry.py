from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.registry import CheckerRegistry, CheckerRevokedError
from jacobian.store import ArtifactStore


@pytest.mark.integration
@pytest.mark.conformance
def test_revoked_checker_cannot_authorize_new_verification(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    registry = CheckerRegistry(store.db_path)
    checker = registry.authorize(
        name="reject-all-v1",
        entrypoint="jacobian_checkers.reject:check",
        evidence_kind="WITNESS",
        format_id="example.witness",
        format_version="1",
        claim_schema_uris=(),
        semantics_uris=(),
        candidate_schema_uris=(),
    )

    assert registry.require_active(checker.checker_id) == checker

    registry.revoke(checker.checker_id, reason="test revocation")

    with pytest.raises(CheckerRevokedError):
        registry.require_active(checker.checker_id)
    assert [event.action for event in registry.audit_log(checker.checker_id)] == [
        "AUTHORIZED",
        "REVOKED",
    ]
