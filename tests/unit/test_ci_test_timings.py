from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "manage-test-timings"


def run_script(
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def plan_outputs() -> dict[str, str]:
    result = run_script("emit-plan-outputs")
    assert result.returncode == 0, result.stderr
    return dict(
        line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
    )


def shard_count() -> int:
    return int(plan_outputs()["integration-shard-count"])


def pinned_pytest_split_version() -> str:
    return plan_outputs()["pytest-split-version"]


def test_prepare_falls_back_to_equal_weighting_without_github_context(
    tmp_path: Path,
) -> None:
    output = tmp_path / "durations.json"
    env = os.environ.copy()
    env.pop("GITHUB_REPOSITORY", None)
    env.pop("GH_TOKEN", None)

    result = run_script("prepare", "--output", str(output), env=env)

    assert result.returncode == 0
    assert json.loads(output.read_text(encoding="utf-8")) == {}
    assert "equal weighting" in result.stderr


def test_merge_publishes_versioned_metadata_and_all_shards(tmp_path: Path) -> None:
    count = shard_count()
    inputs: list[str] = []
    for shard in range(1, count + 1):
        path = tmp_path / f"shard-{shard}.json"
        path.write_text(
            json.dumps({f"tests/integration/test_{shard}.py::test_case": shard}),
            encoding="utf-8",
        )
        inputs.extend(["--input", str(path)])
    output = tmp_path / "integration-test-durations.json"

    result = run_script(
        "merge",
        *inputs,
        "--output",
        str(output),
        "--source-sha",
        "a" * 40,
        "--python-version",
        "3.12",
        "--pytest-split-version",
        pinned_pytest_split_version(),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["suite"] == "integration"
    assert payload["shard_count"] == count
    assert len(payload["durations"]) == count


def test_merge_defaults_pytest_split_version_from_pyproject(tmp_path: Path) -> None:
    count = shard_count()
    inputs: list[str] = []
    for shard in range(1, count + 1):
        path = tmp_path / f"shard-{shard}.json"
        path.write_text(
            json.dumps(
                {f"tests/integration/infrastructure/test_shared.py::test_{shard}": 1.0}
            ),
            encoding="utf-8",
        )
        inputs.extend(["--input", str(path)])

    result = run_script(
        "merge",
        *inputs,
        "--output",
        str(tmp_path / "output.json"),
        "--source-sha",
        "a" * 40,
        "--python-version",
        "3.12",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads((tmp_path / "output.json").read_text(encoding="utf-8"))
    assert payload["pytest_split_version"] == pinned_pytest_split_version()


def test_emit_plan_outputs_exposes_ci_config_ssot() -> None:
    outputs = plan_outputs()
    assert outputs["node-version-jscpd"] == "20"
    assert outputs["node-version-npm"] == "24"
    assert outputs["pytest-randomly-shard-seed"] == "0"
    assert outputs["pytest-split-version"]
    assert (
        run_script("node-version", "npm").stdout.strip() == outputs["node-version-npm"]
    )


def test_merge_rejects_duplicate_node_ids(tmp_path: Path) -> None:
    count = shard_count()
    inputs: list[str] = []
    for shard in range(1, count + 1):
        path = tmp_path / f"shard-{shard}.json"
        path.write_text(
            json.dumps(
                {"tests/integration/infrastructure/test_shared.py::test_case": shard}
            ),
            encoding="utf-8",
        )
        inputs.extend(["--input", str(path)])

    result = run_script(
        "merge",
        *inputs,
        "--output",
        str(tmp_path / "output.json"),
        "--source-sha",
        "a" * 40,
        "--python-version",
        "3.12",
        "--pytest-split-version",
        pinned_pytest_split_version(),
    )

    assert result.returncode != 0
    assert "duplicate" in result.stderr.lower() or result.stderr
