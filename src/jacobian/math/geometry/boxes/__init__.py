"""Exact rational axis-aligned box operations."""

from jacobian.math.geometry.boxes._models import (
    BoxIntersectionLedgerEntry,
    BoxUnionVolumeResult,
)
from jacobian.math.geometry.boxes._operations import compute_box_union_volume
from jacobian.math.geometry.boxes.values import RationalAxisAlignedBox
from jacobian.math.intervals import ClosedRationalInterval

__all__ = [
    "BoxIntersectionLedgerEntry",
    "BoxUnionVolumeResult",
    "ClosedRationalInterval",
    "RationalAxisAlignedBox",
    "compute_box_union_volume",
]
