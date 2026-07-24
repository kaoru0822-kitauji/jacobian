from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from jacobian.canonical import canonicalize_json
from jacobian.contracts.checkers import EvidenceKind
from jacobian.registry import (
    CheckerRegistry,
    CheckerRegistryError,
    CheckerRevokedError,
)
from jacobian.store import ArtifactStore

CLAIM_SCHEMA_A = "artifact://sha256/" + "a" * 64
CLAIM_SCHEMA_B = "artifact://sha256/" + "b" * 64


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
        claim_schema_uris=(CLAIM_SCHEMA_A,),
        semantics_uris=(CLAIM_SCHEMA_A,),
        candidate_schema_uris=(CLAIM_SCHEMA_A,),
    )

    assert registry.require_active(checker.checker_id) == checker

    registry.revoke(checker.checker_id, reason="test revocation")

    with pytest.raises(CheckerRevokedError):
        registry.require_active(checker.checker_id)
    assert [event.action for event in registry.audit_log(checker.checker_id)] == [
        "AUTHORIZED",
        "REVOKED",
    ]


@pytest.mark.integration
@pytest.mark.conformance
@pytest.mark.parametrize("corruption", ["registration", "digest_column"])
def test_checker_registry_rejects_identity_metadata_corruption(
    tmp_path: Path,
    corruption: str,
) -> None:
    store = ArtifactStore(tmp_path)
    registry = CheckerRegistry(store.db_path)
    checker = registry.authorize(
        name="reject-all-v1",
        entrypoint="jacobian_checkers.reject:check",
        evidence_kind="WITNESS",
        format_id="example.witness",
        format_version="1",
        claim_schema_uris=(CLAIM_SCHEMA_A,),
        semantics_uris=(CLAIM_SCHEMA_A,),
        candidate_schema_uris=(CLAIM_SCHEMA_A,),
    )

    with sqlite3.connect(store.db_path) as connection:
        if corruption == "registration":
            tampered = checker.model_dump(mode="json")
            tampered["claim_schema_uris"] = [CLAIM_SCHEMA_A, CLAIM_SCHEMA_B]
            connection.execute(
                """
                UPDATE checkers
                SET registration_json = ?
                WHERE checker_id = ?
                """,
                (canonicalize_json(tampered), checker.checker_id),
            )
        else:
            connection.execute(
                """
                UPDATE checkers
                SET executable_digest = ?
                WHERE checker_id = ?
                """,
                ("sha256:" + "0" * 64, checker.checker_id),
            )

    with pytest.raises(CheckerRegistryError, match="stored checker metadata"):
        registry.get(checker.checker_id)


@pytest.mark.integration
@pytest.mark.conformance
@pytest.mark.parametrize(
    ("evidence_kind", "claim_schemas", "semantics", "candidate_schemas", "targets"),
    [
        (EvidenceKind.WITNESS, (), (CLAIM_SCHEMA_A,), (CLAIM_SCHEMA_A,), ()),
        (EvidenceKind.WITNESS, (CLAIM_SCHEMA_A,), (), (CLAIM_SCHEMA_A,), ()),
        (EvidenceKind.WITNESS, (CLAIM_SCHEMA_A,), (CLAIM_SCHEMA_A,), (), ()),
        (
            EvidenceKind.TRANSFORMATION,
            (CLAIM_SCHEMA_A,),
            (CLAIM_SCHEMA_A,),
            (CLAIM_SCHEMA_A,),
            (),
        ),
    ],
)
def test_checker_authorization_requires_explicit_compatibility_scope(
    tmp_path: Path,
    evidence_kind: EvidenceKind,
    claim_schemas: tuple[str, ...],
    semantics: tuple[str, ...],
    candidate_schemas: tuple[str, ...],
    targets: tuple[str, ...],
) -> None:
    registry = CheckerRegistry(ArtifactStore(tmp_path).db_path)

    with pytest.raises(CheckerRegistryError, match="explicit compatibility"):
        registry.authorize(
            name="reject-all-v1",
            entrypoint="jacobian_checkers.reject:check",
            evidence_kind=evidence_kind,
            format_id="example.witness",
            format_version="1",
            claim_schema_uris=claim_schemas,
            semantics_uris=semantics,
            candidate_schema_uris=candidate_schemas,
            target_schema_uris=targets,
            target_semantics_uris=targets,
        )
