"""Contracts for source bootstrap identity and frozen benchmark baselines."""

from __future__ import annotations

import importlib.util
import json
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load_tool(name: str) -> ModuleType:
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_image_preflight_binds_revision_and_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _load_tool("check_jacobian_image")
    image = "registry.invalid/jacobian@sha256:" + "a" * 64

    def fake_run(command: list[str], **_kwargs: object) -> object:
        assert command == ["docker", "image", "inspect", image]
        inspected = [
            {
                "Config": {
                    "Labels": {
                        checker.REVISION_LABEL: "abc123",
                        checker.VERSION_LABEL: "0.6.0",
                    }
                }
            }
        ]
        return type("Completed", (), {"stdout": json.dumps(inspected)})()

    monkeypatch.setattr(checker.subprocess, "run", fake_run)
    report = checker.inspect_image(
        image,
        identity={
            "schema_version": checker.IDENTITY_SCHEMA,
            "image_digest": "sha256:" + "a" * 64,
            "git_revision": "abc123",
            "package_version": "0.6.0",
        },
        expected_revision="abc123",
        expected_version="0.6.0",
        pull=False,
    )
    assert report["status"] == "ok"
    assert report["checks"] == {
        "identity_digest_matches": True,
        "identity_revision_matches": True,
        "identity_version_matches": True,
        "revision_label_matches": True,
        "version_label_matches": True,
    }


def test_image_preflight_rejects_a_mislabeled_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _load_tool("check_jacobian_image")
    image = "registry.invalid/jacobian@sha256:" + "b" * 64
    inspected = [{"Config": {"Labels": {checker.REVISION_LABEL: "old"}}}]
    completed = type("Completed", (), {"stdout": json.dumps(inspected)})()
    monkeypatch.setattr(checker.subprocess, "run", lambda *_args, **_kwargs: completed)
    report = checker.inspect_image(
        image,
        identity={
            "schema_version": checker.IDENTITY_SCHEMA,
            "image_digest": "sha256:" + "b" * 64,
            "git_revision": "new",
            "package_version": "0.6.0",
        },
        expected_revision="new",
        expected_version="0.6.0",
        pull=False,
    )
    assert report["status"] == "error"
    assert report["checks"]["revision_label_matches"] is False
    assert report["checks"]["version_label_matches"] is False


def test_image_preflight_rejects_forged_matching_labels_without_digest_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _load_tool("check_jacobian_image")
    image = "registry.invalid/jacobian@sha256:" + "c" * 64
    inspected = [
        {
            "Config": {
                "Labels": {
                    checker.REVISION_LABEL: "expected",
                    checker.VERSION_LABEL: "0.6.0",
                }
            }
        }
    ]
    completed = type("Completed", (), {"stdout": json.dumps(inspected)})()
    monkeypatch.setattr(checker.subprocess, "run", lambda *_args, **_kwargs: completed)
    with pytest.raises(ValueError, match="image_digest"):
        checker.inspect_image(
            image,
            identity={
                "schema_version": checker.IDENTITY_SCHEMA,
                "image_digest": "sha256:" + "d" * 64,
                "git_revision": "expected",
                "package_version": "0.6.0",
            },
            expected_revision="expected",
            expected_version="0.6.0",
            pull=False,
        )


def test_version_identity_uses_uv_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _load_tool("check_jacobian_image")
    doctor = _load_tool("source_agent_doctor")
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> object:
        commands.append(command)
        return type("Completed", (), {"stdout": "0.7.0a0\n"})()

    monkeypatch.setattr(checker.subprocess, "run", fake_run)
    assert checker._repository_version(ROOT) == "0.7.0a0"
    assert doctor._repository_version(ROOT) == "0.7.0a0"
    assert commands == [
        ["uv", "version", "--project", str(ROOT), "--short"],
        ["uv", "version", "--project", str(ROOT), "--short"],
    ]


def test_performance_v1_is_one_explicit_historical_baseline() -> None:
    dataset = ROOT / "benchmarks" / "datasets" / "performance-v1"
    with (dataset / "baseline.toml").open("rb") as stream:
        baseline = tomllib.load(stream)
    assert baseline["classification"] == "historical-baseline"
    revision = baseline["repository_revision"]
    uv_version = baseline["uv_version"]
    task_dirs = sorted((dataset / "tasks").glob("*/*/*"))
    assert len(task_dirs) == 4
    for task_dir in task_dirs:
        environment = task_dir / "environment"
        task_input = json.loads((environment / "input.json").read_text())
        dockerfile = (environment / "Dockerfile").read_text()
        assert task_input["repository_revision"] == revision
        assert f"fetch --depth 1 origin {revision}" in dockerfile
        assert f"ghcr.io/astral-sh/uv:{uv_version}-" in dockerfile


def test_active_uv_surfaces_share_the_repository_pin() -> None:
    pinned = (ROOT / ".uv-version").read_text().strip()
    assert f"ghcr.io/astral-sh/uv:{pinned}-" in (ROOT / "Dockerfile").read_text()
    setup_files = [
        ROOT / ".github" / "actions" / "setup-python-tests" / "action.yml",
        ROOT / ".github" / "actions" / "setup-lean" / "action.yml",
        ROOT / ".github" / "workflows" / "ci.yml",
        ROOT / ".github" / "workflows" / "release.yml",
        ROOT / ".github" / "workflows" / "release-please.yml",
    ]
    for path in setup_files:
        text = path.read_text()
        assert text.count("astral-sh/setup-uv@") == text.count(f'version: "{pinned}"')


def test_every_bootstrap_profile_audits_z3_and_networkx() -> None:
    doctor = _load_tool("source_agent_doctor")
    for providers in doctor._PROFILE_PROVIDERS.values():
        assert "z3" in providers
        assert "networkx" in providers


def test_bootstrap_dry_run_and_client_preflight_fail_closed() -> None:
    script = (ROOT / "scripts" / "setup-agent").read_text()
    assert "uv python find --no-python-downloads" in script
    assert "unknown MCP client" in script
    assert '--provider-path "$PATH"' in script
    assert '--project-environment "$UV_PROJECT_ENVIRONMENT"' in script
    assert '--elan-home "$ELAN_HOME"' in script
    assert '--lean-runtime "$JACOBIAN_LEAN_RUNTIME"' in script
    assert 'git -C "$REPO_ROOT" check-ignore -q -- "$STATE_DIR"' in script
