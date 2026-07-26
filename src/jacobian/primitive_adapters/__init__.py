"""Thin pinned SymPy/NetworkX primitive adapter factory entrypoints.

Each submodule exposes a ``factory(kernel)`` entrypoint returning a tuple of
:class:`CapabilityAdapter` instances that expose one exact deterministic
mathematical outcome.  Adapters report ``COMPUTED`` assurance and never
self-verify; independent checker replay is an explicit open obligation.

Load individual families via the kernel's ``capability_adapter_entrypoints``
parameter, e.g. ``jacobian.primitive_adapters.number_theory:factory``, or load
all fifty at once via :func:`factory`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jacobian.primitive_adapters.combinatorics import factory as _combinatorics
from jacobian.primitive_adapters.graph_invariants import factory as _graph
from jacobian.primitive_adapters.integer_polynomial import factory as _integer_poly
from jacobian.primitive_adapters.matrix_invariants import factory as _matrix
from jacobian.primitive_adapters.number_theory import factory as _number_theory
from jacobian.primitive_adapters.rational_polynomial import factory as _rational_poly

if TYPE_CHECKING:
    from jacobian.capabilities import CapabilityAdapter
    from jacobian.kernel import JacobianKernel


def factory(kernel: JacobianKernel) -> tuple[CapabilityAdapter, ...]:
    """Build all fifty primitive adapters across six domain families."""
    return (
        *_number_theory(kernel),
        *_combinatorics(kernel),
        *_integer_poly(kernel),
        *_rational_poly(kernel),
        *_matrix(kernel),
        *_graph(kernel),
    )
