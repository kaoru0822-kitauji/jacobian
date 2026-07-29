from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.plugins import PluginManifest


def test_plugin_manifest_cannot_declare_trusted_checkers() -> None:
    digest = "a" * 64
    manifest = {
        "plugin_schema_version": "1",
        "domain_id": "example.domain",
        "domain_version": "1",
        "semantics_uri": f"artifact://sha256/{digest}",
        "claim_schema_uri": f"artifact://sha256/{'e' * 64}",
        "candidate_schema_uri": f"artifact://sha256/{'b' * 64}",
        "witness_schema_uris": [f"artifact://sha256/{'c' * 64}"],
        "capabilities": {
            "Evaluator": {
                "implementation_uri": f"artifact://sha256/{'d' * 64}",
                "entrypoint": "example.plugin:evaluate",
            }
        },
        "trusted_checkers": ["example.plugin:self_certify"],
    }

    with pytest.raises(ValidationError):
        PluginManifest.model_validate(manifest)
