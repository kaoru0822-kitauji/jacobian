from __future__ import annotations

import pytest

from jacobian.worker_environment import worker_environment


def test_worker_environment_does_not_forward_parent_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JACOBIAN_TEST_SECRET", "do-not-forward")
    monkeypatch.setenv("HTTPS_PROXY", "http://secret.invalid")

    environment = worker_environment()

    assert "JACOBIAN_TEST_SECRET" not in environment
    assert "HTTPS_PROXY" not in environment
    assert environment["PYTHONHASHSEED"] == "0"
    assert environment["TZ"] == "UTC"
