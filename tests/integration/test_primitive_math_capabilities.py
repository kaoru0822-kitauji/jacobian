from pathlib import Path

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityRequest,
)
from jacobian.contracts.primitive_math import (
    ChineseRemainderRequest,
    IntegerListRequest,
    IntegerModulusRequest,
    IntegerPairRequest,
    IntegerSetPairRequest,
    IntegerValueRequest,
    NonnegativeIntegerRequest,
    NonnegativePairRequest,
    RationalPairRequest,
    RationalValueRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel
from jacobian.primitive_math_capabilities import SPECS


def test_all_primitive_math_capabilities_are_distinct_and_installed(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    ids = [spec.capability_id for spec in SPECS]

    assert len(ids) >= 100
    assert len(ids) == len(set(ids))
    assert set(ids) <= {
        descriptor.capability_id
        for descriptor in kernel.capabilities.catalog().capabilities
    }


def test_number_theory_and_combinatorics_results_are_materialized(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)

    gcd = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="integer.compute.gcd",
            input={"left": "84", "right": "30"},
        )
    )
    binomial = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="combinatorics.compute.binomial",
            input={"n": 10, "k": 3},
        )
    )

    assert gcd.execution.status is ExecutionStatus.COMPLETED
    assert gcd.output["result"] == "6"
    assert binomial.output["result"] == "120"
    for result in (gcd, binomial):
        assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
        assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE
        assert len(result.artifact_uris) == 2


def test_inapplicable_input_fails_closed(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="modular.compute.inverse",
            input={"value": "6", "modulus": 9},
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.diagnostics[0].code == "PRIMITIVE_MATH_NOT_APPLICABLE"
    assert result.assurance.level is CapabilityAssuranceLevel.HEURISTIC
    assert result.artifact_uris == ()
    assert result.episode_uri is None


def test_every_primitive_math_contract_has_a_completing_reproduction(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    payloads = {
        IntegerValueRequest: {"value": "12"},
        NonnegativeIntegerRequest: {"n": 5},
        IntegerPairRequest: {"left": "12", "right": "5"},
        NonnegativePairRequest: {"n": 5, "k": 2},
        IntegerModulusRequest: {"value": "2", "modulus": 5},
        IntegerListRequest: {"values": ["1", "2", "3"]},
        IntegerSetPairRequest: {"left": ["1", "2"], "right": ["2", "3"]},
        RationalValueRequest: {"value": {"num": "3", "den": "2"}},
        RationalPairRequest: {
            "left": {"num": "3", "den": "2"},
            "right": {"num": "2", "den": "3"},
        },
        ChineseRemainderRequest: {"residues": [2, 3], "moduli": [3, 5]},
    }

    for spec in SPECS:
        result = kernel.capabilities.invoke(
            CapabilityRequest(
                capability_id=spec.capability_id,
                input=payloads[spec.request_model],
            )
        )
        assert result.execution.status is ExecutionStatus.COMPLETED, (
            spec.capability_id,
            result.diagnostics,
        )


def test_representative_exact_results(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    cases = (
        (
            "integer.compute.extended_gcd",
            {"left": "84", "right": "30"},
            {"gcd": "6", "left_coefficient": "-1", "right_coefficient": "3"},
        ),
        (
            "combinatorics.compute.bernoulli",
            {"n": 4},
            {"num": "-1", "den": "30"},
        ),
        (
            "integer.compute.nth_root",
            {"n": 65, "k": 3},
            {"root": "4", "exact": False},
        ),
        (
            "finite_set.compute.symmetric_difference",
            {"left": ["3", "1"], "right": ["2", "3"]},
            ["1", "2"],
        ),
        (
            "sequence.compute.prefix_gcds",
            {"values": ["18", "24", "15"]},
            ["18", "6", "3"],
        ),
        (
            "modular.enumerate.quadratic_residues",
            {"value": "0", "modulus": 10},
            ["0", "1", "4", "5", "6", "9"],
        ),
        (
            "rational.compute.continued_fraction",
            {"value": {"num": "-7", "den": "5"}},
            ["-2", "1", "1", "2"],
        ),
        (
            "integer.transform.base_digits",
            {"value": "-10", "modulus": 2},
            {"sign": -1, "base": 2, "digits": ["1", "0", "1", "0"]},
        ),
        (
            "integer.transform.base_digits",
            {"value": "0", "modulus": 10},
            {"sign": 0, "base": 10, "digits": ["0"]},
        ),
    )

    for capability_id, payload, expected in cases:
        result = kernel.capabilities.invoke(
            CapabilityRequest(capability_id=capability_id, input=payload)
        )
        assert result.execution.status is ExecutionStatus.COMPLETED
        assert result.output["result"] == expected


def test_geometric_sequence_handles_zero_terms_exactly(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    cases = (
        (["0", "0", "1"], False),
        (["1", "0", "0"], True),
        (["0", "0", "0"], True),
        (["2", "4", "8", "16"], True),
        (["8", "-4", "2", "-1"], True),
        (["2", "4", "9"], False),
    )

    for values, expected in cases:
        result = kernel.capabilities.invoke(
            CapabilityRequest(
                capability_id="sequence.decide.geometric",
                input={"values": values},
            )
        )
        assert result.execution.status is ExecutionStatus.COMPLETED
        assert result.output["result"] is expected
