from pathlib import Path

import pytest

from jacobian.contracts.capabilities import CapabilityRequest
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel

pytestmark = pytest.mark.usefixtures("initialized_kernel_store")


@pytest.mark.parametrize(
    ("capability_id", "values"),
    (
        ("sequence.compute.first_differences", ["7"]),
        ("sequence.compute.second_differences", ["7"]),
        ("sequence.compute.second_differences", ["7", "11"]),
    ),
)
def test_finite_differences_return_natural_empty_result(
    tmp_path: Path,
    capability_id: str,
    values: list[str],
) -> None:
    kernel = JacobianKernel(tmp_path)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id=capability_id,
            input={"values": values},
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["result"] == {"values": []}
    assert len(result.artifact_uris) == 2
