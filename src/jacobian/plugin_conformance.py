"""Reusable conformance checks for an operator-installed plugin package."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from jacobian.contracts.conjectures import (
    ConjectureOperation,
    ConjectureWorkflowRequest,
)
from jacobian.contracts.discovery import ExperimentState
from jacobian.contracts.plugins import CapabilityName
from jacobian.contracts.results import ExecutionStatus, Verification
from jacobian.contracts.search import (
    SearchExperimentSnapshot,
    SearchRunRequest,
    SearchStopReason,
)
from jacobian.plugins.registry import PluginRegistryError

if TYPE_CHECKING:
    from jacobian.kernel import JacobianKernel


class PluginConformanceCheck(StrEnum):
    EXECUTION_SUCCESS = "execution-success"
    DECLARED_FAILURE = "declared-failure"
    MALFORMED_OUTPUT = "malformed-output"
    TIMEOUT = "timeout"
    PATH_ATTACK = "path-attack"
    SYMLINK_ATTACK = "symlink-attack"
    IMPLEMENTATION_CHANGED = "implementation-changed"
    EVIDENCE_PROMOTION = "unsupported-evidence-promotion"


@dataclass(frozen=True)
class SyntheticPluginConformanceTarget:
    """Disposable installed package consumed by the standard matrix.

    This protocol is for a conformance-only package in isolated test state,
    never for a production plugin. The package's proposer branches on
    ``state["conformance_case"]`` for the four execution cases. Its other
    search capabilities satisfy their ordinary contracts, and its hypothesis
    transformer attempts an unsupported verified parameter-region promotion.
    """

    kernel: JacobianKernel
    plugin_id: str
    search_request: SearchRunRequest
    implementation_file: Path
    symlink_path: Path
    symlink_target: Path
    import_marker: Path | None = None

    def __post_init__(self) -> None:
        if self.search_request.plugin_id != self.plugin_id:
            raise ValueError("conformance search request must target the plugin")


@dataclass(frozen=True)
class PluginConformanceObservation:
    check: PluginConformanceCheck
    passed: bool
    detail: str


class PluginConformanceError(AssertionError):
    """One or more required plugin conformance checks failed."""

    def __init__(
        self,
        observations: tuple[PluginConformanceObservation, ...],
    ) -> None:
        self.observations = observations
        failures = (item for item in observations if not item.passed)
        super().__init__(
            "; ".join(f"{item.check.value}: {item.detail}" for item in failures)
        )


def run_plugin_conformance(
    target: SyntheticPluginConformanceTarget,
) -> tuple[PluginConformanceObservation, ...]:
    """Run every check against real registry and workflow boundaries.

    A fresh idempotency namespace forces repeated suite calls to execute the
    plugin again. Checks are independent observations: one failure does not
    short-circuit the remaining matrix.
    """

    checks: tuple[
        tuple[
            PluginConformanceCheck,
            Callable[[SyntheticPluginConformanceTarget, str], None],
        ],
        ...,
    ] = (
        (PluginConformanceCheck.EXECUTION_SUCCESS, _check_execution_success),
        (PluginConformanceCheck.DECLARED_FAILURE, _check_declared_failure),
        (PluginConformanceCheck.MALFORMED_OUTPUT, _check_malformed_output),
        (PluginConformanceCheck.TIMEOUT, _check_timeout),
        (PluginConformanceCheck.PATH_ATTACK, _check_path_attack),
        (PluginConformanceCheck.SYMLINK_ATTACK, _check_symlink_attack),
        (PluginConformanceCheck.EVIDENCE_PROMOTION, _check_evidence_promotion),
        (
            PluginConformanceCheck.IMPLEMENTATION_CHANGED,
            _check_implementation_changed,
        ),
    )
    run_namespace = uuid4().hex
    observations: list[PluginConformanceObservation] = []
    try:
        for check, run in checks:
            try:
                run(target, run_namespace)
            except Exception as exc:
                observations.append(
                    PluginConformanceObservation(
                        check=check,
                        passed=False,
                        detail=f"{type(exc).__name__}: {exc}",
                    )
                )
            else:
                observations.append(
                    PluginConformanceObservation(
                        check=check,
                        passed=True,
                        detail="passed",
                    )
                )
    finally:
        if target.import_marker is not None:
            target.import_marker.unlink(missing_ok=True)
    return tuple(observations)


def require_plugin_conformance(
    target: SyntheticPluginConformanceTarget,
) -> tuple[PluginConformanceObservation, ...]:
    """Run the standard matrix and raise one aggregate error on failure."""

    observations = run_plugin_conformance(target)
    if any(not observation.passed for observation in observations):
        raise PluginConformanceError(observations)
    return observations


def _search(
    target: SyntheticPluginConformanceTarget,
    check: PluginConformanceCheck,
    run_namespace: str,
) -> SearchExperimentSnapshot:
    request = target.search_request
    budget = request.budget
    if check is PluginConformanceCheck.TIMEOUT:
        budget = budget.model_copy(update={"wall_seconds": 1})
    idempotency_prefix = request.idempotency_key[:55]
    selected = request.model_copy(
        update={
            "idempotency_key": (f"{idempotency_prefix}:{run_namespace}:{check.value}"),
            "initial_state": {
                **request.initial_state,
                "conformance_case": check.value,
            },
            "budget": budget,
        }
    )
    handle = target.kernel.search.start(selected)
    return target.kernel.search.wait(handle.experiment_uri, timeout_seconds=15)


def _check_execution_success(
    target: SyntheticPluginConformanceTarget,
    run_namespace: str,
) -> None:
    target.kernel.plugins.snapshot(target.plugin_id)
    for capability in (
        CapabilityName.PROPOSER,
        CapabilityName.REFINER,
        CapabilityName.EVALUATOR,
        CapabilityName.HYPOTHESIS_TRANSFORMER,
    ):
        target.kernel.plugins.resolve(target.plugin_id, capability)
    if target.import_marker is not None and target.import_marker.exists():
        raise AssertionError("plugin discovery imported package code")

    snapshot = _search(
        target,
        PluginConformanceCheck.EXECUTION_SUCCESS,
        run_namespace,
    )
    if (
        snapshot.state is not ExperimentState.COMPLETED
        or snapshot.stop_reason is not SearchStopReason.STRATEGY_COMPLETE
        or not snapshot.strategy_reported_complete
    ):
        raise AssertionError(
            f"successful search ended as {snapshot.state.value}: {snapshot.detail}"
        )
    if target.import_marker is not None and not target.import_marker.exists():
        raise AssertionError("successful worker execution did not import package code")


def _check_declared_failure(
    target: SyntheticPluginConformanceTarget,
    run_namespace: str,
) -> None:
    snapshot = _search(
        target,
        PluginConformanceCheck.DECLARED_FAILURE,
        run_namespace,
    )
    if snapshot.state is not ExperimentState.ERROR:
        raise AssertionError(f"declared failure ended as {snapshot.state.value}")
    if "declared plugin failure" not in snapshot.detail:
        raise AssertionError(f"unexpected declared-failure detail: {snapshot.detail}")


def _check_malformed_output(
    target: SyntheticPluginConformanceTarget,
    run_namespace: str,
) -> None:
    snapshot = _search(
        target,
        PluginConformanceCheck.MALFORMED_OUTPUT,
        run_namespace,
    )
    if snapshot.state is not ExperimentState.ERROR:
        raise AssertionError(f"malformed output ended as {snapshot.state.value}")
    if "plugin response must be a JSON object" not in snapshot.detail:
        raise AssertionError(f"unexpected malformed-output detail: {snapshot.detail}")


def _check_timeout(
    target: SyntheticPluginConformanceTarget,
    run_namespace: str,
) -> None:
    snapshot = _search(
        target,
        PluginConformanceCheck.TIMEOUT,
        run_namespace,
    )
    if (
        snapshot.state is not ExperimentState.TIMEOUT
        or snapshot.stop_reason is not SearchStopReason.WALL_TIME_LIMIT
    ):
        raise AssertionError(
            f"timed execution ended as {snapshot.state.value}: {snapshot.detail}"
        )


def _check_path_attack(
    target: SyntheticPluginConformanceTarget,
    _run_namespace: str,
) -> None:
    _expect_registry_rejection(
        lambda: target.kernel.plugins.register_implementation("../escape:run"),
    )


def _check_symlink_attack(
    target: SyntheticPluginConformanceTarget,
    _run_namespace: str,
) -> None:
    try:
        target.symlink_path.symlink_to(target.symlink_target)
        _expect_registry_rejection(
            lambda: target.kernel.plugins.resolve(
                target.plugin_id,
                CapabilityName.PROPOSER,
            ),
            match="regular file",
        )
    finally:
        if target.symlink_path.is_symlink():
            target.symlink_path.unlink()


def _check_evidence_promotion(
    target: SyntheticPluginConformanceTarget,
    _run_namespace: str,
) -> None:
    result = target.kernel.conjectures.run(
        ConjectureWorkflowRequest(
            operation=ConjectureOperation.GENERATE,
            plugin_id=target.plugin_id,
            source_uri=target.search_request.claim_uri,
            wall_seconds=5,
        )
    )
    if (
        result.execution.status is not ExecutionStatus.ERROR
        or result.verification is not Verification.UNVERIFIED
        or result.hypotheses
    ):
        raise AssertionError("unsupported promotion crossed the evidence boundary")
    if "cannot promote parameter-region evidence" not in result.detail:
        raise AssertionError(f"unexpected promotion detail: {result.detail}")


def _check_implementation_changed(
    target: SyntheticPluginConformanceTarget,
    _run_namespace: str,
) -> None:
    original = target.implementation_file.read_bytes()
    try:
        target.implementation_file.write_bytes(original + b"\n# changed bytes\n")
        _expect_registry_rejection(
            lambda: target.kernel.plugins.resolve(
                target.plugin_id,
                CapabilityName.PROPOSER,
            ),
            match="bytes changed",
        )
    finally:
        target.implementation_file.write_bytes(original)


def _expect_registry_rejection(
    operation: Callable[[], object],
    *,
    match: str | None = None,
) -> None:
    try:
        operation()
    except PluginRegistryError as exc:
        if match is not None and match not in str(exc):
            raise AssertionError(
                f"registry rejection did not contain {match!r}: {exc}"
            ) from exc
        return
    raise AssertionError("registry accepted an invalid plugin package")
