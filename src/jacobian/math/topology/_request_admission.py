"""Request-time admission for finite simplicial topology operations."""

from __future__ import annotations

from collections.abc import Callable

from pydantic_core import PydanticCustomError

from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.topology._models import (
    MAX_TOPOLOGY_DIMENSION,
    SimplicialComplexRequest,
    _require_request_complex,
)


def run_topology_admission[T](
    admission: Callable[[], T], *, location: tuple[str | int, ...]
) -> T:
    """Normalize owner semantic failures at the public operation boundary."""

    try:
        return admission()
    except OperationDomainValidationError:
        raise
    except PydanticCustomError as exc:
        raise OperationDomainValidationError(
            location=location,
            code=exc.type,
            message=exc.message(),
        ) from exc
    except ValueError as exc:
        raise OperationDomainValidationError(
            location=location,
            code="topology.request_not_admitted",
            message=str(exc),
        ) from exc


def require_complex_admission(request: SimplicialComplexRequest) -> None:
    """Check semantic complex bounds immediately before a kernel runs."""

    def admit() -> None:
        if any(
            not 1 <= len(facet) <= MAX_TOPOLOGY_DIMENSION + 1
            for facet in request.facets
        ):
            raise ValueError(
                "each facet must contain between 1 and "
                f"{MAX_TOPOLOGY_DIMENSION + 1} vertices"
            )
        _require_request_complex(request.vertices, request.facets)

    run_topology_admission(admit, location=("facets",))


__all__ = ["require_complex_admission", "run_topology_admission"]
