"""Sequence search and frequency capabilities over finite integer sequences."""

from jacobian.contracts.sequences import (
    IntegerSequenceFrequenciesResult,
    IntegerSequenceIndexListResult,
    IntegerSequenceRequest,
)
from jacobian.domains.sequences._support import sequence_operation
from jacobian.domains.sequences.operations import (
    frequencies,
    zero_indices,
)

SEQUENCE_SEARCH_CAPABILITIES = (
    sequence_operation(
        "sequence.compute.frequencies",
        "Compute value frequencies",
        "Count each distinct value in a finite integer sequence.",
        IntegerSequenceRequest,
        IntegerSequenceFrequenciesResult,
        frequencies,
        "sequence",
        "counting",
    ),
    sequence_operation(
        "sequence.compute.zero_indices",
        "Locate zero terms",
        "Return zero-based indices whose sequence value is zero.",
        IntegerSequenceRequest,
        IntegerSequenceIndexListResult,
        zero_indices,
        "sequence",
        "search",
    ),
)
