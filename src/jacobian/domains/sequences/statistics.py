"""Sequence statistic capabilities producing rational results."""

from jacobian.contracts.sequences import (
    IntegerSequenceRationalResult,
    IntegerSequenceRequest,
)
from jacobian.domains.sequences._support import sequence_operation
from jacobian.domains.sequences.operations import (
    sequence_mean,
    sequence_median,
)

SEQUENCE_STATISTIC_CAPABILITIES = (
    sequence_operation(
        "sequence.compute.mean",
        "Compute sequence mean",
        "Compute the reduced arithmetic mean of a finite integer sequence.",
        IntegerSequenceRequest,
        IntegerSequenceRationalResult,
        sequence_mean,
        "sequence",
        "statistic",
    ),
    sequence_operation(
        "sequence.compute.median",
        "Compute sequence median",
        "Compute the reduced median of a finite integer sequence.",
        IntegerSequenceRequest,
        IntegerSequenceRationalResult,
        sequence_median,
        "sequence",
        "statistic",
    ),
)
