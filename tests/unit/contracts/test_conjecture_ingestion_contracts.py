from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.conjecture_ingestion import (
    ExternalConjectureIngestArtifact,
    ExternalConjectureIngestRequest,
)


def test_request_accepts_openconjecture_provenance() -> None:
    request = ExternalConjectureIngestRequest(
        corpus_id="davisrbr/openconjecture",
        corpus_revision="f665b46c93a6a1d505ef9109417902d7b2973ab8",
        source_url="https://huggingface.co/datasets/davisrbr/openconjecture",
        item_id="fixture-1",
        metadata={"title": "Fixture conjecture"},
        statement="A fixture statement.",
        source_license="CC-BY-4.0",
        license_evidence_url="https://example.invalid/license",
        license_evidence_text="Creative Commons Attribution 4.0",
        license_evidence_digest=(
            "sha256:14cf6e4efc51a33be0438483f0bc0d53963cedad7406282e331b3f797779cc11"
        ),
    )

    assert request.policy_id == "jacobian.external-conjecture-publication/v1"


def test_request_rejects_unknown_license_tokens() -> None:
    with pytest.raises(ValidationError):
        ExternalConjectureIngestRequest(
            corpus_id="fixture",
            corpus_revision="revision-1",
            source_url="https://example.invalid/corpus",
            item_id="item-1",
            metadata={"title": "Fixture conjecture"},
            source_license="probably-open",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("license_evidence_url", ""),
        ("license_evidence_url", "   "),
        ("license_evidence_text", ""),
        ("license_evidence_text", "\n\t"),
    ),
)
def test_request_rejects_blank_license_evidence(field: str, value: str) -> None:
    payload = {
        "corpus_id": "fixture",
        "corpus_revision": "revision-1",
        "source_url": "https://example.invalid/corpus",
        "item_id": "item-1",
        "metadata": {"title": "Fixture conjecture"},
        "statement": "A fixture statement.",
        "source_license": "CC-BY-4.0",
        "license_evidence_url": "https://example.invalid/license",
        "license_evidence_text": "license evidence",
        "license_evidence_digest": "sha256:" + "a" * 64,
    }
    payload[field] = value

    with pytest.raises(ValidationError, match="must not be blank"):
        ExternalConjectureIngestRequest.model_validate(payload)


@pytest.mark.parametrize("statement", (" ", "\n\r\t"))
def test_request_rejects_statement_that_normalizes_to_empty(statement: str) -> None:
    with pytest.raises(ValidationError, match="statement must not be blank"):
        ExternalConjectureIngestRequest(
            corpus_id="fixture",
            corpus_revision="revision-1",
            source_url="https://example.invalid/corpus",
            item_id="item-1",
            metadata={"title": "Fixture conjecture"},
            statement=statement,
            source_license="MISSING",
        )


def test_artifact_cannot_claim_verification() -> None:
    with pytest.raises(ValidationError):
        ExternalConjectureIngestArtifact(
            corpus_id="fixture",
            corpus_revision="revision-1",
            source_url="https://example.invalid/corpus",
            item_id="item-1",
            metadata={"title": "Fixture conjecture"},
            record_digest="sha256:" + "a" * 64,
            source_license="MISSING",
            policy_id="jacobian.external-conjecture-publication/v1",
            license_decision="METADATA_ONLY",
            license_reason="No license was supplied.",
            withheld_fields=(),
            ingestion_status="METADATA_INDEXED_TEXT_WITHHELD",
            verification="VERIFIED",
        )
