"""MILP surface used by discrepancy-theory operations."""

from collections.abc import Mapping
from typing import Any

class Bounds:
    def __init__(self, lb: Any, ub: Any) -> None: ...

class LinearConstraint:
    def __init__(self, A: Any, lb: Any, ub: Any) -> None: ...

class OptimizeResult:
    status: int
    x: Any | None

def milp(
    *,
    c: Any,
    integrality: Any = ...,
    bounds: Bounds | None = ...,
    constraints: LinearConstraint | None = ...,
    options: Mapping[str, object] | None = ...,
) -> OptimizeResult: ...
