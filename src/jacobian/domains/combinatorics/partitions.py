"""Partition-owned exact combinatorics capabilities."""

from jacobian.contracts.combinatorics import (
    IntegerPartitionEnumerationRequest,
    IntegerPartitionEnumerationResult,
    IntegerResult,
    NonnegativeIntegerRequest,
    NonnegativePairRequest,
)
from jacobian.domains._examples import example
from jacobian.domains.combinatorics._support import (
    combinatorics_operation,
)
from jacobian.domains.combinatorics.operations import (
    bell,
    enumerate_integer_partitions,
    partition_number,
    stirling_first,
    stirling_second,
)

PARTITION_CAPABILITIES = (
    combinatorics_operation(
        "combinatorics.compute.stirling_first",
        "Compute Stirling number of first kind",
        "Count permutations of n elements with k cycles, unsigned.",
        NonnegativePairRequest,
        IntegerResult,
        stirling_first,
        "combinatorics",
        "partition",
    ),
    combinatorics_operation(
        "combinatorics.compute.stirling_second",
        "Compute Stirling number of second kind",
        "Count partitions of n labeled elements into k nonempty blocks.",
        NonnegativePairRequest,
        IntegerResult,
        stirling_second,
        "combinatorics",
        "partition",
    ),
    combinatorics_operation(
        "combinatorics.compute.bell",
        "Compute Bell number",
        "Count set partitions of n labeled elements.",
        NonnegativeIntegerRequest,
        IntegerResult,
        bell,
        "combinatorics",
        "partition",
    ),
    combinatorics_operation(
        "combinatorics.compute.partition_number",
        "Compute partition number",
        "Count unordered additive partitions of n.",
        NonnegativeIntegerRequest,
        IntegerResult,
        partition_number,
        "combinatorics",
        "partition",
    ),
    combinatorics_operation(
        "combinatorics.enumerate.integer_partitions",
        "Enumerate integer partitions",
        (
            "Enumerate every partition of bounded n containing at most "
            "max_parts summands, in canonical descending order."
        ),
        IntegerPartitionEnumerationRequest,
        IntegerPartitionEnumerationResult,
        enumerate_integer_partitions,
        "combinatorics",
        "partition",
        "enumeration",
        invocation_examples=(
            example(
                "partitions_of_5_with_two_parts",
                "Enumerate partitions of 5 using at most two parts.",
                {"n": 5, "max_parts": 2},
            ),
        ),
    ),
)
