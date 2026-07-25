from __future__ import annotations

from typing import Any

import pytest

from jacobian.experiment_router import ExperimentRouter
from jacobian.experiments import ExperimentNotFoundError


class _Backend:
    def __init__(self, experiment_uri: str, result: object) -> None:
        self.experiment_uri = experiment_uri
        self.result = result
        self.calls: list[tuple[str, float | None]] = []

    def contains(self, experiment_uri: str) -> bool:
        return experiment_uri == self.experiment_uri

    def inspect(self, experiment_uri: str) -> Any:
        self.calls.append(("inspect", None))
        return self.result

    def wait(
        self,
        experiment_uri: str,
        *,
        timeout_seconds: float = 30,
    ) -> Any:
        self.calls.append(("wait", timeout_seconds))
        return self.result

    def cancel(self, experiment_uri: str) -> Any:
        self.calls.append(("cancel", None))
        return self.result


def test_router_dispatches_each_operation_to_the_owning_backend() -> None:
    first = _Backend("experiment://" + "a" * 32, object())
    expected = object()
    second = _Backend("experiment://" + "b" * 32, expected)
    router = ExperimentRouter(first, second)

    assert router.inspect(second.experiment_uri) is expected
    assert router.wait(second.experiment_uri, timeout_seconds=7) is expected
    assert router.cancel(second.experiment_uri) is expected
    assert first.calls == []
    assert second.calls == [
        ("inspect", None),
        ("wait", 7),
        ("cancel", None),
    ]


def test_router_rejects_an_unknown_experiment_without_probing_operations() -> None:
    backend = _Backend("experiment://" + "a" * 32, object())
    router = ExperimentRouter(backend)

    with pytest.raises(ExperimentNotFoundError, match="experiment was not found"):
        router.inspect("experiment://" + "f" * 32)

    assert backend.calls == []
