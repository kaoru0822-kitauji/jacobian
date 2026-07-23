from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from jacobian.canonical import (
    CanonicalizationError,
    CanonicalLimits,
    canonicalize_json,
)
from jacobian.contracts.exact import CanonicalRational


@pytest.mark.contract
def test_equivalent_rationals_have_identical_canonical_bytes() -> None:
    first = canonicalize_json({"weight": {"num": "2", "den": "4"}})
    second = canonicalize_json({"weight": {"num": "1", "den": "2"}})

    assert first == second == b'{"weight":{"den":"2","num":"1"}}'


@pytest.mark.contract
@pytest.mark.parametrize(
    "value",
    [
        {"weight": 0.5},
        '{"x": 1, "x": 2}',
        {"weight": {"num": "1", "den": "0"}},
    ],
)
def test_ambiguous_or_inexact_json_is_rejected(value: object) -> None:
    with pytest.raises(CanonicalizationError):
        canonicalize_json(value)


@pytest.mark.contract
def test_canonical_rational_wire_model_rejects_unreduced_input() -> None:
    with pytest.raises(ValidationError):
        CanonicalRational.model_validate({"num": "2", "den": "4"})


@pytest.mark.contract
def test_num_den_is_a_reserved_exact_rational_shape() -> None:
    assert canonicalize_json({"num": "2", "den": "4"}) == canonicalize_json(
        {"num": "1", "den": "2"}
    )


@pytest.mark.contract
def test_unicode_bom_and_non_json_tuples_are_rejected() -> None:
    with pytest.raises(CanonicalizationError):
        canonicalize_json(b'\xef\xbb\xbf{"value":1}')
    with pytest.raises(CanonicalizationError):
        canonicalize_json({"value": (1, 2)})


@pytest.mark.contract
@pytest.mark.conformance
def test_nesting_beyond_the_configured_limit_is_rejected() -> None:
    with pytest.raises(CanonicalizationError, match="depth"):
        canonicalize_json(
            {"a": {"b": {"c": {"d": 1}}}},
            limits=CanonicalLimits(max_depth=2),
        )


@pytest.mark.contract
@pytest.mark.property
@given(
    numerator=st.integers(min_value=-(10**100), max_value=10**100),
    denominator=st.integers(min_value=1, max_value=10**50),
    scale=st.integers(min_value=1, max_value=10**12),
)
def test_scaled_rationals_have_the_same_canonical_bytes(
    numerator: int,
    denominator: int,
    scale: int,
) -> None:
    reduced = canonicalize_json({"num": str(numerator), "den": str(denominator)})
    scaled = canonicalize_json(
        {
            "num": str(numerator * scale),
            "den": str(denominator * scale),
        }
    )

    assert scaled == reduced
