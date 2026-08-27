"""Native exact visibility-kernel operation and private claim verification."""

from jacobian.math.geometry.polygon_kernel._kernel import compute_kernel_data
from jacobian.math.geometry.polygon_kernel._models import (
    PolygonKernelRequest,
    PolygonKernelResult,
)


def compute_visibility_kernel(request: PolygonKernelRequest) -> PolygonKernelResult:
    """Reconstruct a simple CCW polygon's closed visibility kernel exactly."""

    data = compute_kernel_data(request.polygon)
    return PolygonKernelResult._from_kernel(request.polygon, data=data)


__all__ = ["compute_visibility_kernel"]
