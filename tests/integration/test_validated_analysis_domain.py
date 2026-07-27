from __future__ import annotations

import subprocess
from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from jacobian.artifacts import ArtifactService
from jacobian.capabilities import CapabilityService
from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityObligationStatus,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.contracts.validated_analysis import (
    RationalLinearProgramObligation,
)
from jacobian.domains.analysis import REAL_ANALYSIS_BUNDLE
from jacobian.domains.optimization import RATIONAL_OPTIMIZATION_BUNDLE
from jacobian.domains.probability import FINITE_PROBABILITY_BUNDLE
from jacobian.memory import ResearchMemory
from jacobian.operation_installation import OperationInstaller
from jacobian.schema_registry import SchemaRegistry
from jacobian.store import ArtifactStore

pytestmark = pytest.mark.integration


def _rational(num: int, den: int = 1) -> dict[str, str]:
    return {"num": str(num), "den": str(den)}


@pytest.fixture(scope="module")
def analysis_runtime(tmp_path_factory: pytest.TempPathFactory) -> _Runtime:
    store = ArtifactStore(tmp_path_factory.mktemp("validated-analysis"))
    schemas = SchemaRegistry(store)
    artifacts = ArtifactService(store, schemas)
    capabilities = CapabilityService(store, ResearchMemory(store, schemas))
    installer = OperationInstaller(store, schemas, artifacts)
    for bundle in (
        REAL_ANALYSIS_BUNDLE,
        FINITE_PROBABILITY_BUNDLE,
        RATIONAL_OPTIMIZATION_BUNDLE,
    ):
        installed = installer.install(bundle)
        for adapter in installed.adapters:
            capabilities.register(adapter)
    return _Runtime(store=store, capabilities=capabilities)


@dataclass(frozen=True)
class _Runtime:
    store: ArtifactStore
    capabilities: CapabilityService


def test_subject_bundles_preserve_wire_contracts_and_report_one_backend() -> None:
    assert {
        bundle.domain_id: (
            bundle.provider_runtime.provider,
            bundle.schema_namespace,
            tuple(operation.capability_id for operation in bundle.capabilities),
        )
        for bundle in (
            REAL_ANALYSIS_BUNDLE,
            FINITE_PROBABILITY_BUNDLE,
            RATIONAL_OPTIMIZATION_BUNDLE,
        )
    } == {
        "analysis": (
            "python-flint",
            "jacobian.validated-analysis",
            ("analysis.real_function.point_enclosure.compute",),
        ),
        "probability": (
            "python-flint",
            "jacobian.validated-analysis",
            ("probability.finite_distribution.raw_moment.compute",),
        ),
        "optimization": (
            "jacobian.sympy",
            "jacobian.validated-analysis",
            ("optimization.linear.rational_optimum.compute",),
        ),
    }


def test_arb_point_enclosure_materializes_exact_dyadics_and_obligation(
    analysis_runtime: _Runtime,
) -> None:
    runtime = analysis_runtime

    result = runtime.capabilities.invoke(
        CapabilityRequest(
            capability_id="analysis.real_function.point_enclosure.compute",
            input={
                "function": "EXP",
                "argument": _rational(1, 3),
                "precision_bits": 128,
                "wall_seconds": 10,
            },
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["status"] == "ENCLOSED"
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["lower"]["mantissa"]
    assert result.output["upper"]["mantissa"]
    assert result.output["relative_accuracy_bits"] >= 120
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE
    assert len(result.artifact_uris) == 3
    assert result.obligations[0].status is CapabilityObligationStatus.OPEN
    obligation = runtime.store.get(result.obligations[0].obligation_uri)
    assert obligation.payload["required_checker"] == (
        "AUTHORIZED_INDEPENDENT_BALL_ARITHMETIC"
    )
    assert set(obligation.manifest.parents) == set(result.artifact_uris[:2])


def test_arb_nonfinite_and_timeout_are_non_conclusions(
    analysis_runtime: _Runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = analysis_runtime
    nonfinite = runtime.capabilities.invoke(
        CapabilityRequest(
            capability_id="analysis.real_function.point_enclosure.compute",
            input={
                "function": "LOG",
                "argument": _rational(-1),
                "wall_seconds": 10,
            },
        )
    )

    assert nonfinite.output["status"] == "NONFINITE"
    assert nonfinite.output["lower"] is None
    assert nonfinite.output["upper"] is None
    assert nonfinite.output["conclusion"] == "UNKNOWN"
    assert nonfinite.completeness.status is CapabilityCompletenessStatus.UNKNOWN
    assert nonfinite.obligations[0].status is CapabilityObligationStatus.OPEN

    from jacobian.domains.analysis import operations

    def timeout(
        _payload: dict[str, object],
        *,
        wall_seconds: int,
    ) -> dict[str, object]:
        raise subprocess.TimeoutExpired("validated-analysis-worker", wall_seconds)

    monkeypatch.setattr(operations, "_run_worker", timeout)
    timed_out = runtime.capabilities.invoke(
        CapabilityRequest(
            capability_id="analysis.real_function.point_enclosure.compute",
            input={
                "function": "SIN",
                "argument": _rational(1),
                "wall_seconds": 1,
            },
        )
    )

    assert timed_out.execution.status is ExecutionStatus.TIMEOUT
    assert timed_out.output["status"] == "TIMEOUT"
    assert timed_out.output["conclusion"] == "UNKNOWN"
    assert timed_out.diagnostics[0].code == "ARB_POINT_ENCLOSURE_TIMEOUT"
    assert timed_out.assurance.level is CapabilityAssuranceLevel.HEURISTIC
    assert timed_out.completeness.status is CapabilityCompletenessStatus.UNKNOWN
    assert timed_out.obligations[0].status is CapabilityObligationStatus.OPEN


def test_finite_raw_moment_preserves_exact_contributions(
    analysis_runtime: _Runtime,
) -> None:
    runtime = analysis_runtime

    result = runtime.capabilities.invoke(
        CapabilityRequest(
            capability_id="probability.finite_distribution.raw_moment.compute",
            input={
                "atoms": [
                    {"value": _rational(-1), "probability": _rational(1, 2)},
                    {"value": _rational(3), "probability": _rational(1, 2)},
                ],
                "order": 2,
            },
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["result"]["moment"] == _rational(5)
    assert [
        item["contribution"] for item in result.output["result"]["contributions"]
    ] == [_rational(1, 2), _rational(9, 2)]
    assert result.output["result"]["verification"] == "UNVERIFIED"
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert len(result.artifact_uris) == 2
    persisted = runtime.store.get(result.artifact_uris[1])
    assert persisted.payload == result.output["result"]


def test_invalid_finite_distribution_fails_before_artifact_writes(
    analysis_runtime: _Runtime,
) -> None:
    runtime = analysis_runtime

    result = runtime.capabilities.invoke(
        CapabilityRequest(
            capability_id="probability.finite_distribution.raw_moment.compute",
            input={
                "atoms": [
                    {"value": _rational(0), "probability": _rational(1, 3)},
                    {"value": _rational(1), "probability": _rational(1, 3)},
                ],
                "order": 1,
            },
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.diagnostics[0].code == "INVALID_FINITE_PROBABILITY_REQUEST"
    assert result.artifact_uris == ()


def test_rational_lp_produces_inspectable_primal_dual_certificate(
    analysis_runtime: _Runtime,
) -> None:
    runtime = analysis_runtime

    result = runtime.capabilities.invoke(
        CapabilityRequest(
            capability_id="optimization.linear.rational_optimum.compute",
            input={
                "program": {
                    "variables": ["x", "y"],
                    "objective": [_rational(1), _rational(2)],
                    "coefficients": [[_rational(1), _rational(1)]],
                    "rhs": [_rational(1)],
                },
                "wall_seconds": 10,
            },
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["status"] == "CERTIFICATE_PRODUCED"
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["primal_candidate"] == [_rational(1), _rational(0)]
    assert result.output["dual_candidate"] == [_rational(1)]
    assert result.output["primal_objective"] == _rational(1)
    assert result.output["dual_objective"] == _rational(1)
    assert result.output["primal_residuals"] == [_rational(0)]
    assert result.output["dual_slacks"] == [_rational(0), _rational(1)]
    assert result.output["verification"] == "UNVERIFIED"
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.obligations[0].status is CapabilityObligationStatus.OPEN
    obligation = runtime.store.get(result.obligations[0].obligation_uri)
    assert obligation.payload["required_checks"] == [
        "PRIMAL_FEASIBILITY",
        "DUAL_FEASIBILITY",
        "OBJECTIVE_EQUALITY",
    ]


def test_rational_lp_dual_variables_are_unrestricted_and_dimension_bound(
    analysis_runtime: _Runtime,
) -> None:
    result = analysis_runtime.capabilities.invoke(
        CapabilityRequest(
            capability_id="optimization.linear.rational_optimum.compute",
            input={
                "program": {
                    "variables": ["x", "y"],
                    "objective": [_rational(-1), _rational(3)],
                    "coefficients": [
                        [_rational(1), _rational(0)],
                        [_rational(0), _rational(1)],
                    ],
                    "rhs": [_rational(1), _rational(2)],
                },
                "wall_seconds": 10,
            },
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["status"] == "CERTIFICATE_PRODUCED"
    assert result.output["primal_candidate"] == [_rational(1), _rational(2)]
    assert result.output["dual_candidate"] == [_rational(-1), _rational(3)]
    assert result.output["primal_objective"] == _rational(5)
    assert result.output["dual_objective"] == _rational(5)
    assert result.output["dual_slacks"] == [_rational(0), _rational(0)]

    obligation = analysis_runtime.store.get(result.obligations[0].obligation_uri)
    assert len(obligation.payload["dual_candidate"]) == len(
        obligation.payload["program"]["coefficients"]
    )


def test_rational_lp_obligation_rejects_wrong_candidate_dimensions() -> None:
    program = {
        "variables": ["x", "y"],
        "objective": [_rational(1), _rational(1)],
        "coefficients": [[_rational(1), _rational(1)]],
        "rhs": [_rational(1)],
    }

    with pytest.raises(ValidationError, match="primal candidate length"):
        RationalLinearProgramObligation.model_validate(
            {
                "program": program,
                "status": "CERTIFICATE_PRODUCED",
                "primal_candidate": [_rational(1)],
                "dual_candidate": [_rational(1)],
            }
        )
    with pytest.raises(ValidationError, match="dual candidate length"):
        RationalLinearProgramObligation.model_validate(
            {
                "program": program,
                "status": "CERTIFICATE_PRODUCED",
                "primal_candidate": [_rational(1), _rational(0)],
                "dual_candidate": [_rational(1), _rational(0)],
            }
        )
