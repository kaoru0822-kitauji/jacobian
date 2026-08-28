from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from pydantic import ValidationError

from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.combinatorics._difference_set_models import (
    CyclicDifferenceMultiplicity,
    CyclicDifferenceSetExtensionRequest,
    CyclicPerfectDifferenceSetResult,
    IntegerSidonRequest,
    IntegerSidonResult,
)
from jacobian.math.combinatorics._difference_sets import (
    decide_cyclic_difference_set_extension,
)


@contextmanager
def raises_code(code: str) -> Iterator[None]:
    with pytest.raises(ValidationError) as exc_info:
        yield
    assert exc_info.value.errors()[0]["type"] == code


def test_sidon_request_rejects_duplicate_integer_elements() -> None:
    with raises_code("combinatorics.sidon_invariant"):
        IntegerSidonRequest(elements=("1", "2", "1"))


def test_sidon_result_keeps_structural_normalization() -> None:
    result = IntegerSidonResult(
        normalized_elements=("1", "2", "4"),
        ordered_differences=(),
        is_sidon=True,
    )
    assert result.normalized_elements == ("1", "2", "4")


def test_extension_request_rejects_an_unbounded_candidate_space() -> None:
    request = CyclicDifferenceSetExtensionRequest(
        base_elements=("0", "1", "2", "3", "4", "5", "6"),
        target_order=10,
    )
    with pytest.raises(OperationDomainValidationError) as error:
        decide_cyclic_difference_set_extension(request)
    assert error.value.errors() == (
        {
            "loc": ("base_elements", "target_order"),
            "type": "combinatorics.extension_candidate_space_bound",
            "msg": "extension candidate space exceeds the complete-search bound",
        },
    )


def test_pds_result_accepts_the_canonical_fano_profile() -> None:
    residues = (0, 1, 3)
    modulus = 7
    counts = Counter(
        (left - right) % modulus
        for left in residues
        for right in residues
        if left != right
    )
    profile = tuple(
        CyclicDifferenceMultiplicity(
            residue=residue, multiplicity=counts.get(residue, 0)
        )
        for residue in range(1, modulus)
    )
    missing = tuple(
        residue for residue in range(1, modulus) if counts.get(residue, 0) == 0
    )
    repeated = tuple(
        residue for residue in range(1, modulus) if counts.get(residue, 0) > 1
    )
    result = CyclicPerfectDifferenceSetResult(
        modulus=modulus,
        normalized_residues=residues,
        order=len(residues),
        expected_modulus=modulus,
        difference_multiplicities=profile,
        missing_residues=missing,
        repeated_residues=repeated,
        is_perfect=True,
    )
    assert result.is_perfect is True
