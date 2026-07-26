from __future__ import annotations

from pathlib import Path

from jacobian.artifacts import ArtifactService
from jacobian.bounded_process import BoundedProcessResult
from jacobian.capabilities import CapabilityService
from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.domains.combinatorics import COMBINATORICS_BUNDLE
from jacobian.domains.number_theory import NUMBER_THEORY_BUNDLE
from jacobian.kernel import JacobianKernel
from jacobian.memory import ResearchMemory
from jacobian.operation_installation import OperationInstaller
from jacobian.schema_registry import SchemaRegistry
from jacobian.store import ArtifactStore


def _service(tmp_path: Path) -> CapabilityService:
    store = ArtifactStore(tmp_path)
    schemas = SchemaRegistry(store)
    artifacts = ArtifactService(store, schemas)
    service = CapabilityService(store, ResearchMemory(store, schemas))
    installer = OperationInstaller(store, schemas, artifacts)
    for bundle in (NUMBER_THEORY_BUNDLE, COMBINATORICS_BUNDLE):
        for adapter in installer.install(bundle).adapters:
            service.register(adapter)
    return service


def test_kernel_catalog_uses_only_domain_owned_operation_ids(tmp_path: Path) -> None:
    catalog_ids = {
        descriptor.capability_id
        for descriptor in JacobianKernel(tmp_path).capabilities.catalog().capabilities
    }

    assert {
        "number_theory.compute.jacobi_symbol",
        "modular.compute.discrete_logarithm",
        "combinatorics.enumerate.integer_partitions",
    } <= catalog_ids
    assert {
        "number_theory.jacobi_symbol.compute",
        "number_theory.discrete_log.bounded",
        "combinatorics.integer_partition.enumerate",
    }.isdisjoint(catalog_ids)


def test_jacobi_symbol_is_domain_owned_exact_computation(tmp_path: Path) -> None:
    result = _service(tmp_path).invoke(
        CapabilityRequest(
            capability_id="number_theory.compute.jacobi_symbol",
            input={"a": "10", "n": 21},
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["result"] == {"a": "10", "n": 21, "jacobi": -1}
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED


def test_even_jacobi_denominator_fails_before_artifact_writes(
    tmp_path: Path,
) -> None:
    result = _service(tmp_path).invoke(
        CapabilityRequest(
            capability_id="number_theory.compute.jacobi_symbol",
            input={"a": "10", "n": 20},
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.artifact_uris == ()


def test_discrete_logarithm_materializes_bound_result_and_obligation(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    result = service.invoke(
        CapabilityRequest(
            capability_id="modular.compute.discrete_logarithm",
            input={"base": 7, "target": 15, "modulus": 41},
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output == {
        "status": "SOLVED",
        "base": 7,
        "target": 15,
        "modulus": 41,
        "discrete_log": 3,
    }
    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert len(result.artifact_uris) == 3
    assert len(result.obligations) == 1
    obligation = service.store.get(result.obligations[0].obligation_uri)
    assert obligation.payload["required_checks"] == [
        "DISCRETE_LOG_WITNESS_REPLAY"
    ]


def test_discrete_logarithm_reports_unsolvable_without_false_witness(
    tmp_path: Path,
) -> None:
    result = _service(tmp_path).invoke(
        CapabilityRequest(
            capability_id="modular.compute.discrete_logarithm",
            input={"base": 2, "target": 3, "modulus": 8},
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["status"] == "UNSOLVABLE"
    assert result.output["discrete_log"] is None
    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE


def test_discrete_logarithm_timeout_is_an_artifact_free_non_conclusion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "jacobian.domains.number_theory.discrete_logarithm.run_bounded_process",
        lambda *args, **kwargs: BoundedProcessResult(
            returncode=None,
            stdout=b"",
            stderr=b"",
            stdout_exceeded=False,
            stderr_exceeded=False,
            timed_out=True,
        ),
    )
    result = _service(tmp_path).invoke(
        CapabilityRequest(
            capability_id="modular.compute.discrete_logarithm",
            input={
                "base": 7,
                "target": 15,
                "modulus": 41,
                "resource_budget": {"wall_seconds": 1},
            },
        )
    )

    assert result.execution.status is ExecutionStatus.TIMEOUT
    assert result.diagnostics[0].code == "DISCRETE_LOGARITHM_TIMEOUT"
    assert result.artifact_uris == ()
    assert (
        result.completeness.status
        is CapabilityCompletenessStatus.NOT_APPLICABLE
    )


def test_integer_partition_enumeration_is_complete_and_canonical(
    tmp_path: Path,
) -> None:
    result = _service(tmp_path).invoke(
        CapabilityRequest(
            capability_id="combinatorics.enumerate.integer_partitions",
            input={"n": 5, "max_parts": 2},
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["result"] == {
        "n": 5,
        "max_parts": 2,
        "partitions": [[5], [4, 1], [3, 2]],
    }
    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE
