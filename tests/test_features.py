"""Tests for the feature flag infrastructure."""

from __future__ import annotations

import pytest

from jacobian.features import FeatureFlags


class TestFeatureFlags:
    def test_is_enabled_returns_true_for_enabled_flag(self) -> None:
        FeatureFlags.pluggable_checkers = True
        assert FeatureFlags.is_enabled("pluggable_checkers") is True

    def test_is_enabled_returns_false_for_disabled_flag(self) -> None:
        FeatureFlags.adaptive_shrinking = False
        assert FeatureFlags.is_enabled("adaptive_shrinking") is False

    def test_is_enabled_raises_for_unknown_flag(self) -> None:
        with pytest.raises(KeyError, match="Unknown feature flag"):
            FeatureFlags.is_enabled("nonexistent_flag")

    def test_snapshot_includes_all_boolean_class_vars(self) -> None:
        snapshot = FeatureFlags.snapshot()
        assert "pluggable_checkers" in snapshot
        assert "parallel_search" in snapshot
        assert "adaptive_shrinking" in snapshot
        assert "structured_tracing" in snapshot
        assert "checker_concurrency" in snapshot
        assert "exhaustive_enumeration" in snapshot
        # All values are booleans.
        assert all(isinstance(v, bool) for v in snapshot.values())

    def test_snapshot_reflects_current_state(self) -> None:
        FeatureFlags.parallel_search = True
        FeatureFlags.adaptive_shrinking = False
        snapshot = FeatureFlags.snapshot()
        assert snapshot["parallel_search"] is True
        assert snapshot["adaptive_shrinking"] is False
        # Restore defaults for other tests.
        FeatureFlags.parallel_search = False

    def test_default_flags_have_sensible_values(self) -> None:
        assert FeatureFlags.pluggable_checkers is True
        assert FeatureFlags.parallel_search is False
        assert FeatureFlags.exhaustive_enumeration is False
        assert FeatureFlags.checker_concurrency is False
        assert FeatureFlags.adaptive_shrinking is False
        assert FeatureFlags.structured_tracing is False
