from __future__ import annotations

import pytest

from jacobian.contracts.arithmetic import RealQuadraticOrderRequest
from jacobian.domains.arithmetic.quadratic import compute_real_quadratic_order


def _value(a: int, b: int) -> dict[str, object]:
    return {
        "rational_part": {"num": str(a), "den": "1"},
        "radical_coefficient": {"num": str(b), "den": "1"},
        "radicand": 2,
    }


@pytest.mark.parametrize(
    ("left", "right", "order", "basis"),
    (
        (_value(1, 0), _value(2, 0), "LT", "RATIONAL_ONLY"),
        (_value(1, 1), _value(0, 0), "GT", "SAME_SIGN"),
        (_value(1, -1), _value(1, -1), "EQ", "RATIONAL_ONLY"),
    ),
)
def test_real_quadratic_order_covers_exact_sign_structures(
    left: dict[str, object],
    right: dict[str, object],
    order: str,
    basis: str,
) -> None:
    result = compute_real_quadratic_order(
        RealQuadraticOrderRequest(left=left, right=right)
    )

    assert result.order == order
    assert result.sign_basis == basis
