from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.arithmetic import (
    RealQuadraticOrderRequest,
    RealQuadraticValue,
)


def _value(radicand: int, *, digits: int = 1) -> RealQuadraticValue:
    return RealQuadraticValue(
        rational_part={"num": "1" * digits, "den": "1"},
        radical_coefficient={"num": "1", "den": "2"},
        radicand=radicand,
    )


def test_real_quadratic_value_rejects_a_non_square_free_radicand() -> None:
    with pytest.raises(ValidationError, match="radicand must be square-free"):
        _value(12)


def test_real_quadratic_request_requires_one_shared_radicand() -> None:
    with pytest.raises(ValidationError, match="one shared radicand"):
        RealQuadraticOrderRequest(left=_value(2), right=_value(3))


def test_real_quadratic_value_enforces_its_operation_digit_bound() -> None:
    with pytest.raises(ValidationError, match="exceeds the 256-digit bound"):
        _value(3, digits=257)
