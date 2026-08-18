"""Domain-owned Markov chain operations."""

from __future__ import annotations

from jacobian._exact import CanonicalRational
from jacobian.math.markov_chain import (
    ergodic_properties,
    stationary_distribution_extremes,
)
from jacobian.math.markov_chain._models import (
    ErgodicDecisionResult,
    ExtremeStationaryDistribution,
    StationaryDistributionResult,
    TransitionMatrixRequest,
)


def compute_stationary_distribution(
    request: TransitionMatrixRequest,
) -> StationaryDistributionResult:
    matrix = [[{"num": c.num, "den": c.den} for c in row] for row in request.matrix]
    extremes = stationary_distribution_extremes(matrix)  # type: ignore[no-untyped-call]
    return StationaryDistributionResult(
        extreme_distributions=tuple(
            ExtremeStationaryDistribution(
                closed_class=closed_class,
                distribution=tuple(
                    CanonicalRational.from_integer_ratio(int(value.p), int(value.q))
                    for value in distribution
                ),
            )
            for closed_class, distribution in extremes
        ),
        unique=len(extremes) == 1,
    )


def compute_ergodic_decision(request: TransitionMatrixRequest) -> ErgodicDecisionResult:
    matrix = [[{"num": c.num, "den": c.den} for c in row] for row in request.matrix]
    irreducible, aperiodic = ergodic_properties(matrix)  # type: ignore[no-untyped-call]
    return ErgodicDecisionResult(
        is_ergodic=irreducible and aperiodic,
        is_irreducible=irreducible,
        is_aperiodic=aperiodic,
    )
