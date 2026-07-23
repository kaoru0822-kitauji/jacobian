from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jacobian.cli import app


@pytest.mark.integration
def test_cli_init_reports_both_reference_domains(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        ["--state-dir", str(tmp_path), "init"],
    )

    assert result.exit_code == 0
    catalog = json.loads(result.stdout)
    assert set(catalog) == {"graph_paths", "matrices"}
