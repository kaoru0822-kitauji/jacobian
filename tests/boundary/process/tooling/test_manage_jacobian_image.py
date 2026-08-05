from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[4] / "tools" / "manage_jacobian_image.py"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("manage_jacobian_image", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inspect_payload() -> dict:
    return {
        "Id": "sha256:" + "2" * 64,
        "RepoDigests": ["ghcr.io/morluto/jacobian@sha256:" + "1" * 64],
        "Os": "linux",
        "Architecture": "amd64",
        "Config": {
            "Labels": {
                "org.opencontainers.image.revision": "a" * 40,
                "org.opencontainers.image.version": "0.8.0",
                "io.jacobian.source-dirty": "false",
            }
        },
    }


def test_image_identity_records_reproducibility_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    monkeypatch.setattr(module, "_docker_inspect", lambda _image: _inspect_payload())

    identity = module.image_identity("ghcr.io/morluto/jacobian:sha-" + "a" * 40)

    assert identity == {
        "source_sha": "a" * 40,
        "source_dirty": False,
        "reference": "ghcr.io/morluto/jacobian:sha-" + "a" * 40,
        "digest_reference": "ghcr.io/morluto/jacobian@sha256:" + "1" * 64,
        "image_id": "sha256:" + "2" * 64,
        "platform": "linux/amd64",
        "jacobian_package_version": "0.8.0",
    }


def test_select_builds_local_image_for_dirty_tree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    monkeypatch.setattr(module, "_source_dirty", lambda: True)
    built: list[str] = []
    monkeypatch.setattr(module, "build", lambda image: built.append(image) or image)

    assert module.select("ghcr.io/morluto/jacobian") == "jacobian:local"
    assert built == ["jacobian:local"]


def test_pull_rejects_dirty_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "_source_dirty", lambda: True)

    with pytest.raises(module.ImageError, match="clean worktree"):
        module.pull("ghcr.io/morluto/jacobian")


def test_bind_runtime_preserves_snapshot_and_adds_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    snapshot = tmp_path / "runtime.json"
    snapshot.write_text(json.dumps({"model": "gpt-5.6-luna"}), encoding="utf-8")
    identity = {"source_sha": "a" * 40}
    monkeypatch.setattr(module, "image_identity", lambda _image: identity)

    module.bind_runtime("jacobian:local", snapshot)

    assert json.loads(snapshot.read_text(encoding="utf-8")) == {
        "jacobian_image": identity,
        "model": "gpt-5.6-luna",
    }
