"""Shared persistence projections for research-episode indexing."""

from __future__ import annotations

from typing import Any


def failure_metadata(result: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """Extract the bounded failure dimensions persisted by the episode index."""

    metadata: set[tuple[str, str]] = set()
    diagnostics = result.get("diagnostics", ())
    if isinstance(diagnostics, (list, tuple)):
        for diagnostic in diagnostics:
            if not isinstance(diagnostic, dict):
                continue
            stage = diagnostic.get("stage")
            classification = diagnostic.get("code")
            if isinstance(stage, str) and isinstance(classification, str):
                metadata.add((stage, classification))
    output = result.get("output")
    if isinstance(output, dict):
        classifications = output.get("failure_classifications", ())
        if isinstance(classifications, (list, tuple)):
            for classification in classifications:
                if isinstance(classification, str):
                    metadata.add(("mathematical_evaluation", classification))
    return tuple(sorted(metadata))


__all__ = ["failure_metadata"]
