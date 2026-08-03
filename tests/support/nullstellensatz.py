"""Frozen exact Nullstellensatz evidence shared across semantic test lanes."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jacobian.contracts.nullstellensatz import NullstellensatzChartCertificate

_ROOT = Path(__file__).resolve().parents[2]
_PUBLIC_CERTIFICATE = (
    _ROOT
    / "benchmarks"
    / "datasets"
    / "research-diagnostics-v1"
    / "jcb-postdoc-019"
    / "solution"
    / "nullstellensatz-certificate.json"
)


@lru_cache(maxsize=1)
def load_chart_certificates() -> tuple[NullstellensatzChartCertificate, ...]:
    """Load the checked-in public reproduction without recomputing its proof."""

    payload = json.loads(_PUBLIC_CERTIFICATE.read_text(encoding="utf-8"))
    return tuple(
        NullstellensatzChartCertificate.model_validate(chart)
        for chart in payload["charts"]
    )


__all__ = ["load_chart_certificates"]
