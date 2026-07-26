from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from jacobian.artifacts import ArtifactService
from jacobian.bounded_process import BoundedProcessResult
from jacobian.capabilities import CapabilityService
from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityRequest,
)
from jacobian.contracts.number_theory import (
    FactorialValuationRequest,
    ModularValueRequest,
    NonnegativeIntegerRequest,
    PositiveIntegerRequest,
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
    assert obligation.payload["required_checks"] == ["DISCRETE_LOG_WITNESS_REPLAY"]


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
    assert result.completeness.status is CapabilityCompletenessStatus.NOT_APPLICABLE


def test_factorization_is_complete_in_an_isolated_bounded_worker(
    tmp_path: Path,
) -> None:
    result = _service(tmp_path).invoke(
        CapabilityRequest(
            capability_id="integer.compute.prime_factorization",
            input={
                "value": "360",
                "resource_budget": {"wall_seconds": 10},
            },
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["result"] == {
        "factors": [
            {"prime": "2", "power": 3},
            {"prime": "3", "power": 2},
            {"prime": "5", "power": 1},
        ]
    }
    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED


def test_factorization_timeout_is_an_artifact_free_non_conclusion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    observed: dict[str, object] = {}

    def timeout_worker(*args, **kwargs):
        observed.update(kwargs)
        return BoundedProcessResult(
            returncode=None,
            stdout=b"",
            stderr=b"",
            stdout_exceeded=False,
            stderr_exceeded=False,
            timed_out=True,
        )

    monkeypatch.setattr(
        "jacobian.domains.number_theory.factorization.run_bounded_process",
        timeout_worker,
    )
    result = _service(tmp_path).invoke(
        CapabilityRequest(
            capability_id="integer.compute.divisors",
            input={
                "value": "9999999967",
                "resource_budget": {"wall_seconds": 1},
            },
        )
    )

    assert result.execution.status is ExecutionStatus.TIMEOUT
    assert result.diagnostics[0].code == "INTEGER_FACTORIZATION_TIMEOUT"
    assert result.artifact_uris == ()
    assert result.assurance.level is CapabilityAssuranceLevel.HEURISTIC
    limits = observed["resource_limits"]
    assert limits.cpu_seconds == 2
    assert limits.address_space_bytes == 512 * 1024 * 1024


def test_in_process_factorization_dependencies_have_small_input_bounds() -> None:
    for model, payload in (
        (PositiveIntegerRequest, {"n": 1_001}),
        (NonnegativeIntegerRequest, {"n": 1_001}),
        (ModularValueRequest, {"value": "2", "modulus": 10_001}),
        (FactorialValuationRequest, {"n": 1, "base": 1_000_001}),
    ):
        with pytest.raises(ValidationError):
            model.model_validate(payload)


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
