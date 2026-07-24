from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.contracts.claims import ClaimSpec
from jacobian.contracts.conjectures import (
    ConjectureOperation,
    ConjectureWorkflowRequest,
    FalsificationPlan,
    HypothesisTransformationRecord,
    NoveltyAssessment,
    ParameterRegionEvidence,
)
from jacobian.contracts.evidence import WitnessRole
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
    assert region.verification_record_uri is None
    assert result.hypotheses[0].verification is Verification.UNVERIFIED
    transformation = HypothesisTransformationRecord.model_validate(
        kernel.store.get(result.hypotheses[0].transformation_uri).payload
    )
    assert transformation.parameter_region == region


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
    assert "cannot promote parameter-region evidence" in result.detail


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
    assert "must be supplied as workflow evidence" in result.detail
