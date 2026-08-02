"""Episode recording summaries and invocation telemetry."""

from __future__ import annotations

import logging
import time

from jacobian.contracts.capabilities import CapabilityResult

_LOGGER = logging.getLogger(__name__)


def episode_summary(result: CapabilityResult) -> str:
    return (
        f"{result.capability_id} {result.mode.value.lower()} "
        f"{result.execution.status.value.lower()} "
        f"({result.assurance.level.value.lower()})"
    )


def log_invocation(result: CapabilityResult, started: float) -> None:
    elapsed_ms = round((time.monotonic() - started) * 1000)
    diagnostic_codes = (
        ",".join(diagnostic.code for diagnostic in result.diagnostics) or "-"
    )
    _LOGGER.info(
        (
            "capability invocation capability_id=%s version=%s mode=%s "
            "status=%s assurance=%s elapsed_ms=%d diagnostics=%s episode=%s"
        ),
        result.capability_id,
        result.capability_version,
        result.mode.value,
        result.execution.status.value,
        result.assurance.level.value,
        elapsed_ms,
        diagnostic_codes,
        result.episode_uri or "-",
        extra={
            "jacobian_capability_id": result.capability_id,
            "jacobian_capability_version": result.capability_version,
            "jacobian_mode": result.mode.value,
            "jacobian_execution_status": result.execution.status.value,
            "jacobian_assurance_level": result.assurance.level.value,
            "jacobian_elapsed_ms": elapsed_ms,
            "jacobian_diagnostic_codes": tuple(
                diagnostic.code for diagnostic in result.diagnostics
            ),
            "jacobian_episode_uri": result.episode_uri,
        },
    )


__all__ = ["episode_summary", "log_invocation"]
