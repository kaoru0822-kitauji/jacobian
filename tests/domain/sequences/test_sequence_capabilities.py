from collections.abc import Iterator
from pathlib import Path

import pytest
from tests.support.services import DomainTestServices, open_domain_services

from jacobian.contracts.capabilities import CapabilityRequest
from jacobian.contracts.results import ExecutionStatus
from jacobian.domains.sequences import build_sequence_bundle


@pytest.fixture
def domain_services(tmp_path: Path) -> Iterator[DomainTestServices]:
    with open_domain_services(tmp_path / "state", build_sequence_bundle()) as services:
        yield services


def test_prefix_gcds_return_each_prefix_result(
    domain_services: DomainTestServices,
) -> None:
    result = domain_services.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="sequence.compute.prefix_gcds",
            input={"values": ["18", "24", "15"]},
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["result"] == {"values": ["18", "6", "3"]}


@pytest.mark.parametrize(
    ("values", "expected"),
    (
        (["0", "0", "1"], False),
        (["1", "0", "0"], True),
        (["0", "0", "0"], True),
        (["2", "4", "8", "16"], True),
        (["8", "-4", "2", "-1"], True),
        (["2", "4", "9"], False),
    ),
)
def test_geometric_sequence_handles_zero_terms_exactly(
    domain_services: DomainTestServices,
    values: list[str],
    expected: bool,
) -> None:
    result = domain_services.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="sequence.decide.geometric",
            input={"values": values},
        )
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["result"] == {"holds": expected}
