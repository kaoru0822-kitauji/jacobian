from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "manage-test-timings"
CI_CONFIG = ROOT / ".github" / "ci-config.json"


def shard_count() -> int:
    return int(
        json.loads(CI_CONFIG.read_text(encoding="utf-8"))["integration_shard_count"]
    )


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
        "0.11.0",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["suite"] == "integration"
    assert payload["shard_count"] == count
    assert len(payload["durations"]) == count


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
        "0.11.0",
    )

    assert result.returncode != 0
    assert "duplicate timing entry" in result.stderr
