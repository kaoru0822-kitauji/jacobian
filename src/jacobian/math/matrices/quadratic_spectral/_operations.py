"""Wire adapters for exact real-quadratic matrix spectra."""

from collections.abc import Callable

from pydantic_core import PydanticCustomError

from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.matrices.quadratic_spectral._models import (
    RealQuadraticInertiaRequest,
    RealQuadraticSingularSpectrumRequest,
    RealQuadraticSymmetricSpectrumRequest,
)
from jacobian.math.matrices.quadratic_spectral.operations import (
    inertia,
    singular_spectrum,
    symmetric_spectrum,
)
from jacobian.math.matrices.quadratic_spectral.values import (
    RealQuadraticInertia,
    RealQuadraticSpectrum,
)


def _run[ResultT](operation: Callable[[], ResultT]) -> ResultT:
    try:
        return operation()
    except (PydanticCustomError, ValueError) as exc:
        code = (
            exc.type
            if isinstance(exc, PydanticCustomError)
            else "matrix.domain_invalid"
        )
        message = exc.message() if isinstance(exc, PydanticCustomError) else str(exc)
        raise OperationDomainValidationError(
            location=("matrix",), code=code, message=message
        ) from exc


def compute_symmetric_spectrum(
    request: RealQuadraticSymmetricSpectrumRequest,
) -> RealQuadraticSpectrum:
    return _run(lambda: symmetric_spectrum(request.matrix))


def compute_singular_spectrum(
    request: RealQuadraticSingularSpectrumRequest,
) -> RealQuadraticSpectrum:
    return _run(lambda: singular_spectrum(request.matrix))


def compute_inertia(request: RealQuadraticInertiaRequest) -> RealQuadraticInertia:
    return _run(lambda: inertia(request.matrix))


__all__ = [
    "compute_inertia",
    "compute_singular_spectrum",
    "compute_symmetric_spectrum",
]
