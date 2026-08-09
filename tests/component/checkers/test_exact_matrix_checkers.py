from __future__ import annotations

import copy
from typing import Any

from tests.component.checkers.exact_domain_checker_support import (
    _MATRIX_CASES,
    _qq,
)
from tests.support.artifacts import canonical_digest as _digest
from tests.support.rationals import rational_payload as _q

from jacobian_checkers.exact_domain_operations import (
    check_matrix_nullspace,
    check_matrix_product,
)


def _matrix_product_checker_request() -> dict[str, Any]:
    return copy.deepcopy(
        next(
            checker_request
            for checker, checker_request in _MATRIX_CASES
            if checker is check_matrix_product
        )
    )


def _derived_matrix_product_checker_request() -> dict[str, Any]:
    checker_request = _matrix_product_checker_request()
    checker_request["claim"]["payload"] = {
        "left": _qq([[1, 2, 0], [0, 1, 1]]),
        "right": None,
        "derived_operand": {
            "operand_derivation_version": "1",
            "source": "LEFT",
            "target": "RIGHT",
            "transform": "TRANSPOSE",
        },
    }
    checker_request["claim"]["payload_digest"] = _digest(
        checker_request["claim"]["payload"]
    )
    checker_request["candidate"]["payload"]["product"] = _qq([[5, 2], [2, 2]])
    checker_request["candidate"]["payload_digest"] = _digest(
        checker_request["candidate"]["payload"]
    )
    return checker_request


def test_matrix_product_checker_accepts_bound_transpose_derivation() -> None:
    decision = check_matrix_product(_derived_matrix_product_checker_request())

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"


def test_matrix_product_checker_rejects_filled_derivation_target() -> None:
    checker_request = _derived_matrix_product_checker_request()
    checker_request["claim"]["payload"]["right"] = _qq([[1, 0], [2, 1], [0, 1]])
    checker_request["claim"]["payload_digest"] = _digest(
        checker_request["claim"]["payload"]
    )

    decision = check_matrix_product(checker_request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_matrix_product_checker_rejects_altered_derivation_transform() -> None:
    checker_request = _derived_matrix_product_checker_request()
    checker_request["claim"]["payload"]["derived_operand"]["transform"] = "IDENTITY"
    checker_request["claim"]["payload_digest"] = _digest(
        checker_request["claim"]["payload"]
    )

    decision = check_matrix_product(checker_request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_matrix_nullspace_checker_rejects_wrong_rank() -> None:
    checker_request = copy.deepcopy(
        next(
            checker_request
            for checker, checker_request in _MATRIX_CASES
            if checker is check_matrix_nullspace
        )
    )
    checker_request["candidate"]["payload"]["rank"] = 2
    checker_request["candidate"]["payload_digest"] = _digest(
        checker_request["candidate"]["payload"]
    )

    decision = check_matrix_nullspace(checker_request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_matrix_product_checker_rejects_wrong_entry() -> None:
    checker_request = _matrix_product_checker_request()
    checker_request["candidate"]["payload"]["product"]["entries"][0][0] = _q(2)
    checker_request["candidate"]["payload_digest"] = _digest(
        checker_request["candidate"]["payload"]
    )

    decision = check_matrix_product(checker_request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_matrix_product_checker_rejects_wrong_shape_binding() -> None:
    checker_request = _matrix_product_checker_request()
    checker_request["candidate"]["payload"]["inner_dimension"] = 2
    checker_request["candidate"]["payload_digest"] = _digest(
        checker_request["candidate"]["payload"]
    )

    decision = check_matrix_product(checker_request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_matrix_product_checker_rejects_oversized_source() -> None:
    checker_request = _matrix_product_checker_request()
    checker_request["claim"]["payload"]["left"] = _qq([[1]] * 33)
    checker_request["claim"]["payload_digest"] = _digest(
        checker_request["claim"]["payload"]
    )

    decision = check_matrix_product(checker_request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"
