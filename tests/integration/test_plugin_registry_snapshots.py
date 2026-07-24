from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

import jacobian.plugins.registry as registry_module
from jacobian.contracts.plugins import (
    CapabilityName,
    PluginManifest,
    PluginRegistrySnapshot,
)
from jacobian.kernel import JacobianKernel
from jacobian.plugins.registry import PluginRegistryError

pytestmark = pytest.mark.conformance


def _install_external_plugin(
    kernel: JacobianKernel,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, str, Path]:
    package = tmp_path / "external_plugin"
    package.mkdir()
    marker = tmp_path / "imported"
    (package / "__init__.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('imported')\n",
        encoding="utf-8",
    )
    (package / "entry.py").write_text(
        "def evaluate(request):\n    return {'seen': request.get('request_version')}\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    existing_path = os.environ.get("PYTHONPATH")
    monkeypatch.setenv(
        "PYTHONPATH",
        str(tmp_path) if not existing_path else f"{tmp_path}:{existing_path}",
    )
    sys.modules.pop("external_plugin", None)
    sys.modules.pop("external_plugin.entry", None)

    claim_schema_uri = kernel.schemas.register(
        name="external-plugin.claim",
        version="1",
        schema={"type": "object"},
    )
    candidate_schema_uri = kernel.schemas.register(
        name="external-plugin.candidate",
        version="1",
        schema={"type": "object"},
    )
    semantics_uri = kernel.store.register_descriptor(
        kind="semantics",
        name="external-plugin.domain",
        version="1",
        definition={"description": "external plugin snapshot fixture"},
    )
    entrypoint = "external_plugin.entry:evaluate"
    implementation_uri = kernel.plugins.register_implementation(entrypoint)
    assert not marker.exists()
    manifest = kernel.artifacts.put(
        schema_uri=kernel.reference_installer.manifest_schema_uri,
        semantics_uri=kernel.reference_installer.manifest_semantics_uri,
        payload=PluginManifest(
            domain_id="external.plugin",
            domain_version="1",
            semantics_uri=semantics_uri,
            claim_schema_uri=claim_schema_uri,
            candidate_schema_uri=candidate_schema_uri,
            capabilities={
                CapabilityName.EVALUATOR: {
                    "implementation_uri": implementation_uri,
                    "entrypoint": entrypoint,
                    "version": "1",
                },
                CapabilityName.TRANSFORMER: {
                    "implementation_uri": implementation_uri,
                    "entrypoint": entrypoint,
                    "version": "1",
                },
            },
        ).model_dump(mode="json"),
    )
    kernel.plugins.install(manifest.artifact_uri)
    assert not marker.exists()
    return manifest.artifact_uri, implementation_uri, marker


@pytest.mark.integration
@pytest.mark.conformance
def test_registry_snapshot_binds_contract_source_runtime_and_platform(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path / "state")
    plugin_id, implementation_uri, marker = _install_external_plugin(
        kernel,
        tmp_path,
        monkeypatch,
    )

    snapshot_uri = kernel.plugins.snapshot_uri(plugin_id)
    snapshot = kernel.plugins.snapshot(plugin_id)
    stored = kernel.store.get(snapshot_uri)

    assert isinstance(snapshot, PluginRegistrySnapshot)
    assert snapshot.plugin_id == plugin_id
    assert (
        snapshot.plugin_manifest_digest
        == kernel.store.get(plugin_id).manifest.object_digest
    )
    assert snapshot.capabilities[
        CapabilityName.EVALUATOR
    ].implementation_digest.startswith("sha256:")
    assert snapshot.capabilities[
        CapabilityName.TRANSFORMER
    ].implementation_digest.startswith("sha256:")
    assert snapshot.runtime_identity.python_version
    assert snapshot.runtime_identity.platform_tag
    assert snapshot.build_identity_digest.startswith("sha256:")
    assert stored.manifest.parents == tuple(sorted((plugin_id, implementation_uri)))
    assert not marker.exists()

    resolved = kernel.plugins.resolve(plugin_id, CapabilityName.EVALUATOR)
    assert resolved.registry_snapshot_uri == snapshot_uri
    assert not marker.exists()
    execution = kernel.plugin_executor.run(
        entrypoint=resolved.descriptor.entrypoint,
        implementation_digest=resolved.implementation_digest,
        request={"request_version": "1"},
        timeout_seconds=5,
    )
    assert execution.status.value == "COMPLETED"
    assert execution.output == {"seen": "1"}
    assert marker.exists()


@pytest.mark.integration
def test_registry_snapshot_fails_closed_on_runtime_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path / "state")
    plugin_id, _, _ = _install_external_plugin(kernel, tmp_path, monkeypatch)
    installed_runtime = kernel.plugins.snapshot(plugin_id).runtime_identity
    incompatible = installed_runtime.model_copy(
        update={"system": installed_runtime.system + "-different"}
    )
    monkeypatch.setattr(registry_module, "_runtime_identity", lambda: incompatible)

    with pytest.raises(
        PluginRegistryError,
        match="incompatible with this runtime",
    ):
        kernel.plugins.resolve(plugin_id, CapabilityName.EVALUATOR)
