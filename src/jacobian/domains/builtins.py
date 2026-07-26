"""Explicit built-in domain portfolio."""

from jacobian.domains.arithmetic import ARITHMETIC_BUNDLE
from jacobian.domains.combinatorics import COMBINATORICS_BUNDLE
from jacobian.domains.finite_sets import FINITE_SET_BUNDLE
from jacobian.domains.geometry import GEOMETRY_BUNDLE
from jacobian.domains.graph_optimization import GRAPH_OPTIMIZATION_BUNDLE
from jacobian.domains.number_theory import NUMBER_THEORY_BUNDLE
from jacobian.domains.sequences import SEQUENCE_BUNDLE

BUILTIN_DOMAIN_BUNDLES = (
    ARITHMETIC_BUNDLE,
    NUMBER_THEORY_BUNDLE,
    COMBINATORICS_BUNDLE,
    FINITE_SET_BUNDLE,
    SEQUENCE_BUNDLE,
    GEOMETRY_BUNDLE,
    GRAPH_OPTIMIZATION_BUNDLE,
)

__all__ = ["BUILTIN_DOMAIN_BUNDLES"]
