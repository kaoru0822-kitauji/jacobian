"""Domain operation for exact rational-polynomial box enclosure."""

from pydantic_core import PydanticCustomError

from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.polynomials.intervals._kernel import natural_interval_extension
from jacobian.math.polynomials.intervals._models import (
    PolynomialBoxEnclosureRequest,
    PolynomialBoxEnclosureResult,
    _require_enclosure_preflight,
)


def compute_polynomial_box_enclosure(
    request: PolynomialBoxEnclosureRequest,
) -> PolynomialBoxEnclosureResult:
    """Return the deterministic natural interval extension on the complete box."""

    try:
        _require_enclosure_preflight(request.polynomial, request.box)
    except PydanticCustomError as exc:
        raise OperationDomainValidationError(
            location=(), code=exc.type, message=exc.message()
        ) from exc
    except ValueError as exc:
        raise OperationDomainValidationError(
            location=(), code="polynomial.box_admission", message=str(exc)
        ) from exc

    return PolynomialBoxEnclosureResult._from_kernel(
        request,
        enclosure=natural_interval_extension(request.polynomial, request.box),
    )


__all__ = ["compute_polynomial_box_enclosure"]
