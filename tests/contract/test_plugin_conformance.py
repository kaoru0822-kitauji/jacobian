from __future__ import annotations

from jacobian.plugin_conformance import (
    PluginConformanceCheck,
    PluginConformanceError,
    PluginConformanceObservation,
)


def test_plugin_conformance_error_reports_every_failure() -> None:
    observations = tuple(
        PluginConformanceObservation(
            check=check,
            passed=check
            not in {
                PluginConformanceCheck.DECLARED_FAILURE,
                PluginConformanceCheck.SYMLINK_ATTACK,
            },
            detail="fixture failure",
        )
        for check in PluginConformanceCheck
    )

    error = PluginConformanceError(observations)

    assert "declared-failure" in str(error)
    assert "symlink-attack" in str(error)
    assert len(error.observations) == len(PluginConformanceCheck)
