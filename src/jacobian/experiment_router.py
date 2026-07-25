"""Dispatch shared experiment operations to the owning service."""

from __future__ import annotations

from typing import Protocol

from jacobian.contracts.discovery import (
    ExperimentCancelResult,
    ExperimentSnapshot,
)
from jacobian.contracts.search import (
    ExperimentControlResult,
    SearchExperimentSnapshot,
)
from jacobian.experiments import ExperimentNotFoundError

ExperimentReadResult = ExperimentSnapshot | SearchExperimentSnapshot
ExperimentCancelResponse = ExperimentCancelResult | ExperimentControlResult


class ExperimentBackend(Protocol):
    """The common lifecycle surface implemented by experiment services."""

    def contains(self, experiment_uri: str) -> bool: ...

    def inspect(self, experiment_uri: str) -> ExperimentReadResult: ...

    def wait(
        self,
        experiment_uri: str,
        *,
        timeout_seconds: float = 30,
    ) -> ExperimentReadResult: ...

    def cancel(self, experiment_uri: str) -> ExperimentCancelResponse: ...


class ExperimentRouter:
    """Resolve an experiment URI once, then delegate without exception probing."""

    def __init__(self, *backends: ExperimentBackend) -> None:
        self._backends = backends

    def inspect(self, experiment_uri: str) -> ExperimentReadResult:
        return self._resolve(experiment_uri).inspect(experiment_uri)

    def wait(
        self,
        experiment_uri: str,
        *,
        timeout_seconds: float = 30,
    ) -> ExperimentReadResult:
        return self._resolve(experiment_uri).wait(
            experiment_uri,
            timeout_seconds=timeout_seconds,
        )

    def cancel(self, experiment_uri: str) -> ExperimentCancelResponse:
        return self._resolve(experiment_uri).cancel(experiment_uri)

    def _resolve(self, experiment_uri: str) -> ExperimentBackend:
        for backend in self._backends:
            if backend.contains(experiment_uri):
                return backend
        raise ExperimentNotFoundError(
            "The experiment was not found. Check the URI returned by search.run or "
            "search.enumerate, or start a new experiment."
        )
