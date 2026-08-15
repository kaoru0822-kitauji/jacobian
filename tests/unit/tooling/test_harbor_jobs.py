from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from benchmarks.tooling.benchmark_contracts import (
    benchmark_contract_inventory,
    collect_contract_failures,
    validate_job_contract,
)
from benchmarks.tooling.harbor_suite import load_registry

ROOT = Path(__file__).parents[3]


JOB = (
    ROOT
    / "benchmarks"
    / "datasets"
    / "mathematical-benchmarks-v1"
    / "jobs"
    / "jacobian-observation.json"
)
CONTROL_JOB = ROOT / "benchmarks" / "config" / "mathematical-benchmarks-v1-control.json"


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_observation_job_uses_harbor_dataset_selection() -> None:
    job = _read_json(JOB)

    assert "tasks" not in job
    assert job["datasets"] == [
        {
            "path": "benchmarks/datasets/mathematical-benchmarks-v1",
            "task_names": ["graph-counterexample"],
        }
    ]
    assert job["agents"] == [
        {
            "name": "codex",
            "kwargs": {"web_search": "disabled"},
        }
    ]


def test_benchmark_inventory_covers_proxy_control_and_observation_jobs() -> None:
    """The execution-config gate must validate proxied job configs, not skip them.

    The inventory is consumed by ``validate_all``, the contract layer beneath
    ``make harbor-contracts``. A missing proxy entry would therefore remove it
    from the repository gate.
    """
    inventory = benchmark_contract_inventory()

    assert tuple(path.name for path in inventory.proxy_jobs) == (
        "mathematical-benchmarks-v1-control-proxy.json",
        "jacobian-observation-proxy.json",
    )


def test_job_contract_rejects_a_malformed_proxy_control_job() -> None:
    """A malformed proxied control job must not pass the execution-config gate."""
    path = benchmark_contract_inventory().proxy_jobs[0]
    malformed = _read_json(path)
    malformed["artifacts"] = ["logs/agent/trajectory.json"]

    failures = validate_job_contract(
        malformed,
        path=path,
        suite=load_registry()[0],
    )

    assert any("control-proxy" in f and "artifacts" in f for f in failures), (
        f"expected a contract failure for the malformed proxy control job, "
        f"got: {failures}"
    )


def test_contract_failure_collection_runs_every_phase_in_order() -> None:
    calls: list[str] = []

    def phase(name: str, *failures: str) -> Callable[[], list[str]]:
        def validate() -> list[str]:
            calls.append(name)
            return list(failures)

        return validate

    failures = collect_contract_failures(
        (
            phase("schemas", "schema failure"),
            phase("proxy jobs"),
            phase("snapshots", "snapshot failure 1", "snapshot failure 2"),
        )
    )

    assert calls == ["schemas", "proxy jobs", "snapshots"]
    assert failures == [
        "schema failure",
        "snapshot failure 1",
        "snapshot failure 2",
    ]


def test_paired_jobs_use_three_attempts_per_condition() -> None:
    treatment = _read_json(JOB)
    control = _read_json(CONTROL_JOB)

    assert treatment["n_attempts"] == 3
    assert control["n_attempts"] == 3


def test_paired_jobs_collect_runtime_evidence_available_in_each_condition() -> None:
    treatment = _read_json(JOB)
    control = _read_json(CONTROL_JOB)

    assert treatment["artifacts"] == [
        "/logs/agent/trajectory.json",
        {"source": "/logs/jacobian/mcp.log", "service": "jacobian"},
    ]
    assert control["artifacts"] == ["/logs/agent/trajectory.json"]


def test_agent_eval_resolves_a_current_image_when_not_explicitly_set(
    tmp_path: Path,
) -> None:
    """The treatment defaults to the clean revision's immutable registry image."""
    runtime_snapshot = tmp_path / "runtime.json"
    runtime_snapshot.write_text("{}", encoding="utf-8")
    trace = tmp_path / "trace.txt"
    selected = "registry.invalid/jacobian@sha256:" + "a" * 64
    fake_uv = tmp_path / "uv"
    fake_uv.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        "  *'tools.manage_jacobian_image select'*)\n"
        '    printf \'%s\\n\' "$*" >> "$TRACE"\n'
        "    printf '%s\\n' \"$SELECTED_IMAGE\"\n"
        "    ;;\n"
        "  *'tools.manage_jacobian_image bind-runtime'*)\n"
        '    printf \'bind image=%s\\n\' "$JACOBIAN_IMAGE" >> "$TRACE"\n'
        "    ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    fake_harbor = tmp_path / "harbor"
    fake_harbor.write_text(
        '#!/bin/sh\nprintf \'harbor image=%s\\n\' "$JACOBIAN_IMAGE" >> "$TRACE"\n',
        encoding="utf-8",
    )
    fake_harbor.chmod(0o755)
    environment = os.environ | {
        "JACOBIAN_IMAGE": "",
        "SELECTED_IMAGE": selected,
        "TRACE": str(trace),
    }

    completed = subprocess.run(
        [
            "make",
            "agent-eval",
            "EVAL_EXECUTE=1",
            "JACOBIAN_MODEL=test-model",
            f"RUNTIME_SNAPSHOT={runtime_snapshot}",
            f"UV_RUN={fake_uv}",
            f"HARBOR_RUNNER={fake_harbor}",
            "JACOBIAN_REGISTRY_IMAGE=registry.invalid/jacobian",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert trace.read_text(encoding="utf-8").splitlines() == [
        "python -m tools.manage_jacobian_image select --registry-image registry.invalid/jacobian",
        f"bind image={selected}",
        f"harbor image={selected}",
    ]


@pytest.mark.parametrize(
    ("proxy", "expected_job"),
    [
        ("0", "jacobian-observation.json"),
        ("1", "jacobian-observation-proxy.json"),
    ],
)
def test_agent_eval_keeps_the_local_mcp_endpoint_independent_of_egress_proxy(
    tmp_path: Path,
    proxy: str,
    expected_job: str,
) -> None:
    """Harbor egress control shares service networking, so MCP stays on loopback."""
    runtime_snapshot = tmp_path / "runtime.json"
    runtime_snapshot.write_text("{}", encoding="utf-8")
    trace = tmp_path / "harbor-args.txt"
    fake_uv = tmp_path / "uv"
    fake_uv.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_uv.chmod(0o755)
    fake_harbor = tmp_path / "harbor"
    fake_harbor.write_text(
        '#!/bin/sh\nprintf \'%s\\n\' "$@" > "$TRACE"\n',
        encoding="utf-8",
    )
    fake_harbor.chmod(0o755)

    completed = subprocess.run(
        [
            "make",
            "agent-eval",
            "EVAL_EXECUTE=1",
            "JACOBIAN_MODEL=test-model",
            f"RUNTIME_SNAPSHOT={runtime_snapshot}",
            "JACOBIAN_IMAGE=jacobian:test",
            f"JACOBIAN_EVAL_PROXY={proxy}",
            "JACOBIAN_EVAL_HTTP_PROXY=http://proxy.invalid:7890",
            f"UV_RUN={fake_uv}",
            f"HARBOR_RUNNER={fake_harbor}",
        ],
        cwd=ROOT,
        env=os.environ | {"TRACE": str(trace)},
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    arguments = trace.read_text(encoding="utf-8").splitlines()
    assert arguments[arguments.index("-c") + 1].endswith(expected_job)
    mcp_index = arguments.index("--mcp-config")
    assert arguments[mcp_index + 1] == "benchmarks/config/jacobian-loopback.mcp.json"
