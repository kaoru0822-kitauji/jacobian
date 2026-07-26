"""Sequence predicate capabilities over finite integer sequences."""

from jacobian.contracts.sequences import (
    IntegerSequenceBooleanResult,
    IntegerSequenceRequest,
)
from jacobian.domains.sequences._support import sequence_operation
from jacobian.domains.sequences.operations import (
    decide_arithmetic,
    decide_geometric,
    decide_nondecreasing,
    decide_strictly_increasing,
)

SEQUENCE_PREDICATE_CAPABILITIES = (
    sequence_operation(
        "sequence.decide.arithmetic",
        "Decide arithmetic progression",
        "Decide whether consecutive terms have one common difference.",
        IntegerSequenceRequest,
        IntegerSequenceBooleanResult,
        decide_arithmetic,
        "sequence",
        "predicate",
    ),
    sequence_operation(
        "sequence.decide.geometric",
        "Decide geometric progression",
        "Decide whether a finite integer sequence has a consistent rational ratio.",
        IntegerSequenceRequest,
        IntegerSequenceBooleanResult,
        decide_geometric,
        "sequence",
        "predicate",
    ),
    sequence_operation(
        "sequence.decide.nondecreasing",
        "Decide nondecreasing order",
        "Decide whether every term is at least its predecessor.",
        IntegerSequenceRequest,
        IntegerSequenceBooleanResult,
        decide_nondecreasing,
        "sequence",
        "predicate",
    ),
    sequence_operation(
        "sequence.decide.strictly_increasing",
        "Decide strict increase",
        "Decide whether every term is greater than its predecessor.",
        IntegerSequenceRequest,
        IntegerSequenceBooleanResult,
        decide_strictly_increasing,
        "sequence",
        "predicate",
    ),
)
