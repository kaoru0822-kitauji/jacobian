"""Portfolio and smoke checks for resource-mined domain atomics."""

from __future__ import annotations

from pathlib import Path

from jacobian.contracts.capabilities import CapabilityAssuranceLevel, CapabilityRequest
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel


def test_resource_portfolio_has_more_than_one_hundred_atomic_capabilities(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    assert len(kernel.capabilities.catalog().capabilities) >= 100


def test_domain_atomic_results_are_exact_computed_evidence(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    cases = (
        (
            "number_theory.prime_counting.compute",
            {"n": 100},
            {"n": 100, "prime_count": 25},
        ),
        (
            "matrix.determinant.compute",
            {
                "matrix": {
                    "domain": "QQ",
                    "entries": [
                        [
                            {"num": "1", "den": "1"},
                            {"num": "2", "den": "1"},
                        ],
                        [
                            {"num": "3", "den": "1"},
                            {"num": "4", "den": "1"},
                        ],
                    ],
                }
            },
            {"determinant": {"num": "-2", "den": "1"}},
        ),
        (
            "graph.invariant.triangle_count",
            {
                "vertices": ["a", "b", "c"],
                "edges": [["a", "b"], ["b", "c"], ["c", "a"]],
            },
            {"triangle_count": 1},
        ),
    )
    for capability_id, payload, expected in cases:
        result = kernel.capabilities.invoke(
            CapabilityRequest(capability_id=capability_id, input=payload)
        )
        assert result.execution.status is ExecutionStatus.COMPLETED
        assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
        assert all(result.output[key] == value for key, value in expected.items())


def test_domain_atomic_input_failure_is_not_a_mathematical_conclusion(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="number_theory.prime_counting.compute",
            input={"n": -1},
        )
    )
    assert result.execution.status is ExecutionStatus.ERROR
    assert result.assurance.level is CapabilityAssuranceLevel.HEURISTIC
    assert result.assurance.verification_record_uri is None
