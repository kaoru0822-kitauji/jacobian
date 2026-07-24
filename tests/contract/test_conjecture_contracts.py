from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.conjectures import (
    ConjectureOperation,
    ConjectureWorkflowRequest,
    ConjectureWorkflowResult,
    FalsificationPlan,
    HypothesisEdit,
    ParameterRegion,
    PluginHypothesisProposal,
)
from jacobian.contracts.results import (
    Execution,
    ExecutionStatus,
    InputStatus,
    InputValidation,
    Verification,
)
from jacobian.contracts.search import SearchBudget

ARTIFACT = "artifact://sha256/" + "a" * 64
DIGEST = "sha256:" + "b" * 64


def _budget() -> SearchBudget:
    return SearchBudget(
        candidates_max=4,
        iterations_max=4,
        wall_seconds=30,
    )


def test_repair_requires_verified_source_lineage() -> None:
    with pytest.raises(
        ValidationError,
        match="repair and parameter generalization require a verified source",
    ):
        ConjectureWorkflowRequest(
            operation=ConjectureOperation.REPAIR,
            plugin_id=ARTIFACT,
        )


def test_falsification_plan_requires_complete_checker_policy() -> None:
    with pytest.raises(
        ValidationError,
        match="witness role and counterexample checker must be configured together",
    ):
        FalsificationPlan(
            witness_role="REFUTES_CLAIM",
            budget=_budget(),
        )


def test_falsification_plan_rejects_supporting_witness_roles() -> None:
    with pytest.raises(
        ValidationError,
        match="falsification requires a defeating or refuting witness",
    ):
        FalsificationPlan(
            witness_role="SUPPORTS_CLAIM",
            counterexample_checker_id=("checker://sha256/" + "c" * 64),
            budget=_budget(),
        )


def test_plugin_cannot_promote_parameter_region() -> None:
    with pytest.raises(
        ValidationError,
        match="hypothesis plugins cannot promote parameter-region evidence",
    ):
        PluginHypothesisProposal(
            claim={"predicate": "fixture"},
            edit=HypothesisEdit(
                kind="parameter",
                description="widen a finite range",
            ),
            parameter_region=ParameterRegion(
                kind="SUFFICIENT",
                conditions={"n": {"minimum": 1}},
                evidence="VERIFIED_SUFFICIENT",
                subject_uri=ARTIFACT,
                verification_record_uri=ARTIFACT,
            ),
        )


def test_sampled_parameter_region_requires_sample_artifacts() -> None:
    with pytest.raises(
        ValidationError,
        match="sampled parameter regions require sample artifacts",
    ):
        ParameterRegion(
            kind="SUFFICIENT",
            conditions={"n": {"minimum": 1}},
            evidence="SAMPLED",
        )


def test_conjecture_workflow_cannot_self_certify() -> None:
    with pytest.raises(
        ValidationError,
        match="conjecture workflows cannot self-certify",
    ):
        ConjectureWorkflowResult(
            operation=ConjectureOperation.GENERATE,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            input=InputValidation(status=InputStatus.ACCEPTED),
            request_digest=DIGEST,
            plugin_id=ARTIFACT,
            verification=Verification.VERIFIED,
        )


def test_accepted_conjecture_workflow_requires_exact_identity() -> None:
    with pytest.raises(
        ValidationError,
        match="accepted conjecture workflows require operation and plugin identity",
    ):
        ConjectureWorkflowResult(
            execution=Execution(status=ExecutionStatus.COMPLETED),
            input=InputValidation(status=InputStatus.ACCEPTED),
            request_digest=DIGEST,
        )
