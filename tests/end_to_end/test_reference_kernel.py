from __future__ import annotations

import hashlib
import json
import subprocess
import sys

import pytest

from jacobian.canonical import canonicalize_json
from jacobian.contracts.evidence import (
    CertificateEnvelope,
    EvidenceBindings,
)
from jacobian.kernel import JacobianKernel


@pytest.fixture
def kernel(kernel_with_references: JacobianKernel) -> JacobianKernel:
    return kernel_with_references


def test_graph_search_witness_and_independent_replay(
    kernel: JacobianKernel,
) -> None:
    reference = kernel.references["graph_paths"]
    claim = kernel.artifacts.put(
        schema_uri=reference.claim_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={
            "claim_schema_version": "1",
            "domain_id": "jacobian.graph-paths",
            "domain_version": "1",
            "semantics_uri": reference.semantics_uri,
            "quantifiers": [],
            "predicate": {
                "name": "intended_paths_complete",
                "parameters": {"simple": True},
            },
            "bounds": {},
            "required_capabilities": ["Evaluator", "WitnessOracle"],
            "correspondence_status": "HUMAN_REVIEWED",
        },
    )
    candidate = kernel.artifacts.put(
        schema_uri=reference.candidate_schema_uri,
        semantics_uri=reference.semantics_uri,
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

    evaluation = kernel.evaluation.evaluate_batch(
        claim_uri=claim.artifact_uri,
        candidate_uris=(candidate.artifact_uri,),
        plugin_id=reference.plugin_id,
        profile="EXACT_CANDIDATE",
        seed=0,
        wall_seconds=30,
    )
    assert evaluation.items[0].result.conclusion.value == "FALSE"
    assert evaluation.items[0].result.assurance.verification.value == "UNVERIFIED"

    found = kernel.witnesses.find(
        claim_uri=claim.artifact_uri,
        candidate_uri=candidate.artifact_uri,
        plugin_id=reference.plugin_id,
        witness_role="DEFEATS_CANDIDATE",
        wall_seconds=30,
    )
    assert found.witness_uri is not None
    verified = kernel.verification.verify_witness(
        claim_uri=claim.artifact_uri,
        candidate_uri=candidate.artifact_uri,
        witness_uri=found.witness_uri,
        checker_id=reference.witness_checker_ids["graph.omitted_path"],
    )

    assert verified.conclusion.value == "FALSE"
    assert verified.assurance.verification.value == "VERIFIED"

    replay = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json,sys;"
                "from jacobian.kernel import JacobianKernel;"
                "kernel=JacobianKernel(sys.argv[1],install_references=True);"
                "result=kernel.verification.verify_witness("
                "claim_uri=sys.argv[2],candidate_uri=sys.argv[3],"
                "witness_uri=sys.argv[4],checker_id=sys.argv[5]);"
                "print(json.dumps(result.model_dump(mode='json'),sort_keys=True))"
            ),
            str(kernel.store.root),
            claim.artifact_uri,
            candidate.artifact_uri,
            found.witness_uri,
            reference.witness_checker_ids["graph.omitted_path"],
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    replayed = json.loads(replay.stdout)
    assert replayed["conclusion"] == "FALSE"
    assert replayed["assurance"]["verification"] == "VERIFIED"


def test_matrix_kernel_witness_and_independent_replay(kernel) -> None:
    reference = kernel.references["matrices"]
    claim = kernel.artifacts.put(
        schema_uri=reference.claim_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={
            "claim_schema_version": "1",
            "domain_id": "jacobian.integer-matrices",
            "domain_version": "1",
            "semantics_uri": reference.semantics_uri,
            "quantifiers": [],
            "predicate": {
                "name": "is_nonsingular",
                "parameters": {},
            },
            "bounds": {},
            "required_capabilities": ["Evaluator", "WitnessOracle"],
            "correspondence_status": "HUMAN_REVIEWED",
        },
    )
    candidate = kernel.artifacts.put(
        schema_uri=reference.candidate_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={
            "rows": 2,
            "cols": 2,
            "entries": [["2", "4"], ["1", "2"]],
        },
    )

    found = kernel.witnesses.find(
        claim_uri=claim.artifact_uri,
        candidate_uri=candidate.artifact_uri,
        plugin_id=reference.plugin_id,
        witness_role="DEFEATS_CANDIDATE",
        wall_seconds=30,
    )
    assert found.witness_uri is not None
    verified = kernel.verification.verify_witness(
        claim_uri=claim.artifact_uri,
        candidate_uri=candidate.artifact_uri,
        witness_uri=found.witness_uri,
        checker_id=reference.witness_checker_ids["matrix.kernel_vector"],
    )

    assert verified.conclusion.value == "FALSE"
    assert verified.assurance.arithmetic.value == "EXACT_RATIONAL"
    assert verified.assurance.verification.value == "VERIFIED"


def test_erdos_straus_range_witness_and_independent_replay(
    kernel,
) -> None:
    reference = kernel.references["erdos_straus"]
    claim = kernel.artifacts.put(
        schema_uri=reference.claim_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={
            "claim_schema_version": "1",
            "domain_id": "jacobian.erdos-straus",
            "domain_version": "1",
            "semantics_uri": reference.semantics_uri,
            "quantifiers": [],
            "predicate": {
                "name": "erdos_straus_range",
                "parameters": {"lower_bound": 2, "upper_bound": 1000},
            },
            "bounds": {},
            "required_capabilities": ["Evaluator", "WitnessOracle"],
            "correspondence_status": "HUMAN_REVIEWED",
        },
    )
    candidate = kernel.artifacts.put(
        schema_uri=reference.candidate_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={"lower_bound": 2, "upper_bound": 1000},
    )

    found = kernel.witnesses.find(
        claim_uri=claim.artifact_uri,
        candidate_uri=candidate.artifact_uri,
        plugin_id=reference.plugin_id,
        witness_role="SUPPORTS_CLAIM",
        wall_seconds=30,
    )
    assert found.witness_uri is not None
    verified = kernel.verification.verify_witness(
        claim_uri=claim.artifact_uri,
        candidate_uri=candidate.artifact_uri,
        witness_uri=found.witness_uri,
        checker_id=reference.witness_checker_ids["erdos_straus.decomposition_table"],
    )

    assert verified.conclusion.value == "TRUE"
    assert verified.assurance.arithmetic.value == "EXACT_INTEGER"
    assert verified.assurance.coverage.value == "EXHAUSTIVE"
    assert verified.assurance.verification.value == "VERIFIED"


def test_matrix_maxdet_certificate_replays_full_scope(kernel) -> None:
    reference = kernel.references["matrices"]
    claim = kernel.artifacts.put(
        schema_uri=reference.claim_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={
            "claim_schema_version": "1",
            "domain_id": "jacobian.integer-matrices",
            "domain_version": "1",
            "semantics_uri": reference.semantics_uri,
            "quantifiers": [],
            "predicate": {
                "name": "maximize_absolute_determinant",
                "parameters": {
                    "scope": {
                        "rows": 3,
                        "cols": 3,
                        "entries": [-1, 1],
                    }
                },
            },
            "bounds": {},
            "required_capabilities": ["SemanticEnumerator"],
            "correspondence_status": "HUMAN_REVIEWED",
        },
    )
    candidate = kernel.artifacts.put(
        schema_uri=reference.candidate_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={
            "rows": 3,
            "cols": 3,
            "entries": [
                [-1, -1, -1],
                [-1, -1, 1],
                [-1, 1, -1],
            ],
        },
    )
    found = kernel.witnesses.find(
        claim_uri=claim.artifact_uri,
        candidate_uri=candidate.artifact_uri,
        plugin_id=reference.plugin_id,
        witness_role="SUPPORTS_CLAIM",
        wall_seconds=30,
    )
    assert found.witness_uri is not None
    verified_witness = kernel.verification.verify_witness(
        claim_uri=claim.artifact_uri,
        candidate_uri=candidate.artifact_uri,
        witness_uri=found.witness_uri,
        checker_id=reference.witness_checker_ids["matrix.maximizer"],
    )
    assert verified_witness.conclusion.value == "TRUE"
    assert verified_witness.assurance.coverage.value == "EXHAUSTIVE"

    payload = {
        "maximum": {"num": "4", "den": "1"},
        "objects_checked": 512,
    }
    certificate = CertificateEnvelope(
        certificate_type="matrix.maxdet_enumeration",
        format_version="1",
        bindings=EvidenceBindings(
            claim_digest=claim.object_digest,
            semantics_digest=kernel.store.get(
                reference.semantics_uri
            ).manifest.object_digest,
            candidate_digest=candidate.object_digest,
        ),
        payload_digest=(
            "sha256:" + hashlib.sha256(canonicalize_json(payload)).hexdigest()
        ),
        payload=payload,
    )
    stored = kernel.store.put(
        schema_uri=reference.certificate_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload=certificate.model_dump(mode="json"),
        parents=(claim.artifact_uri, candidate.artifact_uri),
    )

    verified = kernel.verification.verify_certificate(
        certificate_uri=stored.artifact_uri
    )

    assert verified.conclusion.value == "TRUE"
    assert verified.assurance.coverage.value == "EXHAUSTIVE"
    assert verified.assurance.verification.value == "VERIFIED"


def test_graph_counterexample_shrinks_to_the_odd_cycle(kernel) -> None:
    reference = kernel.references["graph_paths"]
    claim = kernel.artifacts.put(
        schema_uri=reference.claim_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={
            "claim_schema_version": "1",
            "domain_id": "jacobian.graph-paths",
            "domain_version": "1",
            "semantics_uri": reference.semantics_uri,
            "quantifiers": [],
            "predicate": {"name": "is_bipartite", "parameters": {}},
            "bounds": {},
            "required_capabilities": ["Reducer"],
            "correspondence_status": "HUMAN_REVIEWED",
        },
    )
    candidate = kernel.artifacts.put(
        schema_uri=reference.candidate_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={
            "vertices": ["a", "b", "c", "x", "y"],
            "arcs": [["a", "b"], ["b", "c"], ["c", "a"]],
        },
    )

    shrunk = kernel.shrinking.run(
        target_kind="candidate",
        target_uri=candidate.artifact_uri,
        claim_uri=claim.artifact_uri,
        plugin_id=reference.plugin_id,
        preservation_checker_id=reference.preservation_checker_ids[
            "graph.counterexample_preservation"
        ],
        reducers=("delete_vertex",),
        objectives=("vertices", "edges"),
        evaluation_budget=20,
    )

    final = kernel.store.get(shrunk.final_target_uri).payload
    assert set(final["vertices"]) == {"a", "b", "c"}
    assert shrunk.minimality.value == "NONE"
    assert shrunk.result.assurance.verification.value == "VERIFIED"
