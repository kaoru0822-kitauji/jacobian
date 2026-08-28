from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from pydantic import ValidationError

from jacobian.math.combinatorics._difference_set_models import (
    CyclicDifferenceMultiplicity,
    CyclicDifferenceSetExtensionRequest,
    CyclicDifferenceSetExtensionResult,
    CyclicPerfectDifferenceSetResult,
    IntegerSidonRequest,
)


@contextmanager
def raises_code(code: str) -> Iterator[None]:
    with pytest.raises(ValidationError) as exc_info:
        yield
    assert exc_info.value.errors()[0]["type"] == code


def test_sidon_request_rejects_duplicate_integer_elements() -> None:
    with raises_code("combinatorics.sidon_invariant"):
        IntegerSidonRequest(elements=("1", "2", "1"))


def test_extension_request_rejects_an_unbounded_candidate_space() -> None:
    with raises_code("combinatorics.extension_invariant"):
        CyclicDifferenceSetExtensionRequest(
            base_elements=("0", "1", "2", "3", "4", "5", "6"),
            target_order=10,
        )


def test_negative_extension_result_binds_exact_candidate_count() -> None:
    with raises_code("combinatorics.extension_invariant"):
        CyclicDifferenceSetExtensionResult(
            target_order=6,
            modulus=31,
            base_residues=(1, 2, 4, 8, 13),
            candidate_space_size=25,
            decision="DOES_NOT_EXTEND",
            extension=(),
            coverage="ALL_CANDIDATES",
        )


def test_positive_extension_result_rejects_residue_outside_modulus() -> None:
    with raises_code("combinatorics.extension_invariant"):
        CyclicDifferenceSetExtensionResult(
            target_order=3,
            modulus=7,
            base_residues=(0, 1),
            candidate_space_size=5,
            decision="EXTENDS",
            extension=(0, 1, 7),
            coverage="WITNESS",
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
