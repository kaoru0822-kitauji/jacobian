from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

import jacobian.plugins.registry as registry_module
from jacobian.contracts.claims import ClaimSpec
from jacobian.contracts.plugins import (
    CapabilityName,
    PluginManifest,
    PluginRegistrySnapshot,
)
from jacobian.contracts.search import SearchBudget, SearchRunRequest
from jacobian.kernel import JacobianKernel
from jacobian.plugin_conformance import (
    PluginConformanceCheck,
    SyntheticPluginConformanceTarget,
    require_plugin_conformance,
    run_plugin_conformance,
)
from jacobian.plugins.registry import PluginRegistryError

pytestmark = [
    pytest.mark.conformance,
]


@pytest.fixture
def plugin_kernel(
    tmp_path: Path,
    kernel_store_template: Path,
) -> JacobianKernel:
    """Kernel rooted at ``tmp_path/state`` so plugin packages can live beside it."""

    state = tmp_path / "state"
    shutil.copytree(kernel_store_template, state)
    return JacobianKernel(state)


def _install_external_plugin(
    kernel: JacobianKernel,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, tuple[str, ...], Path, str]:
    package = tmp_path / "external_plugin"
    package.mkdir()
    marker = tmp_path / "imported"
    (package / "__init__.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('imported')\n",
        encoding="utf-8",
    )
    (package / "entry.py").write_text(
        "\n".join(
            (
                "import time",
                "",
                "def propose(request):",
                "    case = request['state'].get('conformance_case')",
                "    if case == 'declared-failure':",
                "        raise RuntimeError('declared plugin failure')",
                "    if case == 'malformed-output':",
                "        return ['not', 'an', 'object']",
                "    if case == 'timeout':",
                "        time.sleep(10)",
                "    return {",
                "        'response_version': '1',",
                "        'candidates': [{'value': 1}],",
                "        'state': request['state'],",
                "        'complete': True,",
                "    }",
                "",
                "def refine(request):",
                "    return {",
                "        'response_version': '1',",
                "        'state': request['state'],",
                "        'nominations': [],",
                "    }",
                "",
                "def evaluate(request):",
                "    return {",
                "        'conclusion': 'UNKNOWN',",
                "        'arithmetic': 'EXACT_INTEGER',",
                "        'method': 'EXHAUSTIVE_FINITE',",
                "        'coverage': 'EXHAUSTIVE',",
                "        'features': {'value': str(request['candidate']['value'])},",
                "    }",
                "",
                "def transform(_request):",
                "    fake = 'artifact://sha256/' + ('a' * 64)",
                "    return {",
                "        'response_version': '1',",
                "        'proposals': [{",
                "            'claim': {},",
                "            'edit': {",
                "                'kind': 'parameter',",
                "                'description': 'unsupported promotion',",
                "            },",
                "            'parameter_region': {",
                "                'kind': 'SUFFICIENT',",
                "                'conditions': {'n': {'minimum': 1}},",
                "                'evidence': 'VERIFIED_SUFFICIENT',",
                "                'subject_uri': fake,",
                "                'verification_record_uri': fake,",
                "            },",
                "        }],",
                "        'state': {},",
                "        'complete': True,",
                "    }",
                "",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    existing_path = os.environ.get("PYTHONPATH")
    monkeypatch.setenv(
        "PYTHONPATH",
        str(tmp_path) if not existing_path else f"{tmp_path}:{existing_path}",
    )
    monkeypatch.delitem(sys.modules, "external_plugin", raising=False)
    monkeypatch.delitem(sys.modules, "external_plugin.entry", raising=False)

    claim_schema_uri = kernel.schemas.register(
        name="external-plugin.claim",
        version="1",
        schema=ClaimSpec.model_json_schema(),
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
    entrypoints = {
        CapabilityName.PROPOSER: "external_plugin.entry:propose",
        CapabilityName.REFINER: "external_plugin.entry:refine",
        CapabilityName.EVALUATOR: "external_plugin.entry:evaluate",
        CapabilityName.HYPOTHESIS_TRANSFORMER: "external_plugin.entry:transform",
    }
    implementation_uris = {
        capability: kernel.plugins.register_implementation(entrypoint)
        for capability, entrypoint in entrypoints.items()
    }
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
                capability: {
                    "implementation_uri": implementation_uris[capability],
                    "entrypoint": entrypoint,
                    "version": "1",
                }
                for capability, entrypoint in entrypoints.items()
            },
        ).model_dump(mode="json"),
    )
    kernel.plugins.install(manifest.artifact_uri)
    assert not marker.exists()
    claim = kernel.artifacts.put(
        schema_uri=claim_schema_uri,
        semantics_uri=semantics_uri,
        payload={
            "claim_schema_version": "1",
            "domain_id": "external.plugin",
            "domain_version": "1",
            "semantics_uri": semantics_uri,
            "quantifiers": [],
            "predicate": {
                "name": "external_fixture",
                "parameters": {},
            },
            "bounds": {},
            "required_capabilities": [
                "Proposer",
                "Refiner",
                "Evaluator",
            ],
            "correspondence_status": "UNREVIEWED",
        },
    )
    return (
        manifest.artifact_uri,
        tuple(implementation_uris.values()),
        marker,
        claim.artifact_uri,
    )


@pytest.mark.conformance
def test_registry_snapshot_binds_contract_source_runtime_and_platform(
    tmp_path: Path,
    plugin_kernel: JacobianKernel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = plugin_kernel
    plugin_id, implementation_uris, marker, _ = _install_external_plugin(
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
        CapabilityName.HYPOTHESIS_TRANSFORMER
    ].implementation_digest.startswith("sha256:")
    assert snapshot.runtime_identity.python_version
    assert snapshot.runtime_identity.platform_tag
    assert snapshot.build_identity_digest.startswith("sha256:")
    assert stored.manifest.parents == tuple(sorted((plugin_id, *implementation_uris)))
    assert not marker.exists()

    resolved = kernel.plugins.resolve(plugin_id, CapabilityName.EVALUATOR)
    assert resolved.registry_snapshot_uri == snapshot_uri
    assert not marker.exists()
    execution = kernel.plugin_executor.run(
        entrypoint=resolved.descriptor.entrypoint,
        implementation_digest=resolved.implementation_digest,
        request={"candidate": {"value": 1}},
        timeout_seconds=5,
    )
    assert execution.status.value == "COMPLETED"
    assert execution.output is not None
    assert execution.output["conclusion"] == "UNKNOWN"
    assert marker.exists()


def test_registry_snapshot_fails_closed_on_runtime_mismatch(
    tmp_path: Path,
    plugin_kernel: JacobianKernel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = plugin_kernel
    plugin_id, _, _, _ = _install_external_plugin(kernel, tmp_path, monkeypatch)
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


@pytest.mark.subprocess
def test_external_plugin_passes_the_generic_conformance_kit(
    tmp_path: Path,
    plugin_kernel: JacobianKernel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = plugin_kernel
    plugin_id, _, _, claim_uri = _install_external_plugin(
        kernel,
        tmp_path,
        monkeypatch,
    )
    package = tmp_path / "external_plugin"
    entrypoint = package / "entry.py"
    outside = tmp_path / "outside.py"
    outside.write_text("value = 1\n", encoding="utf-8")
    target = SyntheticPluginConformanceTarget(
        kernel=kernel,
        plugin_id=plugin_id,
        search_request=SearchRunRequest(
            idempotency_key="external-conformance-001",
            claim_uri=claim_uri,
            plugin_id=plugin_id,
            budget=SearchBudget(
                candidates_max=4,
                iterations_max=4,
                wall_seconds=30,
                batch_size=1,
                workers=1,
            ),
        ),
        implementation_file=entrypoint,
        symlink_path=package / "escape.py",
        symlink_target=outside,
        import_marker=tmp_path / "imported",
    )

    observations = require_plugin_conformance(target)

    assert all(observation.passed for observation in observations)
    with sqlite3.connect(kernel.store.db_path) as connection:
        first_run_count = connection.execute(
            "SELECT COUNT(*) FROM search_experiments"
        ).fetchone()

    repeated = require_plugin_conformance(target)

    assert all(observation.passed for observation in repeated)
    with sqlite3.connect(kernel.store.db_path) as connection:
        second_run_count = connection.execute(
            "SELECT COUNT(*) FROM search_experiments"
        ).fetchone()
    assert first_run_count == (4,)
    assert second_run_count == (8,)

    assert target.import_marker is not None
    target.import_marker.write_text("unexpected discovery import", encoding="utf-8")
    marker_observations = run_plugin_conformance(target)
    execution_observation = next(
        observation
        for observation in marker_observations
        if observation.check is PluginConformanceCheck.EXECUTION_SUCCESS
    )
    assert not execution_observation.passed
    assert "plugin discovery imported package code" in execution_observation.detail
    assert not target.import_marker.exists()
