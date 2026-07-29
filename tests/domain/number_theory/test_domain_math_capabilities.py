from collections.abc import Iterator
from pathlib import Path

import pytest
from tests.support.services import DomainTestServices, open_domain_services

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.domains.arithmetic import ARITHMETIC_BUNDLE
from jacobian.domains.combinatorics import COMBINATORICS_BUNDLE
from jacobian.domains.finite_sets import FINITE_SET_BUNDLE
from jacobian.domains.number_theory import NUMBER_THEORY_BUNDLE
from jacobian.domains.sequences import SEQUENCE_BUNDLE


@pytest.fixture
def domain_services(tmp_path: Path) -> Iterator[DomainTestServices]:
    with open_domain_services(
        tmp_path / "state",
        ARITHMETIC_BUNDLE,
        COMBINATORICS_BUNDLE,
        FINITE_SET_BUNDLE,
        NUMBER_THEORY_BUNDLE,
        SEQUENCE_BUNDLE,
    ) as services:
        yield services


def test_representative_exact_domain_results(domain_services) -> None:
    cases = (
        (
            "integer.compute.extended_gcd",
            {"left": "84", "right": "30"},
            {"gcd": "6", "left_coefficient": "-1", "right_coefficient": "3"},
        ),
        (
            "combinatorics.compute.bernoulli",
            {"n": 4},
            {"value": {"num": "-1", "den": "30"}},
        ),
        (
            "integer.compute.nth_root",
            {"value": 65, "degree": 3},
            {"root": "4", "exact": False},
        ),
        (
            "finite_set.compute.symmetric_difference",
            {
                "left": {"elements": ["3", "1"]},
                "right": {"elements": ["2", "3"]},
            },
            {"elements": ["1", "2"]},
        ),
        (
            "sequence.compute.prefix_gcds",
            {"values": ["18", "24", "15"]},
            {"values": ["18", "6", "3"]},
        ),
        (
            "modular.enumerate.quadratic_residues",
            {"modulus": 10},
            {"residues": ["0", "1", "4", "5", "6", "9"]},
        ),
        (
            "rational.compute.continued_fraction",
            {"value": {"num": "-7", "den": "5"}},
            {"terms": ["-2", "1", "1", "2"]},
        ),
        (
            "integer.transform.base_digits",
            {"value": "-10", "base": 2},
            {"sign": -1, "base": 2, "digits": ["1", "0", "1", "0"]},
        ),
    )

    for capability_id, payload, expected in cases:
        result = domain_services.core.capabilities.invoke(
            CapabilityRequest(capability_id=capability_id, input=payload)
        )
        assert result.execution.status is ExecutionStatus.COMPLETED
        assert result.output["result"] == expected


def test_domain_error_fails_before_artifact_writes(domain_services) -> None:
    result = domain_services.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="modular.compute.inverse",
            input={"value": "6", "modulus": 9},
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.diagnostics[0].code == "NUMBER_THEORY_OPERATION_NOT_APPLICABLE"
    assert result.assurance.level is CapabilityAssuranceLevel.HEURISTIC
    assert result.artifact_uris == ()
    assert result.episode_uri is None


def test_number_theory_boundary_results(domain_services) -> None:
    empty_cases = (
        ("integer.compute.proper_divisors", {"value": "1"}, {"divisors": []}),
        ("integer.compute.proper_divisors", {"value": "-1"}, {"divisors": []}),
        ("integer.compute.prime_factorization", {"value": "1"}, {"factors": []}),
        ("integer.compute.prime_factorization", {"value": "-1"}, {"factors": []}),
    )
    for capability_id, payload, expected in empty_cases:
        result = domain_services.core.capabilities.invoke(
            CapabilityRequest(capability_id=capability_id, input=payload)
        )
        assert result.execution.status is ExecutionStatus.COMPLETED
        assert result.output["result"] == expected

    for capability_id, payload in (
        ("integer.compute.divisors", {"value": "0"}),
        ("integer.compute.prime_factorization", {"value": "0"}),
        ("integer.compute.previous_prime", {"n": 2}),
    ):
        result = domain_services.core.capabilities.invoke(
            CapabilityRequest(capability_id=capability_id, input=payload)
        )
        assert result.execution.status is ExecutionStatus.ERROR
        assert result.artifact_uris == ()


def test_geometric_sequence_handles_zero_terms_exactly(domain_services) -> None:
    cases = (
        (["0", "0", "1"], False),
        (["1", "0", "0"], True),
        (["0", "0", "0"], True),
        (["2", "4", "8", "16"], True),
        (["8", "-4", "2", "-1"], True),
        (["2", "4", "9"], False),
    )

    for values, expected in cases:
        result = domain_services.core.capabilities.invoke(
            CapabilityRequest(
                capability_id="sequence.decide.geometric",
                input={"values": values},
            )
        )
        assert result.execution.status is ExecutionStatus.COMPLETED
        assert result.output["result"] == {"holds": expected}
