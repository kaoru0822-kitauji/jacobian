from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jacobian.cli import app
from jacobian.kernel import JacobianKernel

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_project_codex_profile_starts_the_local_stdio_server() -> None:
    config = tomllib.loads(
        (PROJECT_ROOT / ".codex" / "config.toml").read_text(encoding="utf-8")
    )

    profile = config["mcp_servers"]["jacobian_local"]
    assert profile == {
        "command": "uv",
        "args": [
            "run",
            "jacobian-mcp",
            "--tool-profile",
            "capabilities",
        ],
        "cwd": ".",
        "enabled": True,
        "required": True,
        "startup_timeout_sec": 30,
        "tool_timeout_sec": 360,
    }


@pytest.mark.integration
def test_cli_init_reports_reference_domains_and_polytope_formats(
    tmp_path: Path,
) -> None:
    result = CliRunner().invoke(
        app,
        ["--state-dir", str(tmp_path), "init"],
    )

    assert result.exit_code == 0
    catalog = json.loads(result.stdout)
    assert set(catalog) == {
        "erdos_straus",
        "graph_paths",
        "matrices",
        "finite_polytopes",
        "lean4",
    }
    assert catalog["erdos_straus"]["witness_checker_ids"][
        "erdos_straus.decomposition_table"
    ].startswith("checker://sha256/")
    assert catalog["finite_polytopes"]["certificate_checker_id"].startswith(
        "checker://sha256/"
    )
    assert catalog["lean4"]["lean_version"] == "4.31.0"
    assert catalog["lean4"]["profiles"]["MATHLIB"]["mathlib_commit"] == (
        "fabf563a7c95a166b8d7b6efca11c8b4dc9d911f"
    )
    assert catalog["lean4"]["profiles"]["MATHLIB"]["checker_timeout_seconds"] == 75


@pytest.mark.integration
def test_cli_help_exposes_v02_operations() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in (
        "structure-canonicalize",
        "search-enumerate",
        "search-run",
        "experiment-inspect",
        "experiment-cancel",
        "experiment-pause",
        "experiment-resume",
        "conjecture-repair",
        "conjecture-generate",
        "parameter-generalize",
        "transform-apply",
        "transform-verify",
        "polytope-separate",
    ):
        assert command in result.stdout


@pytest.mark.integration
def test_cli_enumeration_completes_before_the_local_process_exits(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    reference = kernel.references["matrices"]
    claim = kernel.artifacts.put(
        schema_uri=reference.claim_schema_uri,
        semantics_uri=reference.semantics_uri,
        payload={
            "claim_schema_version": "1",
            "domain_id": "jacobian.integer-matrices",
            "domain_version": "1",
            "semantics_uri": reference.semantics_uri,
            "quantifiers": [],
            "predicate": {"name": "is_nonsingular", "parameters": {}},
            "bounds": {},
            "required_capabilities": ["CandidateEnumerator", "Evaluator"],
            "correspondence_status": "HUMAN_REVIEWED",
        },
    )
    bounds = tmp_path / "bounds.json"
    bounds.write_text(
        json.dumps({"rows": 1, "cols": 1, "entries": [0]}),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "--state-dir",
            str(tmp_path),
            "search-enumerate",
            claim.artifact_uri,
            reference.plugin_id,
            str(bounds),
            "--candidates-max",
            "1",
            "--wall-seconds",
            "30",
            "--page-size",
            "1",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "COMPLETED"
    assert payload["stop_reason"] == "COMPLETE"
    assert payload["verification"] == "UNVERIFIED"
