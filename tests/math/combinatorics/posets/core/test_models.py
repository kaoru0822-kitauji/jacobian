from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.combinatorics.posets.core._models import (
    FinitePoset,
    FinitePosetMaterializationResult,
    FinitePosetRequest,
    LinearExtensionRequest,
    MobiusFunctionRequest,
)
from jacobian.math.combinatorics.posets.core._operations import (
    _linear_extensions,
    _materialized_poset,
)
from jacobian.math.combinatorics.posets.core._tools import TOOLS


def _materialize(elements: list[str], relation: list[tuple[str, str]]) -> FinitePoset:
    operation = next(
        operation
        for operation in TOOLS
        if operation.operation_id == "poset.finite.compute"
    )
    outcome = operation.run(
        FinitePosetRequest.model_validate(
            {
                "elements": elements,
                "relation": [
                    {"lower": lower, "upper": upper} for lower, upper in relation
                ],
                "interpretation": "COVER_EDGES",
            }
        )
    )
    assert isinstance(outcome, FinitePosetMaterializationResult)
    return outcome.poset


def _assert_code(exc: pytest.ExceptionInfo[ValidationError], code: str) -> None:
    assert exc.value.errors()[0]["type"] == code


def _assert_operation_code(
    exc: pytest.ExceptionInfo[OperationDomainValidationError], code: str
) -> None:
    assert exc.value.errors()[0]["type"] == code


def test_cover_relation_rejects_cycles_and_redundant_edges() -> None:
    with pytest.raises(OperationDomainValidationError) as exc:
        _materialized_poset(
            FinitePosetRequest.model_validate(
                {
                    "elements": ["a", "b"],
                    "relation": [
                        {"lower": "a", "upper": "b"},
                        {"lower": "b", "upper": "a"},
                    ],
                    "interpretation": "COVER_EDGES",
                }
            )
        )
    _assert_operation_code(exc, "poset.relation_antisymmetric")
    with pytest.raises(OperationDomainValidationError) as exc:
        _materialized_poset(
            FinitePosetRequest.model_validate(
                {
                    "elements": ["a", "b", "c"],
                    "relation": [
                        {"lower": "a", "upper": "b"},
                        {"lower": "b", "upper": "c"},
                        {"lower": "a", "upper": "c"},
                    ],
                    "interpretation": "COVER_EDGES",
                }
            )
        )
    _assert_operation_code(exc, "poset.cover_edges_transitive_redundancy")


def test_comparable_pairs_require_complete_transitive_relation() -> None:
    with pytest.raises(OperationDomainValidationError) as exc:
        _materialized_poset(
            FinitePosetRequest.model_validate(
                {
                    "elements": ["a", "b", "c"],
                    "relation": [
                        {"lower": "a", "upper": "b"},
                        {"lower": "b", "upper": "c"},
                    ],
                    "interpretation": "COMPARABLE_PAIRS",
                }
            )
        )
    _assert_operation_code(exc, "poset.comparable_pairs_complete")


def test_required_reflexive_policy_binds_the_entire_diagonal() -> None:
    with pytest.raises(OperationDomainValidationError) as exc:
        _materialized_poset(
            FinitePosetRequest.model_validate(
                {
                    "elements": ["a", "b"],
                    "relation": [{"lower": "a", "upper": "a"}],
                    "interpretation": "COMPARABLE_PAIRS",
                    "reflexive_pairs": "REQUIRED",
                }
            )
        )
    _assert_operation_code(exc, "poset.required_reflexive_full_carrier")


def test_linear_extension_contract_has_a_separate_exponential_bound() -> None:
    antichain = _materialize([f"x{index}" for index in range(21)], [])
    request = LinearExtensionRequest(poset=antichain)
    with pytest.raises(OperationDomainValidationError) as exc:
        _linear_extensions(request)
    _assert_operation_code(exc, "poset.linear_extension_size_bound")


def test_selected_mobius_scope_rejects_nonintervals_and_empty_selection() -> None:
    poset = _materialize(["a", "b"], [])
    with pytest.raises(ValidationError) as exc:
        MobiusFunctionRequest.model_validate(
            {"poset": poset, "scope": "SELECTED_INTERVALS"}
        )
    _assert_code(exc, "poset.selected_scope_nonempty")
    with pytest.raises(ValidationError) as exc:
        MobiusFunctionRequest.model_validate(
            {
                "poset": poset,
                "scope": "SELECTED_INTERVALS",
                "intervals": [{"lower": "a", "upper": "b"}],
            }
        )
    _assert_code(exc, "poset.interval_is_comparable")
