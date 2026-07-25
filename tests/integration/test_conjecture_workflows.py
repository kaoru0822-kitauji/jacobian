from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from jacobian.canonical import canonicalize_json
from jacobian.conjectures import ConjectureError
from jacobian.contracts.claims import ClaimSpec
from jacobian.contracts.conjectures import (
    ConjectureOperation,
    ConjectureWorkflowRequest,
    FalsificationPlan,
    HypothesisTransformationRecord,
    NoveltyAssessment,
    ParameterRegionEvidence,
    ParameterRegionSubject,
)
from jacobian.contracts.evidence import (
    CertificateEnvelope,
    EvidenceBindings,
    WitnessRole,
)
from jacobian.contracts.plugins import PluginManifest
from jacobian.contracts.results import ExecutionStatus, Verification
from jacobian.contracts.search import SearchBudget
from jacobian.kernel import JacobianKernel

pytestmark = [pytest.mark.integration, pytest.mark.conformance]


def _install_hypothesis_plugin(
    kernel: JacobianKernel,
    *,
    transformer_entrypoint: str = (
        "tests.fixtures.plugin_functions:transform_fixture_hypothesis"
    ),
) -> tuple[str, str, str, str]:
    claim_schema_uri = kernel.schemas.register(
        name="fixture.hypothesis-claim",
        version="1",
        schema=ClaimSpec.model_json_schema(),
    )
    candidate_schema_uri = kernel.schemas.register(
        name="fixture.hypothesis-candidate",
        version="1",
        schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
            "additionalProperties": False,
        },
    )
    semantics_uri = kernel.store.register_descriptor(
        kind="semantics",
        name="fixture.hypothesis-domain",
        version="1",
        definition={"description": "finite hypothesis workflow fixture"},
    )
    entrypoints = {
        "HypothesisTransformer": transformer_entrypoint,
        "Proposer": "tests.fixtures.plugin_functions:propose_fixture_values",
        "Refiner": "tests.fixtures.plugin_functions:refine_fixture_search",
        "Evaluator": "tests.fixtures.plugin_functions:evaluate_candidate",
        "WitnessOracle": ("tests.fixtures.plugin_functions:find_fixture_witness"),
    }
    capabilities: dict[str, dict[str, str]] = {}
    for name, entrypoint in entrypoints.items():
        capabilities[name] = {
            "implementation_uri": kernel.plugins.register_implementation(entrypoint),
            "entrypoint": entrypoint,
            "version": "1",
        }
    manifest = kernel.artifacts.put(
        schema_uri=kernel.reference_installer.manifest_schema_uri,
        semantics_uri=kernel.reference_installer.manifest_semantics_uri,
        payload=PluginManifest(
            domain_id="fixture.hypothesis-domain",
            domain_version="1",
            semantics_uri=semantics_uri,
            claim_schema_uri=claim_schema_uri,
            candidate_schema_uri=candidate_schema_uri,
            capabilities=capabilities,
        ).model_dump(mode="json"),
    )
    kernel.plugins.install(manifest.artifact_uri)
    claim = kernel.artifacts.put(
        schema_uri=claim_schema_uri,
        semantics_uri=semantics_uri,
        payload={
            "claim_schema_version": "1",
            "domain_id": "fixture.hypothesis-domain",
            "domain_version": "1",
            "semantics_uri": semantics_uri,
            "quantifiers": [],
            "predicate": {
                "name": "fixture_predicate",
                "parameters": {"threshold": "0"},
            },
            "bounds": {},
            "required_capabilities": list(entrypoints),
            "correspondence_status": "UNREVIEWED",
        },
    )
    checker = kernel.checkers.authorize(
        name="fixture-hypothesis-value-v1",
        entrypoint="tests.fixtures.checker_functions:check_fixture_value",
        evidence_kind="WITNESS",
        format_id="fixture.value",
        format_version="1",
        claim_schema_uris=(claim_schema_uri,),
        semantics_uris=(semantics_uri,),
        candidate_schema_uris=(candidate_schema_uri,),
        reason="conjecture workflow conformance fixture",
    )
    return (
        claim.artifact_uri,
        manifest.artifact_uri,
        checker.checker_id,
        candidate_schema_uri,
    )


def _verified_counterexample(
    kernel: JacobianKernel,
    *,
    claim_uri: str,
    plugin_id: str,
    checker_id: str,
    candidate_schema_uri: str,
    witness_role: WitnessRole = WitnessRole.REFUTES_CLAIM,
) -> tuple[str, str, str]:
    manifest = kernel.plugins.get(plugin_id)
    candidate = kernel.artifacts.put(
        schema_uri=candidate_schema_uri,
        semantics_uri=manifest.semantics_uri,
        payload={"value": 3},
    )
    found = kernel.witnesses.find(
        claim_uri=claim_uri,
        candidate_uri=candidate.artifact_uri,
        plugin_id=plugin_id,
        witness_role=witness_role,
        wall_seconds=10,
    )
    assert found.witness_uri is not None
    verified = kernel.verification.verify_witness(
        claim_uri=claim_uri,
        candidate_uri=candidate.artifact_uri,
        witness_uri=found.witness_uri,
        checker_id=checker_id,
    )
    assert verified.assurance.verification is Verification.VERIFIED
    assert verified.verification_record_uri is not None
    return (
        verified.verification_record_uri,
        found.witness_uri,
        candidate.artifact_uri,
    )


def _falsification(checker_id: str) -> FalsificationPlan:
    return FalsificationPlan(
        initial_state={"cursor": 0},
        witness_role=WitnessRole.REFUTES_CLAIM,
        counterexample_checker_id=checker_id,
        budget=SearchBudget(
            candidates_max=4,
            iterations_max=2,
            wall_seconds=30,
            batch_size=4,
        ),
    )


@pytest.mark.subprocess
def test_repair_preserves_verified_source_and_falsification_lineage(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id, checker_id, candidate_schema_uri = _install_hypothesis_plugin(
        kernel
    )
    verification_record_uri, witness_uri, _ = _verified_counterexample(
        kernel,
        claim_uri=claim_uri,
        plugin_id=plugin_id,
        checker_id=checker_id,
        candidate_schema_uri=candidate_schema_uri,
    )

    result = kernel.conjectures.run(
        ConjectureWorkflowRequest(
            operation=ConjectureOperation.REPAIR,
            plugin_id=plugin_id,
            source_uri=claim_uri,
            verification_record_uri=verification_record_uri,
            falsification=_falsification(checker_id),
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.verification is Verification.UNVERIFIED
    assert len(result.hypotheses) == 1
    hypothesis = result.hypotheses[0]
    assert hypothesis.verification is Verification.UNVERIFIED
    assert hypothesis.verified_counterexamples == 4
    assert hypothesis.search_experiment_uri is not None
    transformation = HypothesisTransformationRecord.model_validate(
        kernel.store.get(hypothesis.transformation_uri).payload
    )
    assert transformation.source_uri == claim_uri
    assert transformation.evidence_uris == (
        verification_record_uri,
        witness_uri,
    )
    assert {
        claim_uri,
        hypothesis.claim_uri,
        verification_record_uri,
        witness_uri,
    }.issubset(set(kernel.store.get(hypothesis.transformation_uri).manifest.parents))


@pytest.mark.subprocess
def test_repair_replays_the_exact_verification_record(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id, checker_id, candidate_schema_uri = _install_hypothesis_plugin(
        kernel
    )
    verification_record_uri, _, _ = _verified_counterexample(
        kernel,
        claim_uri=claim_uri,
        plugin_id=plugin_id,
        checker_id=checker_id,
        candidate_schema_uri=candidate_schema_uri,
    )
    genuine = kernel.store.get(verification_record_uri)
    forged = kernel.store.put(
        schema_uri=genuine.manifest.schema_uri,
        semantics_uri=genuine.manifest.semantics_uri,
        payload=genuine.payload,
        parents=genuine.manifest.parents,
        summary="caller-authored verification record",
    )

    result = kernel.conjectures.run(
        ConjectureWorkflowRequest(
            operation=ConjectureOperation.REPAIR,
            plugin_id=plugin_id,
            source_uri=claim_uri,
            verification_record_uri=forged.artifact_uri,
        )
    )

    assert result.input.status.value == "REJECTED"
    assert "Re-run verification with an active checker" in result.detail


def test_generation_deduplicates_claims_and_reports_unknown_novelty(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id, _, _ = _install_hypothesis_plugin(kernel)

    result = kernel.conjectures.run(
        ConjectureWorkflowRequest(
            operation=ConjectureOperation.GENERATE,
            plugin_id=plugin_id,
            source_uri=claim_uri,
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert len(result.hypotheses) == 1
    assert result.hypotheses[0].novelty is NoveltyAssessment.UNKNOWN
    assert result.hypotheses[0].verification is Verification.UNVERIFIED

    generated = kernel.store.get(result.hypotheses[0].claim_uri)
    reference = kernel.store.put(
        schema_uri=generated.manifest.schema_uri,
        semantics_uri=generated.manifest.semantics_uri,
        payload=generated.payload,
        parents=(generated.artifact_uri,),
        summary="same claim with different lineage",
    )
    duplicate = kernel.conjectures.run(
        ConjectureWorkflowRequest(
            operation=ConjectureOperation.GENERATE,
            plugin_id=plugin_id,
            source_uri=claim_uri,
            reference_claim_uris=(reference.artifact_uri,),
        )
    )

    assert duplicate.execution.status is ExecutionStatus.COMPLETED
    assert duplicate.hypotheses == ()


@pytest.mark.subprocess
def test_parameter_generalization_keeps_sampled_region_unverified(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id, checker_id, candidate_schema_uri = _install_hypothesis_plugin(
        kernel
    )
    verification_record_uri, witness_uri, candidate_uri = _verified_counterexample(
        kernel,
        claim_uri=claim_uri,
        plugin_id=plugin_id,
        checker_id=checker_id,
        candidate_schema_uri=candidate_schema_uri,
        witness_role=WitnessRole.RESCUES_CANDIDATE,
    )
    rejected = kernel.conjectures.run(
        ConjectureWorkflowRequest(
            operation=ConjectureOperation.PARAMETER_GENERALIZE,
            plugin_id=plugin_id,
            source_uri=claim_uri,
            verification_record_uri=verification_record_uri,
            constraints={
                "claim_template": kernel.store.get(claim_uri).payload,
            },
        )
    )

    assert "requires a verified construction candidate" in rejected.detail

    result = kernel.conjectures.run(
        ConjectureWorkflowRequest(
            operation=ConjectureOperation.PARAMETER_GENERALIZE,
            plugin_id=plugin_id,
            source_uri=candidate_uri,
            verification_record_uri=verification_record_uri,
            constraints={
                "claim_template": kernel.store.get(claim_uri).payload,
            },
        )
    )

    region = result.hypotheses[0].parameter_region
    assert region is not None
    assert region.evidence is ParameterRegionEvidence.SAMPLED
    assert region.sample_uris == (witness_uri,)
    assert region.subject_uri is not None
    assert region.verification_record_uri is None
    assert result.hypotheses[0].verification is Verification.UNVERIFIED
    transformation = HypothesisTransformationRecord.model_validate(
        kernel.store.get(result.hypotheses[0].transformation_uri).payload
    )
    assert transformation.parameter_region == region


@pytest.mark.parametrize(
    ("region_kind", "expected_evidence"),
    [
        ("SUFFICIENT", ParameterRegionEvidence.VERIFIED_SUFFICIENT),
        ("NECESSARY", ParameterRegionEvidence.VERIFIED_NECESSARY),
    ],
)
@pytest.mark.subprocess
def test_parameter_region_promotion_replays_an_exact_authorized_certificate(
    tmp_path: Path,
    region_kind: str,
    expected_evidence: ParameterRegionEvidence,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id, checker_id, candidate_schema_uri = _install_hypothesis_plugin(
        kernel
    )
    source_record_uri, _, candidate_uri = _verified_counterexample(
        kernel,
        claim_uri=claim_uri,
        plugin_id=plugin_id,
        checker_id=checker_id,
        candidate_schema_uri=candidate_schema_uri,
        witness_role=WitnessRole.RESCUES_CANDIDATE,
    )
    result = kernel.conjectures.run(
        ConjectureWorkflowRequest(
            operation=ConjectureOperation.PARAMETER_GENERALIZE,
            plugin_id=plugin_id,
            source_uri=candidate_uri,
            verification_record_uri=source_record_uri,
            constraints={
                "claim_template": kernel.store.get(claim_uri).payload,
                "region_kind": region_kind,
            },
        )
    )
    region = result.hypotheses[0].parameter_region
    assert region is not None
    assert region.subject_uri is not None
    subject_artifact = kernel.store.get(region.subject_uri)
    subject = ParameterRegionSubject.model_validate(subject_artifact.payload)
    target_claim = kernel.store.get(subject.claim_uri)
    semantics = kernel.store.get(target_claim.manifest.semantics_uri)
    certificate_schema_uri = kernel.schemas.register(
        name="fixture.parameter-region-certificate",
        version="1",
        schema=CertificateEnvelope.model_json_schema(),
    )
    region_checker = kernel.checkers.authorize(
        name=f"fixture-parameter-region-{region_kind.lower()}-v1",
        entrypoint=(
            "tests.fixtures.checker_functions:check_parameter_region_certificate"
        ),
        evidence_kind="CERTIFICATE",
        format_id="fixture.parameter_region",
        format_version="1",
        claim_schema_uris=(target_claim.manifest.schema_uri,),
        semantics_uris=(target_claim.manifest.semantics_uri,),
        candidate_schema_uris=(kernel.conjectures.parameter_region_subject_schema_uri,),
        reason="parameter-region promotion conformance fixture",
    )
    proof = {
        "kind": region_kind,
        "conditions": subject.conditions,
    }
    certificate = CertificateEnvelope(
        certificate_type="fixture.parameter_region",
        format_version="1",
        bindings=EvidenceBindings(
            claim_digest=target_claim.manifest.object_digest,
            semantics_digest=semantics.manifest.object_digest,
            candidate_digest=subject_artifact.manifest.object_digest,
        ),
        payload_digest=(
            "sha256:" + hashlib.sha256(canonicalize_json(proof)).hexdigest()
        ),
        payload=proof,
    )
    stored_certificate = kernel.store.put(
        schema_uri=certificate_schema_uri,
        semantics_uri=target_claim.manifest.semantics_uri,
        payload=certificate.model_dump(mode="json"),
        parents=(target_claim.artifact_uri, subject_artifact.artifact_uri),
        summary="parameter-region certificate fixture",
    )
    verified = kernel.verification.verify_certificate(
        certificate_uri=stored_certificate.artifact_uri
    )
    assert verified.verification_record_uri is not None
    kernel.checkers.authorize(
        name=f"fixture-parameter-region-{region_kind.lower()}-v2",
        entrypoint=(
            "tests.fixtures.checker_functions:check_parameter_region_certificate"
        ),
        evidence_kind="CERTIFICATE",
        format_id="fixture.parameter_region",
        format_version="1",
        claim_schema_uris=(target_claim.manifest.schema_uri,),
        semantics_uris=(target_claim.manifest.semantics_uri,),
        candidate_schema_uris=(kernel.conjectures.parameter_region_subject_schema_uri,),
        reason="compatible checker must not change recorded-checker replay",
    )

    promoted = kernel.conjectures.promote_parameter_region(
        subject_uri=subject_artifact.artifact_uri,
        verification_record_uri=verified.verification_record_uri,
    )

    assert promoted.evidence is expected_evidence
    assert promoted.conditions == region.conditions
    assert promoted.sample_uris == region.sample_uris
    assert promoted.subject_uri == region.subject_uri
    assert promoted.verification_record_uri == verified.verification_record_uri

    substituted_subject = kernel.store.put(
        schema_uri=kernel.conjectures.parameter_region_subject_schema_uri,
        semantics_uri=target_claim.manifest.semantics_uri,
        payload=subject.model_dump(mode="json"),
        parents=subject_artifact.manifest.parents,
        summary="same parameter-region payload in a different carrier",
    )
    substituted_subject_artifact = kernel.store.get(substituted_subject.artifact_uri)
    assert (
        substituted_subject_artifact.manifest.object_digest
        == subject_artifact.manifest.object_digest
    )
    assert substituted_subject.artifact_uri != subject_artifact.artifact_uri
    with pytest.raises(
        ConjectureError,
        match="does not cover this parameter region",
    ):
        kernel.conjectures.promote_parameter_region(
            subject_uri=substituted_subject.artifact_uri,
            verification_record_uri=verified.verification_record_uri,
        )

    kernel.checkers.revoke(
        region_checker.checker_id,
        reason="recorded checker revocation must block replay",
    )
    with pytest.raises(
        ConjectureError,
        match="Re-run verification with an active checker",
    ):
        kernel.conjectures.promote_parameter_region(
            subject_uri=subject_artifact.artifact_uri,
            verification_record_uri=verified.verification_record_uri,
        )


@pytest.mark.subprocess
def test_hypothesis_plugin_cannot_promote_parameter_region(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id, checker_id, candidate_schema_uri = _install_hypothesis_plugin(
        kernel,
        transformer_entrypoint=(
            "tests.fixtures.plugin_functions:"
            "transform_with_unsupported_region_promotion"
        ),
    )
    verification_record_uri, _, candidate_uri = _verified_counterexample(
        kernel,
        claim_uri=claim_uri,
        plugin_id=plugin_id,
        checker_id=checker_id,
        candidate_schema_uri=candidate_schema_uri,
        witness_role=WitnessRole.RESCUES_CANDIDATE,
    )

    result = kernel.conjectures.run(
        ConjectureWorkflowRequest(
            operation=ConjectureOperation.PARAMETER_GENERALIZE,
            plugin_id=plugin_id,
            source_uri=candidate_uri,
            verification_record_uri=verification_record_uri,
            constraints={
                "claim_template": kernel.store.get(claim_uri).payload,
            },
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.verification is Verification.UNVERIFIED
    assert result.hypotheses == ()
    assert "Plugin output must remain unverified" in result.detail
    assert "remove the promoted evidence field" in result.detail


@pytest.mark.subprocess
def test_hypothesis_plugin_cannot_cite_unbound_region_samples(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim_uri, plugin_id, _, _ = _install_hypothesis_plugin(
        kernel,
        transformer_entrypoint=(
            "tests.fixtures.plugin_functions:transform_with_unbound_region_sample"
        ),
    )

    result = kernel.conjectures.run(
        ConjectureWorkflowRequest(
            operation=ConjectureOperation.GENERATE,
            plugin_id=plugin_id,
            source_uri=claim_uri,
            constraints={"sample_uri": claim_uri},
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.verification is Verification.UNVERIFIED
    assert result.hypotheses == ()
    assert "not supplied as workflow evidence" in result.detail
    assert "evidence_uris" in result.detail
