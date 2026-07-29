import pytest

from jacobian.contracts.capabilities import CapabilityRequest
from jacobian.contracts.results import ExecutionStatus
from jacobian.runtime.model import JacobianRuntime


@pytest.mark.parametrize(
    ("capability_id", "values"),
    (
        ("sequence.compute.first_differences", ["7"]),
        ("sequence.compute.second_differences", ["7"]),
        ("sequence.compute.second_differences", ["7", "11"]),
    ),
)
def test_finite_differences_return_natural_empty_result(
    runtime: JacobianRuntime,
    capability_id: str,
    values: list[str],
) -> None:
    result = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id=capability_id,
            input={"values": values},
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["result"] == {"values": []}
    assert len(result.artifact_uris) == 2
