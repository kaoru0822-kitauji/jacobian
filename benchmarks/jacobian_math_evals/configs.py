"""Matched Harbor control/treatment configuration generation."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

AGENTS = (
    ("codex", "${CODEX_MODEL}"),
    ("claude-code", "${CLAUDE_MODEL}"),
    ("qwen-code", "${QWEN_MODEL}"),
)


def matched_configs(
    *, dataset_path: str, seed: int = 1729
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return current-Harbor JobConfig dictionaries.

    Randomized condition order is recorded in the adjacent experiment manifest,
    because it is an experiment concern rather than a Harbor JobConfig field.
    """

    del seed
    common: dict[str, Any] = {
        "jobs_dir": "${JACOBIAN_EVAL_JOBS_DIR}",
        "n_attempts": 1,
        "timeout_multiplier": 1.0,
        "orchestrator": {
            "type": "local",
            "n_concurrent_trials": 1,
            "quiet": False,
        },
        "environment": {
            "type": "docker",
            "force_build": True,
            "delete": True,
        },
        "agents": [
            {"name": name, "model_name": model_name} for name, model_name in AGENTS
        ],
        "datasets": [{"path": dataset_path}],
    }
    control = copy.deepcopy(common)
    treatment = copy.deepcopy(common)
    treatment["environment"]["extra_docker_compose"] = [
        str(Path(__file__).parent / "experiment" / "jacobian-treatment.compose.yaml")
    ]
    treatment["extra_instruction_paths"] = [
        str(Path(__file__).parent / "experiment" / "treatment-instruction.md")
    ]
    for agent in treatment["agents"]:
        agent["mcp_servers"] = [
            {
                "name": "jacobian",
                "transport": "streamable-http",
                "url": "http://jacobian-auth-proxy:8080/mcp",
            }
        ]
    return control, treatment


def condition_normalized(config: dict[str, Any]) -> dict[str, Any]:
    """Remove only the deliberate Jacobian condition surface."""

    normalized = copy.deepcopy(config)
    environment = normalized.get("environment")
    if isinstance(environment, dict):
        environment.pop("extra_docker_compose", None)
    normalized.pop("extra_instruction_paths", None)
    agents = normalized.get("agents")
    if isinstance(agents, list):
        for agent in agents:
            if isinstance(agent, dict):
                agent.pop("mcp_servers", None)
    return normalized


def experiment_fingerprint(config: dict[str, Any]) -> str:
    payload = json.dumps(
        condition_normalized(config),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def experiment_manifest(*, seed: int = 1729) -> dict[str, Any]:
    bucket = hashlib.sha256(str(seed).encode()).digest()[0] & 1
    first = "control" if bucket == 0 else "treatment"
    second = "treatment" if first == "control" else "control"
    return {
        "schema_version": 1,
        "seed": seed,
        "condition_order": [first, second],
        "randomization": "sha256-family schedule; paired within task-agent-model-seed",
        "policy": "COMPUTE_VERIFY_NO_RETRIEVAL",
        "required_trial_record": [
            "jacobian_commit",
            "jacobian_image_digest",
            "catalog_digest",
            "policy_digest",
            "checker_identities",
            "state_directory",
            "task_digest",
            "agent",
            "model",
            "budget",
            "seed",
        ],
    }


def write_matched_configs(
    output_dir: Path,
    *,
    dataset_path: str,
    seed: int = 1729,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    control, treatment = matched_configs(dataset_path=dataset_path, seed=seed)
    paths = (
        output_dir / "control.json",
        output_dir / "treatment.json",
        output_dir / "experiment.json",
    )
    for path, value in zip(
        paths,
        (control, treatment, experiment_manifest(seed=seed)),
        strict=True,
    ):
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return paths


def oracle_config(*, dataset_path: str, jobs_dir: str) -> dict[str, Any]:
    """Local, no-model rollout used only to validate task/verifier contracts."""

    control, _ = matched_configs(dataset_path=dataset_path)
    control["jobs_dir"] = jobs_dir
    control["agents"] = [{"name": "oracle"}]
    control["orchestrator"]["n_concurrent_trials"] = 4
    return control


def validate_treatment_environment(env: dict[str, str]) -> None:
    image = env.get("JACOBIAN_IMAGE", "")
    if "@sha256:" not in image or len(image.rsplit("@sha256:", 1)[1]) != 64:
        raise ValueError("JACOBIAN_IMAGE must be digest-pinned")
    token = env.get("JACOBIAN_MCP_TOKEN")
    if not token:
        raise ValueError("JACOBIAN_MCP_TOKEN is required")
    try:
        token_map = json.loads(env.get("JACOBIAN_AUTH_TOKENS_JSON", ""))
    except json.JSONDecodeError as error:
        raise ValueError("JACOBIAN_AUTH_TOKENS_JSON must be JSON") from error
    if not isinstance(token_map, dict) or token not in token_map:
        raise ValueError("proxy token must exist in the Jacobian token map")
    if not isinstance(token_map[token], str) or not token_map[token]:
        raise ValueError("token map tenant ID must be non-empty")
