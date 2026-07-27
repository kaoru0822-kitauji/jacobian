"""Regression coverage for maximum binary finite-set outputs."""

import pytest

from jacobian.contracts.finite_sets import (
    FiniteIntegerSet,
    FiniteSetCardinalityResult,
    FiniteSetElementListResult,
    FiniteSetPairRequest,
)
from jacobian.domains.finite_sets.operations import (
    set_symmetric_difference,
    set_union,
    union_cardinality,
)


@pytest.fixture
def maximum_disjoint_pair() -> FiniteSetPairRequest:
    return FiniteSetPairRequest(
        left=FiniteIntegerSet(elements=tuple(str(value) for value in range(128))),
        right=FiniteIntegerSet(
            elements=tuple(str(value) for value in range(128, 256))
        ),
    )


def test_maximum_disjoint_union_fits_public_result_contract(
    maximum_disjoint_pair: FiniteSetPairRequest,
) -> None:
    result = set_union(maximum_disjoint_pair)

    assert isinstance(result, FiniteSetElementListResult)
    assert len(result.elements) == 256
    assert result.elements == tuple(str(value) for value in range(256))


def test_maximum_disjoint_symmetric_difference_fits_public_result_contract(
    maximum_disjoint_pair: FiniteSetPairRequest,
) -> None:
    result = set_symmetric_difference(maximum_disjoint_pair)

    assert isinstance(result, FiniteSetElementListResult)
    assert len(result.elements) == 256
    assert result.elements == tuple(str(value) for value in range(256))


def test_maximum_disjoint_union_cardinality_fits_public_result_contract(
    maximum_disjoint_pair: FiniteSetPairRequest,
) -> None:
    result = union_cardinality(maximum_disjoint_pair)

    assert isinstance(result, FiniteSetCardinalityResult)
    assert result.cardinality == 256
