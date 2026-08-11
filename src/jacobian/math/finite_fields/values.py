"""Provider-independent values for exact finite-field linear algebra."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import rfc8785

from jacobian.canonical import sha256_digest
from jacobian.math.prime_field_linear_algebra import PrimeFieldMatrix, rank


def _digest(payload: dict[str, Any]) -> str:
    return sha256_digest(rfc8785.dumps(payload))


@dataclass(frozen=True, slots=True)
class FiniteFieldPresentation:
    """An exact polynomial presentation with a fixed power-basis encoding."""

    characteristic: int
    modulus_coefficients: tuple[int, ...]
    generator: str = "a"
    element_encoding_version: str = "power-basis-v1"

    def __post_init__(self) -> None:
        from sympy import Poly, isprime, symbols

        if type(self.characteristic) is not int or not isprime(self.characteristic):
            raise ValueError("characteristic must be a prime integer")
        if len(self.modulus_coefficients) < 3:
            raise ValueError("finite extension modulus must have degree at least two")
        if self.modulus_coefficients[-1] != 1:
            raise ValueError("modulus must be monic")
        if any(
            type(value) is not int or not 0 <= value < self.characteristic
            for value in self.modulus_coefficients
        ):
            raise ValueError("modulus coefficients must be canonical field residues")
        if not self.generator:
            raise ValueError("generator must be nonempty")
        if self.element_encoding_version != "power-basis-v1":
            raise ValueError("unsupported finite-field element encoding")
        variable = symbols("x")
        polynomial = Poly(
            sum(
                coefficient * variable**power
                for power, coefficient in enumerate(self.modulus_coefficients)
            ),
            variable,
            modulus=self.characteristic,
        )
        if not polynomial.is_irreducible:
            raise ValueError("modulus must be irreducible over the prime field")

    @property
    def degree(self) -> int:
        return len(self.modulus_coefficients) - 1

    @property
    def order(self) -> int:
        return int(pow(self.characteristic, self.degree))

    @property
    def ordered_basis(self) -> tuple[str, ...]:
        return (
            "1",
            self.generator,
            *(f"{self.generator}^{power}" for power in range(2, self.degree)),
        )

    @property
    def digest(self) -> str:
        return _digest(
            {
                "characteristic": self.characteristic,
                "element_encoding_version": self.element_encoding_version,
                "generator": self.generator,
                "modulus_coefficients": list(self.modulus_coefficients),
                "ordered_basis": list(self.ordered_basis),
                "value_type": "finite-field-presentation-v1",
            }
        )


@dataclass(frozen=True, slots=True)
class FiniteFieldElement:
    """Power-basis coordinates bound to one exact field presentation."""

    presentation: FiniteFieldPresentation
    coordinates: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.coordinates) != self.presentation.degree:
            raise ValueError("element coordinates must match the presentation degree")
        if any(
            type(value) is not int or not 0 <= value < self.presentation.characteristic
            for value in self.coordinates
        ):
            raise ValueError("element coordinates must be canonical field residues")

    @property
    def is_zero(self) -> bool:
        return not any(self.coordinates)

    @property
    def is_one(self) -> bool:
        return self.coordinates == (1,) + (0,) * (self.presentation.degree - 1)

    @property
    def digest(self) -> str:
        return _digest(
            {
                "coordinates": list(self.coordinates),
                "presentation": self.presentation.digest,
                "value_type": "finite-field-element-v1",
            }
        )


@dataclass(frozen=True, slots=True)
class Axis:
    """An ordered semantic axis."""

    name: str
    labels: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("axis name must be nonempty")
        if not self.labels or any(not label for label in self.labels):
            raise ValueError("axis labels must be nonempty")
        if len(set(self.labels)) != len(self.labels):
            raise ValueError("axis labels must be unique")

    @property
    def digest(self) -> str:
        return _digest(
            {
                "labels": list(self.labels),
                "name": self.name,
                "value_type": "axis-v1",
            }
        )


@dataclass(frozen=True, slots=True)
class AxisBoundMatrix:
    """An immutable matrix bound to a field presentation and ordered axes."""

    presentation: FiniteFieldPresentation
    row_axis: Axis
    column_axis: Axis
    entries: tuple[tuple[FiniteFieldElement, ...], ...]

    def __post_init__(self) -> None:
        if len(self.entries) != len(self.row_axis.labels):
            raise ValueError("matrix rows must match the row axis")
        if any(len(row) != len(self.column_axis.labels) for row in self.entries):
            raise ValueError("matrix columns must match the column axis")
        if any(
            element.presentation != self.presentation
            for row in self.entries
            for element in row
        ):
            raise ValueError("matrix entries must use the matrix field presentation")

    @property
    def digest(self) -> str:
        return _digest(
            {
                "column_axis": self.column_axis.digest,
                "entries": [
                    [list(element.coordinates) for element in row]
                    for row in self.entries
                ],
                "presentation": self.presentation.digest,
                "row_axis": self.row_axis.digest,
                "value_type": "axis-bound-matrix-v1",
            }
        )


@dataclass(frozen=True, slots=True)
class FiniteDimensionalSubspace:
    """An ordered independent matrix basis over the presentation's prime field."""

    presentation: FiniteFieldPresentation
    basis_axis: Axis
    basis: tuple[AxisBoundMatrix, ...]

    def __post_init__(self) -> None:
        if len(self.basis) != len(self.basis_axis.labels):
            raise ValueError("subspace basis must match its basis axis")
        if not self.basis:
            raise ValueError("subspace basis must be nonempty")
        first = self.basis[0]
        if any(
            matrix.presentation != self.presentation
            or matrix.row_axis != first.row_axis
            or matrix.column_axis != first.column_axis
            for matrix in self.basis
        ):
            raise ValueError("subspace matrices must share their parent and axes")
        flattened = tuple(
            tuple(
                coordinate
                for row in matrix.entries
                for element in row
                for coordinate in element.coordinates
            )
            for matrix in self.basis
        )
        coordinate_rows = tuple(zip(*flattened, strict=True))
        basis_matrix = PrimeFieldMatrix(
            prime=self.presentation.characteristic,
            entries=coordinate_rows,
            columns=len(self.basis),
        )
        if rank(basis_matrix) != len(self.basis):
            raise ValueError("subspace basis matrices must be linearly independent")

    @property
    def row_axis(self) -> Axis:
        return self.basis[0].row_axis

    @property
    def column_axis(self) -> Axis:
        return self.basis[0].column_axis

    @property
    def digest(self) -> str:
        return _digest(
            {
                "basis": [matrix.digest for matrix in self.basis],
                "basis_axis": self.basis_axis.digest,
                "presentation": self.presentation.digest,
                "value_type": "finite-dimensional-subspace-v1",
            }
        )


@dataclass(frozen=True, slots=True)
class ProjectivePoint:
    """A normalized projective point over one field and coordinate axis."""

    presentation: FiniteFieldPresentation
    axis: Axis
    coordinates: tuple[FiniteFieldElement, ...]

    def __post_init__(self) -> None:
        if len(self.coordinates) != len(self.axis.labels):
            raise ValueError("projective coordinates must match their axis")
        if any(
            coordinate.presentation != self.presentation
            for coordinate in self.coordinates
        ):
            raise ValueError("projective coordinates must share their presentation")
        first_nonzero = next(
            (coordinate for coordinate in self.coordinates if not coordinate.is_zero),
            None,
        )
        if first_nonzero is None:
            raise ValueError("projective coordinates cannot all be zero")
        if not first_nonzero.is_one:
            raise ValueError("projective coordinates must be normalized")

    @property
    def digest(self) -> str:
        return _digest(
            {
                "axis": self.axis.digest,
                "coordinates": [list(value.coordinates) for value in self.coordinates],
                "presentation": self.presentation.digest,
                "value_type": "projective-point-v1",
            }
        )


@dataclass(frozen=True, slots=True)
class FiniteLinearMap:
    """A matrix-defined linear map with exact source and target axes."""

    source_axis: Axis
    target_axis: Axis
    matrix: PrimeFieldMatrix

    def __post_init__(self) -> None:
        if self.matrix.columns != len(self.source_axis.labels):
            raise ValueError("linear-map columns must match the source axis")
        if len(self.matrix.entries) != len(self.target_axis.labels):
            raise ValueError("linear-map rows must match the target axis")

    @property
    def digest(self) -> str:
        return _digest(
            {
                "entries": [list(row) for row in self.matrix.entries],
                "prime": self.matrix.prime,
                "source_axis": self.source_axis.digest,
                "target_axis": self.target_axis.digest,
                "value_type": "finite-linear-map-v1",
            }
        )


@dataclass(frozen=True, slots=True)
class RankResult:
    """The exact rank of a direction-bound finite linear map."""

    direction: ProjectivePoint
    linear_map: FiniteLinearMap
    rank: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rank", rank(self.linear_map.matrix))

    @property
    def digest(self) -> str:
        return _digest(
            {
                "direction": self.direction.digest,
                "linear_map": self.linear_map.digest,
                "rank": self.rank,
                "value_type": "rank-result-v1",
            }
        )


@dataclass(frozen=True, slots=True)
class DirectionRankLedger:
    """An ordered, exact binding from projective directions to rank results."""

    subspace: FiniteDimensionalSubspace
    entries: tuple[RankResult, ...]

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValueError("direction-rank ledger must be nonempty")
        first = self.entries[0]
        if len({entry.direction.digest for entry in self.entries}) != len(self.entries):
            raise ValueError("direction-rank ledger cannot repeat a direction")
        if any(
            entry.direction.presentation != first.direction.presentation
            or entry.direction.axis != first.direction.axis
            or entry.linear_map.source_axis != first.linear_map.source_axis
            or entry.linear_map.target_axis != first.linear_map.target_axis
            or entry.linear_map.matrix.prime != first.linear_map.matrix.prime
            for entry in self.entries
        ):
            raise ValueError("direction-rank entries must share their bound semantics")
        if first.direction.presentation != self.subspace.presentation:
            raise ValueError("ledger directions must use the subspace presentation")
        if first.direction.axis != self.subspace.row_axis:
            raise ValueError("ledger directions must use the subspace row axis")
        if first.linear_map.source_axis != self.subspace.basis_axis:
            raise ValueError("ledger maps must use the subspace basis axis")

    @property
    def digest(self) -> str:
        return _digest(
            {
                "entries": [entry.digest for entry in self.entries],
                "subspace": self.subspace.digest,
                "value_type": "direction-rank-ledger-v1",
            }
        )


@dataclass(frozen=True, slots=True)
class OrbitDistribution:
    """Orbit-size counts derived from one exact direction-rank ledger."""

    ledger: DirectionRankLedger
    counts: tuple[tuple[int, int], ...] = field(init=False)

    def __post_init__(self) -> None:
        first = self.ledger.entries[0]
        presentation = first.direction.presentation
        expected_directions = (
            presentation.order ** len(first.direction.axis.labels) - 1
        ) // (presentation.order - 1)
        if len(self.ledger.entries) != expected_directions:
            raise ValueError("orbit aggregation requires every projective direction")
        prime = presentation.characteristic
        target_dimension = len(first.linear_map.target_axis.labels)
        counts: dict[int, int] = {1: expected_directions}
        for entry in self.ledger.entries:
            orbit_size = prime**entry.rank
            counts[orbit_size] = counts.get(orbit_size, 0) + prime ** (
                target_dimension - entry.rank
            )
        object.__setattr__(self, "counts", tuple(sorted(counts.items())))

    @property
    def digest(self) -> str:
        return _digest(
            {
                "counts": [list(item) for item in self.counts],
                "ledger": self.ledger.digest,
                "value_type": "orbit-distribution-v1",
            }
        )
