"""Exact finite-set operations over canonical integers."""

from __future__ import annotations

from typing import cast

from jacobian.contracts.finite_sets import (
    FiniteSetBooleanResult,
    FiniteSetCardinalityResult,
    FiniteSetElementListResult,
    FiniteSetPairRequest,
)
from jacobian.contracts.results import ContractModel


def _pair(request: ContractModel) -> tuple[set[int], set[int]]:
    pair = cast(FiniteSetPairRequest, request)
    return (
        {int(element) for element in pair.left.elements},
        {int(element) for element in pair.right.elements},
    )


def _element_list(values: set[int]) -> FiniteSetElementListResult:
    return FiniteSetElementListResult(
        elements=tuple(str(value) for value in sorted(values)),
    )


def set_union(request: ContractModel) -> ContractModel:
    left, right = _pair(request)
    return _element_list(left | right)


def set_intersection(request: ContractModel) -> ContractModel:
    left, right = _pair(request)
    return _element_list(left & right)


def set_difference(request: ContractModel) -> ContractModel:
    left, right = _pair(request)
    return _element_list(left - right)


def set_symmetric_difference(request: ContractModel) -> ContractModel:
    left, right = _pair(request)
    return _element_list(left ^ right)


def decide_subset(request: ContractModel) -> ContractModel:
    left, right = _pair(request)
    return FiniteSetBooleanResult(holds=left <= right)


def decide_proper_subset(request: ContractModel) -> ContractModel:
    left, right = _pair(request)
    return FiniteSetBooleanResult(holds=left < right)


def decide_disjoint(request: ContractModel) -> ContractModel:
    left, right = _pair(request)
    return FiniteSetBooleanResult(holds=left.isdisjoint(right))


def left_cardinality(request: ContractModel) -> ContractModel:
    left, _ = _pair(request)
    return FiniteSetCardinalityResult(cardinality=len(left))


def intersection_cardinality(request: ContractModel) -> ContractModel:
    left, right = _pair(request)
    return FiniteSetCardinalityResult(cardinality=len(left & right))


def union_cardinality(request: ContractModel) -> ContractModel:
    left, right = _pair(request)
    return FiniteSetCardinalityResult(cardinality=len(left | right))
