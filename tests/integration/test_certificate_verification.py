from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.contracts.evidence import CertificateEnvelope, EvidenceBindings
from jacobian.contracts.results import Conclusion, Verification
from jacobian.registry import CheckerRegistry
from jacobian.store import ArtifactStore
from jacobian.verification import VerificationService


@pytest.mark.integration
@pytest.mark.subprocess
@pytest.mark.conformance
def test_complete_path_enumeration_certificate_is_verified(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    claim_schema = store.register_descriptor(
        kind="schema",
        name="graph.path-closure.claim",
        version="1",
        definition={"type": "object"},
    )
    candidate_schema = store.register_descriptor(
        kind="schema",
        name="graph.candidate",
        version="1",
        definition={"type": "object"},
    )
    scope_schema = store.register_descriptor(
        kind="schema",
        name="graph.path.scope",
        version="1",
        definition={"type": "object"},
    )
    certificate_schema = store.register_descriptor(
        kind="schema",
        name="graph.path-enumeration.certificate",
        version="1",
        definition=CertificateEnvelope.model_json_schema(),
    )
    semantics = store.register_descriptor(
        kind="semantics",
        name="directed-graph.path-language",
        version="1",
        definition={"paths": "all simple source-terminal paths"},
    )
    claim = store.put(
        schema_uri=claim_schema,
        semantics_uri=semantics,
        payload={"predicate": "intended_paths_complete", "simple": True},
    )
    candidate = store.put(
        schema_uri=candidate_schema,
        semantics_uri=semantics,
        payload={
            "vertices": ["s", "a", "b", "x", "t1", "t2"],
            "arcs": [
                ["s", "a"],
                ["a", "x"],
                ["s", "b"],
                ["b", "x"],
                ["x", "t1"],
                ["x", "t2"],
            ],
            "source": "s",
            "terminals": ["t1", "t2"],
            "intended_paths": [
                ["s", "a", "x", "t1"],
                ["s", "b", "x", "t2"],
            ],
        },
    )
    scope = store.put(
        schema_uri=scope_schema,
        semantics_uri=semantics,
        payload={"simple": True, "max_length": 6},
    )
    certificate_payload = {
        "actual_paths": [
            ["s", "a", "x", "t1"],
            ["s", "a", "x", "t2"],
            ["s", "b", "x", "t1"],
            ["s", "b", "x", "t2"],
        ]
    }
    certificate = CertificateEnvelope(
        certificate_type="graph.path_enumeration",
        format_version="1",
        bindings=EvidenceBindings(
            claim_digest=claim.object_digest,
            semantics_digest=store.get(semantics).manifest.object_digest,
            candidate_digest=candidate.object_digest,
            scope_digest=scope.object_digest,
        ),
        payload_digest="sha256:"
        + hashlib.sha256(canonicalize_json(certificate_payload)).hexdigest(),
        payload=certificate_payload,
    )
    certificate_artifact = store.put(
        schema_uri=certificate_schema,
        semantics_uri=semantics,
        payload=loads_strict_json(
            canonicalize_json(certificate.model_dump(mode="json"))
        ),
        parents=(
            claim.artifact_uri,
            candidate.artifact_uri,
            scope.artifact_uri,
        ),
    )
    registry = CheckerRegistry(store.db_path)
    registry.authorize(
        name="graph-path-enumeration-v1",
        entrypoint="jacobian_checkers.graph_paths:check_path_enumeration",
        evidence_kind="CERTIFICATE",
        format_id="graph.path_enumeration",
        format_version="1",
        claim_schema_uris=(claim_schema,),
        semantics_uris=(semantics,),
        candidate_schema_uris=(candidate_schema,),
    )

    result = VerificationService(store, registry).verify_certificate(
        certificate_uri=certificate_artifact.artifact_uri
    )

    assert result.conclusion is Conclusion.FALSE
    assert result.assurance.verification is Verification.VERIFIED
    assert result.assurance.coverage.value == "EXHAUSTIVE"
