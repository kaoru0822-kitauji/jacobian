from __future__ import annotations

import pytest

from jacobian.catalog.catalog import Catalog
from jacobian.catalog.models import OperationDiscoveryRequest


@pytest.mark.parametrize(
    ("query", "operation_id", "unrelated_operation_ids"),
    (
        (
            "proper divisors",
            "integer.compute.divisors",
            ("number_theory.binary_quadratic_form.proper_equivalence.decide",),
        ),
        (
            "aliquot proper divisor list",
            "integer.compute.divisors",
            (
                "graph.chip_firing.canonical_divisor.compute",
                "number_theory.binary_quadratic_form.proper_equivalence.decide",
            ),
        ),
        (
            "sum of proper divisors",
            "integer.compute.divisor_sum",
            ("additive.multiset_sum.representation_profile.compute",),
        ),
        (
            "aliquot sum",
            "integer.compute.divisor_sum",
            ("additive.multiset_sum.representation_profile.compute",),
        ),
    ),
)
def test_proper_divisor_language_ranks_complete_divisor_operations_first(
    query: str,
    operation_id: str,
    unrelated_operation_ids: tuple[str, ...],
) -> None:
    result = Catalog.open().search(OperationDiscoveryRequest(query=query, limit=8))
    positions = {
        match.operation_id: index for index, match in enumerate(result.matches)
    }

    assert result.matches[0].operation_id == operation_id
    assert set(unrelated_operation_ids) <= positions.keys()
    assert all(
        positions[operation_id] < positions[unrelated_operation_id]
        for unrelated_operation_id in unrelated_operation_ids
    )


@pytest.mark.parametrize(
    ("query", "operation_id"),
    (
        ("positive divisors", "integer.compute.divisors"),
        ("sum positive divisors", "integer.compute.divisor_sum"),
    ),
)
def test_positive_divisor_language_keeps_existing_first_rank(
    query: str,
    operation_id: str,
) -> None:
    result = Catalog.open().search(OperationDiscoveryRequest(query=query, limit=8))

    assert result.matches[0].operation_id == operation_id


def test_proper_divisor_aliases_preserve_complete_result_postconditions() -> None:
    catalog = Catalog.open()
    divisors = catalog.operation("integer.compute.divisors")
    divisor_sum = catalog.operation("integer.compute.divisor_sum")

    assert divisors is not None
    assert "every positive divisor" in divisors.description
    assert "proper-divisor" in divisors.description
    assert "aliquot proper-divisor list" in divisors.description
    assert "by removing the input itself" not in divisors.description
    assert divisor_sum is not None
    assert "every positive divisor" in divisor_sum.description
    assert "proper-divisor sum" in divisor_sum.description
    assert "aliquot sum" in divisor_sum.description
    assert "by subtracting the input integer" not in divisor_sum.description
