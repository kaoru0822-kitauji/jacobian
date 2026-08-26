"""Public dispatch regressions for additive-combinatorics admission."""

import pytest

from jacobian.catalog.catalog import Catalog
from jacobian.dispatch import OperationRequestValidationError, invoke_operation


def test_direct_sum_rejects_an_oversized_complete_diagnostic_before_execution():
    """The public boundary reports output admission, not post-run transport failure."""

    with pytest.raises(OperationRequestValidationError) as exc_info:
        invoke_operation(
            "additive.direct_sum_predicate.compute",
            {
                "modulus": 1_200_000,
                "left": {"elements": []},
                "right": {"elements": []},
            },
            Catalog.open(),
        )

    assert exc_info.value.errors()[0]["type"] == (
        "additive_combinatorics.direct_sum_result_transport_exceeded"
    )
