from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from benchmarks.jacobian_math_evals.catalog import load_sources
from benchmarks.jacobian_math_evals.compiler import (
    FAMILIES,
    compile_tasks,
    select_tasks,
    stable_task_name,
    task_specs,
)
from benchmarks.jacobian_math_evals.configs import (
    experiment_fingerprint,
    matched_configs,
)
from benchmarks.jacobian_math_evals.main import parser
from benchmarks.jacobian_math_evals.manual_specs import (
    TEMPLATES,
    manual_family_specs,
)
from benchmarks.jacobian_math_evals.models import Split
from benchmarks.jacobian_math_evals.quality import (
    CoverageGateError,
    coverage_report,
    require_complete_coverage,
)
from benchmarks.jacobian_math_evals.rewards import RewardDimensions


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_catalog_and_public_diagnostics_have_complete_task_coverage() -> None:
    sources = load_sources()
    specs = task_specs()
    assert len(sources) == 176
    assert len(specs) == 194
    assert sum(spec.split == Split.PUBLIC for spec in specs) == 18
    covered = {source_id for spec in specs for source_id in spec.source_ids}
    assert {source.source_id for source in sources} <= covered
    report = coverage_report(sources, specs)
    assert report.complete is False
    assert report.meaningful_source_count == 8
    assert len(report.merely_referenced_source_ids) == 168
    with pytest.raises(CoverageGateError, match="8/176 sources meaningfully covered"):
        require_complete_coverage(report)


def test_resolved_sources_have_immutable_provenance() -> None:
    sources = load_sources()
    ready = [source for source in sources if source.acquisition_ready]
    assert len(ready) == 160
    assert all(source.immutable_revision for source in ready)
    assert all(source.license for source in ready)
    assert all(source.evidence_timestamp for source in ready)
    catalog = json.loads(
        (
            Path(__file__).parents[3]
            / "benchmarks"
            / "jacobian_math_evals"
            / "catalog"
            / "source-lock.json"
        ).read_text()
    )
    github = [
        source
        for source in catalog["sources"]
        if "github.com" in source["canonical_url"]
    ]
    assert len(github) == 102
    assert all("gitcontribute" in source["provider"] for source in github)
    assert all(source["gitcontribute_job_id"] for source in github)
    acquired_ids: set[str] = set()
    catalog_dir = (
        Path(__file__).parents[3] / "benchmarks" / "jacobian_math_evals" / "catalog"
    )
    for report_name in (
        "handler-probes-github.json",
        "handler-probes-github-data.json",
        "handler-probes.json",
        "handler-probes-structured.json",
    ):
        report = json.loads((catalog_dir / report_name).read_text())
        acquired_ids.update(
            record["source_id"]
            for record in report["records"]
            if record["status"] == "supported"
        )
    acquired_ids.add("src-0de4dff1ce92")
    locked = {source["source_id"]: source for source in catalog["sources"]}
    assert len(acquired_ids) == 119
    assert all(
        locked[source_id]["snapshot_sha256"].startswith("sha256:")
        for source_id in acquired_ids
    )


def test_all_task_families_are_represented() -> None:
    families = {spec.family for spec in task_specs()}
    assert families == set(FAMILIES)
    smoke = select_tasks(split=Split.SMOKE)
    assert len(smoke) == len(FAMILIES)
    assert {spec.family for spec in smoke} == set(FAMILIES)


def test_manually_authored_goldens_cover_every_family() -> None:
    from benchmarks.jacobian_math_evals.compiler import _family, _partition

    specs = manual_family_specs(
        load_sources(),
        family_of=_family,
        partition_of=_partition,
    )
    assert set(TEMPLATES) == set(FAMILIES)
    assert {spec.family for spec in specs} == set(FAMILIES)
    assert all(spec.scored and spec.manual for spec in specs)
    by_family: dict[str, list[dict[str, object]]] = {}
    for spec in specs:
        by_family.setdefault(spec.family, []).append(spec.instance)
    for instances in by_family.values():
        payloads = {
            json.dumps(
                {
                    key: value
                    for key, value in instance.items()
                    if key != "coverage_source_ids"
                },
                sort_keys=True,
            )
            for instance in instances
        }
        assert len(payloads) == len(instances)


def test_names_are_registry_safe_stable_and_unique() -> None:
    names = [stable_task_name(spec) for spec in task_specs()]
    assert len(names) == len(set(names))
    assert all(name.startswith("jacobian-evals/") for name in names)
    assert all(name == name.lower() and " " not in name for name in names)


def test_generation_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    compile_tasks(output_dir=first, split=Split.SMOKE)
    compile_tasks(output_dir=second, split=Split.SMOKE)
    assert _tree_digest(first) == _tree_digest(second)


def test_generated_task_uses_harbor_14_and_clean_room_rewardkit(
    tmp_path: Path,
) -> None:
    [task] = compile_tasks(output_dir=tmp_path, split=Split.SMOKE, limit=1)
    toml = (task / "task.toml").read_text()
    assert 'schema_version = "1.4"' in toml
    assert 'version = "1.0.0"' in toml
    assert 'environment_mode = "separate"' in toml
    assert 'network_mode = "no-network"' in toml
    assert 'artifacts = ["/app/submission.json", "/app/evidence"]' in toml
    assert (task / "tests" / "test.sh").read_text().endswith("rewardkit /tests\n")
    assert "harbor-rewardkit==0.1.7" in (task / "tests" / "Dockerfile").read_text()
    assert (task / "solution" / "solve.sh").stat().st_mode & 0o111


def test_required_cli_flags_parse(tmp_path: Path) -> None:
    args = parser().parse_args(
        [
            "--output-dir",
            str(tmp_path),
            "--limit",
            "2",
            "--overwrite",
            "--task-ids",
            "one,two",
            "--source-ids",
            "src-a,src-b",
            "--split",
            "dev",
            "--cache-dir",
            str(tmp_path),
            "--offline",
        ]
    )
    assert args.limit == 2
    assert args.overwrite is True
    assert args.task_ids == frozenset({"one", "two"})
    assert args.source_ids == frozenset({"src-a", "src-b"})
    assert args.split == Split.DEV
    assert args.offline is True


def test_false_certification_and_wrong_answer_force_zero() -> None:
    good = RewardDimensions(1, 1, 1, 1)
    wrong = RewardDimensions(0, 1, 1, 1)
    assert good.aggregate() == pytest.approx(1)
    assert wrong.aggregate() == 0
    assert good.aggregate(false_certification=True) == 0


def test_reward_dimensions_reject_out_of_range_values() -> None:
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        RewardDimensions(1.01, 1, 1, 1).aggregate()


def test_control_treatment_differ_only_in_condition() -> None:
    control, treatment = matched_configs(dataset_path="generated/coverage")
    assert experiment_fingerprint(control) == experiment_fingerprint(treatment)
    assert all("mcp_servers" not in agent for agent in control["agents"])
    assert all(
        agent["mcp_servers"][0]["name"] == "jacobian" for agent in treatment["agents"]
    )


def test_generation_manifest_records_publishability(tmp_path: Path) -> None:
    compile_tasks(output_dir=tmp_path, split=Split.COVERAGE, limit=1)
    manifest = json.loads((tmp_path / "generation-manifest.json").read_text())
    assert manifest["adapter"] == "jacobian-math-evals"
    assert isinstance(manifest["tasks"][0]["admissible_for_publish"], bool)
    assert manifest["coverage"]["complete"] is False
    assert manifest["coverage"]["meaningful_source_count"] == 8


def test_strict_coverage_refuses_placeholder_tasks(tmp_path: Path) -> None:
    with pytest.raises(CoverageGateError, match="placeholder-only"):
        compile_tasks(
            output_dir=tmp_path,
            split=Split.COVERAGE,
            strict_coverage=True,
        )
