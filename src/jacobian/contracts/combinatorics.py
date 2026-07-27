"""Named Pydantic wire contracts for exact combinatorics capabilities."""

from __future__ import annotations

from typing import Self

from pydantic import Field, StrictInt, model_validator

from jacobian.contracts.exact import CanonicalInteger, CanonicalRational
from jacobian.contracts.results import ContractModel

_MAX_N = 1_000
_MAX_PARTS = 256
_MAX_PARTITION_N = 30
_MAX_ENUMERATED_PARTITIONS = 10_000


class NonnegativeIntegerRequest(ContractModel):
    n: StrictInt = Field(ge=0, le=_MAX_N)


class NonnegativePairRequest(ContractModel):
    n: StrictInt = Field(ge=0, le=_MAX_N)
    k: StrictInt = Field(ge=0, le=_MAX_N)


class IntegerListRequest(ContractModel):
    values: tuple[CanonicalInteger, ...] = Field(min_length=1, max_length=_MAX_PARTS)

    @model_validator(mode="after")
    def require_nonnegative_parts(self) -> Self:
        if any(int(v) < 0 for v in self.values):
            raise ValueError("integer list values must be nonnegative")
        return self


class IntegerResult(ContractModel):
    value: CanonicalInteger


class RationalResult(ContractModel):
    value: CanonicalRational


class FibonacciPairResult(ContractModel):
    """Two consecutive Fibonacci values forming one recurrence boundary."""

    n: StrictInt = Field(ge=0, le=10_000)
    f_n: CanonicalInteger
    f_n_plus_one: CanonicalInteger


class FibonacciPairRequest(ContractModel):
    n: StrictInt = Field(ge=0, le=10_000)


class IntegerPartitionEnumerationRequest(ContractModel):
    """Enumerate every partition of n containing at most max_parts summands."""

    n: StrictInt = Field(ge=0, le=_MAX_PARTITION_N)
    max_parts: StrictInt = Field(ge=1, le=_MAX_PARTITION_N)


class IntegerPartitionEnumerationResult(ContractModel):
    """Complete canonical partition enumeration for one bounded request."""

    n: StrictInt = Field(ge=0, le=_MAX_PARTITION_N)
    max_parts: StrictInt = Field(ge=1, le=_MAX_PARTITION_N)
    partitions: tuple[tuple[StrictInt, ...], ...] = Field(
        max_length=_MAX_ENUMERATED_PARTITIONS
    )

    @model_validator(mode="after")
    def require_canonical_complete_items(self) -> Self:
        previous: tuple[int, ...] | None = None
        for partition in self.partitions:
            if len(partition) > self.max_parts:
                raise ValueError("partition exceeds max_parts")
            if any(part <= 0 for part in partition):
                raise ValueError("partition parts must be positive")
            if tuple(sorted(partition, reverse=True)) != partition:
                raise ValueError("partition parts must be nonincreasing")
            if sum(partition) != self.n:
                raise ValueError("partition parts must sum to n")
            if previous is not None and previous <= partition:
                raise ValueError(
                    "partitions must be unique in descending lexicographic order"
                )
            previous = tuple(partition)
        if self.n == 0 and self.partitions != ((),):
            raise ValueError("zero has exactly one empty partition")
        return self
