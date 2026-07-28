from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from jacobian.canonical import canonicalize_json
from jacobian.contracts.evidence import CertificateEnvelope


@pytest.mark.conformance
def test_certificate_payload_must_match_its_declared_digest() -> None:
    original_payload = {"rows": [{"candidate": "0", "value": "1"}]}
    payload_digest = (
        "sha256:" + hashlib.sha256(canonicalize_json(original_payload)).hexdigest()
    )
    certificate = {
        "evidence_schema_version": "1",
        "certificate_type": "finite_enumeration",
        "format_version": "1",
        "bindings": {
            "claim_digest": "sha256:" + "a" * 64,
            "semantics_digest": "sha256:" + "b" * 64,
            "candidate_digest": "sha256:" + "c" * 64,
            "scope_digest": "sha256:" + "d" * 64,
        },
        "payload_digest": payload_digest,
        "payload": {"rows": [{"candidate": "0", "value": "2"}]},
    }

    with pytest.raises(ValidationError):
        CertificateEnvelope.model_validate(certificate)
