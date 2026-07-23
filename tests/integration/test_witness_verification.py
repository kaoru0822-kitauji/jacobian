from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.contracts.evidence import EvidenceBindings, WitnessEnvelope
from jacobian.contracts.results import Conclusion, Verification
from jacobian.registry import CheckerRegistry
from jacobian.store import ArtifactStore
from jacobian.verification import VerificationService


def _graph_case(
    tmp_path: Path,
    *,
    candidate_schema_definition: dict[str, object] | None = None,
) -> tuple[
    ArtifactStore,
    VerificationService,
    str,
    str,
    str,
    str,
    str,
]:
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
        definition=candidate_schema_definition or {"type": "object"},
    )
    witness_schema = store.register_descriptor(
        kind="schema",
        name="graph.omitted-path.witness",
        version="1",
        definition=WitnessEnvelope.model_json_schema(),
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
    semantics_digest = store.get(semantics).manifest.object_digest
    witness_payload = WitnessEnvelope(
        witness_format="graph.omitted_path",
        format_version="1",
        role="DEFEATS_CANDIDATE",
        bindings=EvidenceBindings(
            claim_digest=claim.object_digest,
            semantics_digest=semantics_digest,
            candidate_digest=candidate.object_digest,
        ),
        payload={"path": ["s", "a", "x", "t2"]},
    )
    witness = store.put(
        schema_uri=witness_schema,
        semantics_uri=semantics,
        payload=loads_strict_json(
            canonicalize_json(witness_payload.model_dump(mode="json"))
        ),
        parents=(claim.artifact_uri, candidate.artifact_uri),
    )
    registry = CheckerRegistry(store.db_path)
    checker = registry.authorize(
        name="graph-omitted-path-v1",
        entrypoint="jacobian_checkers.graph_paths:check_omitted_path",
        evidence_kind="WITNESS",
        format_id="graph.omitted_path",
        format_version="1",
        claim_schema_uris=(claim_schema,),
        semantics_uris=(semantics,),
        candidate_schema_uris=(candidate_schema,),
    )
    return (
        store,
        VerificationService(store, registry),
        checker.checker_id,
        claim.artifact_uri,
        candidate.artifact_uri,
        witness.artifact_uri,
        candidate_schema,
    )


@pytest.mark.integration
@pytest.mark.subprocess
@pytest.mark.conformance
def test_omitted_path_witness_is_independently_verified(tmp_path: Path) -> None:
    _, service, checker_id, claim_uri, candidate_uri, witness_uri, _ = _graph_case(
        tmp_path
    )

    result = service.verify_witness(
        claim_uri=claim_uri,
        candidate_uri=candidate_uri,
        witness_uri=witness_uri,
        checker_id=checker_id,
    )

    assert result.conclusion is Conclusion.FALSE
    assert result.assurance.verification is Verification.VERIFIED
    assert result.verification_record_uri is not None


@pytest.mark.integration
@pytest.mark.subprocess
@pytest.mark.conformance
def test_valid_witness_rebound_to_another_candidate_is_rejected(
    tmp_path: Path,
) -> None:
    (
        store,
        service,
        checker_id,
        claim_uri,
        _,
        witness_uri,
        candidate_schema,
    ) = _graph_case(tmp_path)
    claim = store.get(claim_uri)
    nearby_candidate = store.put(
        schema_uri=candidate_schema,
        semantics_uri=claim.manifest.semantics_uri,
        payload={
            "vertices": ["s", "a", "x", "t1"],
            "arcs": [["s", "a"], ["a", "x"], ["x", "t1"]],
            "source": "s",
            "terminals": ["t1"],
            "intended_paths": [["s", "a", "x", "t1"]],
        },
    )

    result = service.verify_witness(
        claim_uri=claim_uri,
        candidate_uri=nearby_candidate.artifact_uri,
        witness_uri=witness_uri,
        checker_id=checker_id,
    )

    assert result.conclusion is Conclusion.UNKNOWN
    assert result.assurance.verification is Verification.UNVERIFIED
    assert result.input.status.value == "REJECTED"


@pytest.mark.integration
@pytest.mark.subprocess
@pytest.mark.conformance
def test_witness_without_bound_artifact_parents_is_rejected(
    tmp_path: Path,
) -> None:
    (
        store,
        service,
        checker_id,
        claim_uri,
        candidate_uri,
        witness_uri,
        _,
    ) = _graph_case(tmp_path)
    original = store.get(witness_uri)
    detached = store.put(
        schema_uri=original.manifest.schema_uri,
        semantics_uri=original.manifest.semantics_uri,
        payload=original.payload,
        parents=(),
    )

    result = service.verify_witness(
        claim_uri=claim_uri,
        candidate_uri=candidate_uri,
        witness_uri=detached.artifact_uri,
        checker_id=checker_id,
    )

    assert result.conclusion is Conclusion.UNKNOWN
    assert result.assurance.verification is Verification.UNVERIFIED
    assert result.input.status.value == "REJECTED"


@pytest.mark.integration
@pytest.mark.subprocess
@pytest.mark.conformance
def test_schema_label_cannot_authorize_an_invalid_candidate(tmp_path: Path) -> None:
    (
        _,
        service,
        checker_id,
        claim_uri,
        candidate_uri,
        witness_uri,
        _,
    ) = _graph_case(
        tmp_path,
        candidate_schema_definition={
            "type": "object",
            "required": ["operator_reviewed"],
            "properties": {"operator_reviewed": {"const": True}},
        },
    )

    result = service.verify_witness(
        claim_uri=claim_uri,
        candidate_uri=candidate_uri,
        witness_uri=witness_uri,
        checker_id=checker_id,
    )

    assert result.conclusion is Conclusion.UNKNOWN
    assert result.assurance.verification is Verification.UNVERIFIED
    assert result.input.status.value == "REJECTED"


@pytest.mark.integration
@pytest.mark.subprocess
@pytest.mark.conformance
def test_revocation_during_checker_execution_prevents_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        store,
        service,
        checker_id,
        claim_uri,
        candidate_uri,
        witness_uri,
        _,
    ) = _graph_case(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    original = service._run_checker

    def delayed_checker(**kwargs: Any) -> Any:
        entered.set()
        assert release.wait(timeout=5)
        return original(**kwargs)

    monkeypatch.setattr(service, "_run_checker", delayed_checker)
    result_holder: list[Any] = []
    worker = threading.Thread(
        target=lambda: result_holder.append(
            service.verify_witness(
                claim_uri=claim_uri,
                candidate_uri=candidate_uri,
                witness_uri=witness_uri,
                checker_id=checker_id,
            )
        )
    )
    worker.start()
    assert entered.wait(timeout=5)
    CheckerRegistry(store.db_path).revoke(checker_id, reason="concurrent test")
    release.set()
    worker.join(timeout=10)

    assert not worker.is_alive()
    result = result_holder[0]
    assert result.conclusion is Conclusion.UNKNOWN
    assert result.assurance.verification is Verification.UNVERIFIED
    assert result.verification_record_uri is None
