from __future__ import annotations

import copy

import pytest

from jacobian.catalog.catalog import Catalog
from jacobian.catalog.models import OperationDomainValidationError
from jacobian.dispatch import invoke_operation


def _example_payload(operation_id: str) -> dict[str, object]:
    operation = Catalog.open().operation(operation_id)
    assert operation is not None
    assert operation.examples
    return copy.deepcopy(operation.examples[0].input)


def test_universal_algebra_assignment_admission_is_typed() -> None:
    operation_id = "universal_algebra.term.evaluate.compute"
    payload = _example_payload(operation_id)
    payload["assignment"] = [0]

    with pytest.raises(OperationDomainValidationError) as caught:
        invoke_operation(operation_id, payload, Catalog.open())

    assert caught.value.errors() == (
        {
            "loc": ("assignment",),
            "type": "universal_algebra.assignment_coverage",
            "msg": "assignment must cover exactly the referenced variables",
        },
    )


def test_edge_path_continuity_admission_is_typed() -> None:
    operation_id = "topology.simplicial.edge_path.word.compute"
    payload = _example_payload(operation_id)
    path = payload["path"]
    assert isinstance(path, list)
    path[1] = {"edge_index": 2, "orientation": 1}

    with pytest.raises(OperationDomainValidationError) as caught:
        invoke_operation(operation_id, payload, Catalog.open())

    assert caught.value.errors()[0]["loc"] == ("path",)
    assert caught.value.errors()[0]["type"] == "topology.edge_path.path_continuity"


def test_orthogonal_recurrence_admission_is_typed() -> None:
    operation_id = "orthogonal_polynomial.recurrence.compute"
    payload = _example_payload(operation_id)
    family = payload["family"]
    assert isinstance(family, dict)
    polynomials = family["polynomials"]
    assert isinstance(polynomials, list)
    first = polynomials[0]
    assert isinstance(first, dict)
    first["squared_norm"] = {"num": "0", "den": "1"}
    family["is_quasi_definite"] = False
    family["is_positive_definite"] = False

    with pytest.raises(OperationDomainValidationError) as caught:
        invoke_operation(operation_id, payload, Catalog.open())

    assert caught.value.errors()[0]["loc"] == ("family",)
    assert caught.value.errors()[0]["type"] == "moments_orthogonal.zero_norm"
