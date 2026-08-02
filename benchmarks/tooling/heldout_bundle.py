"""Validate, fetch, and render private held-out Harbor evaluation bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import tarfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from benchmarks.tooling.harbor_suite import BENCHMARKS, HarborSuiteError, task_digest


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HarborSuiteError(f"invalid JSON {path}: {exc}") from exc


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(path: Path) -> dict[str, Any]:
    manifest = _read_json(path)
    schema = _read_json(BENCHMARKS / "schemas" / "held-out-manifest.schema.json")
    errors = sorted(
        Draft202012Validator(schema).iter_errors(manifest),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        messages = [
            f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors
        ]
        raise HarborSuiteError("held-out manifest is invalid:\n" + "\n".join(messages))
    assert isinstance(manifest, dict)
    task_ids = [item["id"] for item in manifest["tasks"]]
    if len(set(task_ids)) != len(task_ids):
        raise HarborSuiteError("held-out task ids must be unique")
    task_set = set(task_ids)
    families = {item["family"] for item in manifest["tasks"]}
    if len(families) < manifest["dataset"]["minimum_independent_families"]:
        raise HarborSuiteError("held-out bundle has too few independent families")
    for stage, config in manifest["experiment"]["stages"].items():
        unknown = sorted(set(config["task_ids"]) - task_set)
        if unknown:
            raise HarborSuiteError(f"{stage} references unknown task ids: {unknown}")
    if len(manifest["experiment"]["stages"]["pilot"]["task_ids"]) != 3:
        raise HarborSuiteError("pilot must freeze exactly three tasks")
    decision = manifest["experiment"]["stages"]["decision"]
    if len(decision["task_ids"]) < 5 or decision["repetitions"] < 5:
        raise HarborSuiteError(
            "decision stage requires at least five tasks and repetitions"
        )
    conditions = {item["id"]: item["role"] for item in manifest["conditions"]}
    if conditions != {"C1": "PRIMARY_CONTROL", "C2": "PRIMARY_TREATMENT"}:
        raise HarborSuiteError(
            "held-out conditions must be the frozen C1/C2 primary pair"
        )
    return manifest


def _safe_extract(archive: Path, output: Path) -> None:
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            target = (output / member.name).resolve()
            try:
                target.relative_to(output.resolve())
            except ValueError as exc:
                raise HarborSuiteError(
                    f"held-out archive path escapes output: {member.name}"
                ) from exc
            if member.issym() or member.islnk() or member.isdev():
                raise HarborSuiteError(
                    f"held-out archive contains a forbidden entry: {member.name}"
                )
        tar.extractall(output, members=members, filter="data")


def verify_bundle(manifest: dict[str, Any], root: Path) -> None:
    dataset_manifest = root / manifest["dataset"]["path"] / "dataset.toml"
    if _digest(dataset_manifest) != manifest["dataset"]["manifest_digest"]:
        raise HarborSuiteError("held-out dataset manifest digest mismatch")
    for task in manifest["tasks"]:
        task_root = root / "dataset" / task["id"]
        actual = "sha256:" + task_digest(task_root).removeprefix("sha256:")
        if actual != task["digest"]:
            raise HarborSuiteError(f"held-out task digest mismatch: {task['id']}")
        for path_key, digest_key in (
            ("verifier_path", "verifier_digest"),
            ("oracle_path", "oracle_digest"),
        ):
            declared = root / task[path_key]
            try:
                declared.resolve().relative_to(root.resolve())
            except ValueError as exc:
                raise HarborSuiteError(
                    f"held-out path escapes bundle: {task[path_key]}"
                ) from exc
            if _digest(declared) != task[digest_key]:
                raise HarborSuiteError(
                    f"held-out {path_key} digest mismatch: {task['id']}"
                )


def fetch_bundle(manifest_uri: str, output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=False)
    manifest_path = output / "manifest.json"
    subprocess.run(["aws", "s3", "cp", manifest_uri, str(manifest_path)], check=True)
    manifest = validate_manifest(manifest_path)
    archive = output / "bundle.tar.gz"
    subprocess.run(
        ["aws", "s3", "cp", manifest["archive"]["uri"], str(archive)], check=True
    )
    if _digest(archive) != manifest["archive"]["sha256"]:
        raise HarborSuiteError("held-out archive digest mismatch")
    extracted = output / "bundle"
    extracted.mkdir()
    _safe_extract(archive, extracted)
    verify_bundle(manifest, extracted)
    return extracted


def _compose(image: str) -> dict[str, Any]:
    return {
        "services": {
            "jacobian": {
                "image": image,
                "command": [
                    "--transport",
                    "streamable-http",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8000",
                    "--allow-anonymous",
                    "--stateless-http",
                    "--state-dir",
                    "/state",
                ],
                "volumes": ["jacobian-state:/state"],
            }
        },
        "volumes": {"jacobian-state": {}},
    }


def render_plan(
    manifest_path: Path,
    bundle_root: Path,
    output: Path,
    stage: str,
    *,
    max_tokens: int,
    max_cost_usd: float,
) -> Path:
    manifest = validate_manifest(manifest_path)
    verify_bundle(manifest, bundle_root)
    experiment = manifest["experiment"]
    if max_tokens != experiment["max_tokens"] or not math_isclose(
        max_cost_usd, experiment["max_cost_usd"]
    ):
        raise HarborSuiteError("runtime budget must exactly match the frozen manifest")
    stage_config = experiment["stages"][stage]
    output.mkdir(parents=True, exist_ok=False)
    conditions = {item["id"]: item for item in manifest["conditions"]}
    order = ["C1", "C2"]
    random.Random(experiment["randomization_seed"]).shuffle(order)
    runs: list[dict[str, Any]] = []
    for condition_id in order:
        condition = conditions[condition_id]
        compose_path = output / f"{condition_id.lower()}.compose.json"
        compose_path.write_text(
            json.dumps(_compose(condition["image"]), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        job_path = output / f"{condition_id.lower()}.job.json"
        job = {
            "jobs_dir": str(output / "results" / condition_id.lower()),
            "n_attempts": stage_config["repetitions"],
            "timeout_multiplier": 1,
            "orchestrator": {
                "type": "local",
                "n_concurrent_trials": 1,
                "quiet": False,
            },
            "environment": {
                "type": "docker",
                "force_build": True,
                "delete": True,
                "extra_docker_compose": [
                    str(BENCHMARKS / "config" / "agent-eval-proxy.compose.yaml"),
                    str(compose_path),
                ],
            },
            "agents": [{"name": "codex"}],
            "datasets": [
                {
                    "path": str(bundle_root / "dataset"),
                    "task_names": stage_config["task_ids"],
                }
            ],
        }
        job_path.write_text(
            json.dumps(job, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        snapshot_path = output / f"{condition_id.lower()}.runtime.json"
        snapshot_path.write_text(
            json.dumps(
                {
                    "bundle_id": manifest["bundle_id"],
                    "bundle_version": manifest["bundle_version"],
                    "bundle_manifest_digest": _digest(manifest_path),
                    "dataset_manifest_digest": manifest["dataset"]["manifest_digest"],
                    "condition": condition,
                    "model": experiment["model"],
                    "prompt_digest": experiment["prompt_digest"],
                    "reasoning_effort": experiment["reasoning_effort"],
                    "randomization_seed": experiment["randomization_seed"],
                    "stage": stage,
                    "max_tokens": max_tokens,
                    "max_cost_usd": max_cost_usd,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        runs.append(
            {
                "condition": condition_id,
                "job": str(job_path),
                "runtime_snapshot": str(snapshot_path),
                "jobs_dir": job["jobs_dir"],
            }
        )
    run_plan = output / "run-plan.json"
    run_plan.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "stage": stage,
                "model": experiment["model"],
                "reasoning_effort": experiment["reasoning_effort"],
                "max_tokens": max_tokens,
                "max_cost_usd": max_cost_usd,
                "runs": runs,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return run_plan


def math_isclose(left: float, right: float) -> bool:
    return abs(float(left) - float(right)) <= 1e-9


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--manifest", type=Path, required=True)
    fetch_parser = subparsers.add_parser("fetch")
    fetch_parser.add_argument("--manifest-uri", required=True)
    fetch_parser.add_argument("--output", type=Path, required=True)
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--manifest", type=Path, required=True)
    render_parser.add_argument("--bundle-root", type=Path, required=True)
    render_parser.add_argument("--output", type=Path, required=True)
    render_parser.add_argument("--stage", choices=("pilot", "decision"), required=True)
    render_parser.add_argument("--max-tokens", type=int, required=True)
    render_parser.add_argument("--max-cost-usd", type=float, required=True)
    args = parser.parse_args()
    if args.command == "validate":
        validate_manifest(args.manifest)
        print(args.manifest)
    elif args.command == "fetch":
        print(fetch_bundle(args.manifest_uri, args.output))
    else:
        print(
            render_plan(
                args.manifest,
                args.bundle_root,
                args.output,
                args.stage,
                max_tokens=args.max_tokens,
                max_cost_usd=args.max_cost_usd,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["fetch_bundle", "render_plan", "validate_manifest", "verify_bundle"]
