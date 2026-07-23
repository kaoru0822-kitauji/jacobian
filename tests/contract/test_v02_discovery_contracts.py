from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.discovery import (
    EnumerationAccounting,
    ExperimentSnapshot,
    PluginEnumerationPage,
)
from jacobian.contracts.polytope import (
    FiniteGeneratorSet,
    PolytopeSeparateRequest,
)


@pytest.mark.contract
def test_incomplete_enumeration_page_requires_a_progress_cursor() -> None:
    with pytest.raises(ValidationError, match="next_cursor"):
        PluginEnumerationPage(
            candidates=({"rows": 1, "cols": 1, "entries": [["0"]]},),
            complete=False,
            scope={"rows": 1, "cols": 1, "entries": [0, 1]},
        )


@pytest.mark.contract
def test_complete_enumeration_page_rejects_a_cursor() -> None:
    with pytest.raises(ValidationError, match="cannot carry next_cursor"):
        PluginEnumerationPage(
            candidates=(),
            next_cursor={"offset": 1},
            complete=True,
            scope={"rows": 1, "cols": 1, "entries": [0, 1]},
        )


@pytest.mark.contract
def test_polytope_inputs_require_canonical_exact_rationals() -> None:
    with pytest.raises(ValidationError, match="reduced"):
        FiniteGeneratorSet(
            dimension=1,
            generators=({"values": ({"num": "2", "den": "4"},)},),
        )


@pytest.mark.contract
def test_polytope_projection_rejects_duplicate_coordinates() -> None:
    with pytest.raises(ValidationError, match="unique"):
        PolytopeSeparateRequest(
            point_uri="artifact://sha256/" + "1" * 64,
            generator_set_uri="artifact://sha256/" + "2" * 64,
            projection=(0, 0),
        )


@pytest.mark.contract
def test_exhaustive_snapshot_requires_complete_enumerator_report() -> None:
    with pytest.raises(ValidationError, match="complete enumerator"):
        ExperimentSnapshot(
            experiment_uri="experiment://" + "1" * 32,
            state="COMPLETED",
            request={
                "claim_uri": "artifact://sha256/" + "1" * 64,
                "plugin_id": "artifact://sha256/" + "2" * 64,
                "bounds": {},
                "budget": {
                    "candidates_max": 1,
                    "wall_seconds": 1,
                },
            },
            input={"status": "ACCEPTED"},
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            stop_reason="COMPLETE",
            enumerator_reported_complete=False,
            coverage="EXHAUSTIVE",
            accounting=EnumerationAccounting(),
        )


@pytest.mark.contract
def test_terminal_experiment_state_requires_its_matching_stop_reason() -> None:
    with pytest.raises(ValidationError, match="state and stop reason disagree"):
        ExperimentSnapshot(
            experiment_uri="experiment://" + "1" * 32,
            state="CANCELLED",
            request={
                "claim_uri": "artifact://sha256/" + "1" * 64,
                "plugin_id": "artifact://sha256/" + "2" * 64,
                "bounds": {},
                "budget": {
                    "candidates_max": 1,
                    "wall_seconds": 1,
                },
            },
            input={"status": "ACCEPTED"},
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            stop_reason="COMPLETE",
            accounting=EnumerationAccounting(),
        )
