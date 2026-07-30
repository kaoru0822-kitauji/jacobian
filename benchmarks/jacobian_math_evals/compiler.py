"""Compile the source catalog and public diagnostics into Harbor 1.4 tasks."""

from __future__ import annotations

import hashlib
import itertools
import json
import shutil
import urllib.parse
from collections.abc import Iterable, Iterator
from pathlib import Path

from .catalog import PACKAGE_ROOT, load_sources
from .handlers.registry import (
    handled_source_ids,
    iter_materialized_handler_specs,
    materialize_handler_specs,
)
from .manual_specs import manual_family_specs
from .models import (
    OracleKind,
    SourceRecord,
    Split,
    TaskReadiness,
    TaskSpec,
)
from .partitions import source_family_split
from .quality import coverage_report, require_complete_coverage, scan_agent_bundle

RESEARCH_SUITES = (
    PACKAGE_ROOT.parent / "research_challenges" / "public_postdoc_v1.json",
    PACKAGE_ROOT.parent / "research_challenges" / "public_postdoc_frontier_v1.json",
)
FAMILIES = (
    "exact-answer",
    "counterexample",
    "formal-proof",
    "proof-repair",
    "premise-retrieval",
    "statement-alignment",
    "research-artifact",
    "formal-library",
    "tool-application",
)
AGENT_IMAGE = (
    "python:3.12-slim@"
    "sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de"
)
VERIFIER_IMAGE = (
    "ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@"
    "sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e"
)


def _digest(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:length]


def _normalized_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    return urllib.parse.urlunsplit(
        (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", "")
    )


def _partition(source: SourceRecord) -> Split:
    return source_family_split(source)


def _family(source: SourceRecord) -> str:
    text = " ".join(
        (
            source.source_type,
            source.claim_type,
            source.artifacts,
            source.usefulness,
        )
    ).lower()
    if source.kind == "formal_library":
        return "formal-library"
    if "repair" in text or "compiler feedback" in text:
        return "proof-repair"
    if "premise" in text or "retriev" in text:
        return "premise-retrieval"
    if "informal" in text or "align" in text or "misformal" in text:
        return "statement-alignment"
    if "counterexample" in text or "witness" in text or "disprov" in text:
        return "counterexample"
    if "proof" in text or "lean" in text or "coq" in text or "isabelle" in text:
        return "formal-proof"
    if source.kind == "repository" and (
        "tool" in text or "platform" in text or "environment" in text
    ):
        return "tool-application"
    if source.kind == "dataset":
        return "exact-answer"
    return "research-artifact"


def _source_task(source: SourceRecord) -> TaskSpec:
    family = _family(source)
    instance = {
        "source_id": source.source_id,
        "canonical_url": source.canonical_url,
        "kind": source.kind,
        "domain": source.domain,
        "claim_type": source.claim_type,
        "verification_level": source.verification_level,
        "artifacts": source.artifacts,
        "conjecture_name": source.conjecture_name,
        "upstream_status": source.upstream_status,
        "access_state": source.access_state.value,
        "immutable_revision": source.immutable_revision,
        "license": source.license,
        "snapshot_sha256": source.snapshot_sha256,
    }
    expected = {
        "source_ids": [source.source_id],
        "allowed_conclusions": [
            "SUPPORTED",
            "REFUTED",
            "INCONCLUSIVE",
            "UNAVAILABLE",
        ],
        "maximum_assurance": (
            "CHECKED"
            if source.acquisition_ready and source.snapshot_sha256
            else "UNVERIFIED"
        ),
        "required_scope_terms": [source.source_id, source.kind],
        "requires_evidence": True,
    }
    instruction = (
        f"Evaluate the frozen {source.kind} instance in `input/source.json` for "
        f"the {family} outcome described there. Produce `submission.json` using "
        "the supplied schema. Reproduce or check the mathematical claim with the "
        "source-specific checker when the frozen input supports it; otherwise "
        "return INCONCLUSIVE or UNAVAILABLE and identify the open obligation. "
        "Do not infer a mathematical conclusion from a timeout, missing witness, "
        "incomplete search, evaluator score, or unavailable dependency. Evidence "
        "paths must be relative and their SHA-256 digests must match the files."
    )
    limitations: list[str] = []
    if not source.acquisition_ready:
        limitations.append("remote source has not been immutably acquired")
    if source.access_state.value in {"gated", "internal-only"}:
        limitations.append("source cannot be redistributed in a public task bundle")
    return TaskSpec(
        task_id=f"source-{source.source_id.removeprefix('src-')}",
        family=family,
        source_ids=(source.source_id,),
        split=_partition(source),
        instruction=instruction,
        keywords=("mathematics", family, source.kind, source.domain),
        scored=True,
        instance=instance,
        expected=expected,
        admissible_for_publish=source.acquisition_ready
        and source.access_state.value == "public",
        readiness=(
            TaskReadiness.UNAVAILABLE
            if source.access_state.value in {"unavailable", "archived"}
            else TaskReadiness.MANUAL_REQUIRED
        ),
        oracle_kind=OracleKind.NONE,
        limitations=tuple(limitations),
    )


def _public_tasks() -> Iterator[TaskSpec]:
    catalog_urls: dict[str, str] = {}
    for source in load_sources():
        for url in (
            source.url,
            source.canonical_url,
            *source.duplicate_urls,
            *source.redirect_from,
        ):
            catalog_urls[_normalized_url(url)] = source.source_id
    for suite_path in RESEARCH_SUITES:
        suite = json.loads(suite_path.read_text(encoding="utf-8"))
        for case in suite["cases"]:
            source_ids = tuple(
                sorted(
                    {
                        catalog_urls.get(
                            _normalized_url(source["url"]),
                            f"research-{_digest(source['url'])}",
                        )
                        for source in case["sources"]
                    }
                )
            )
            task_id = case["challenge_id"]
            yield TaskSpec(
                task_id=task_id,
                family="research-artifact",
                source_ids=source_ids,
                split=Split.PUBLIC,
                instruction=case["prompt"]
                + "\n\nWrite the standard submission.json contract. This is an "
                "answer-visible public diagnostic and is not a scored held-out case.",
                keywords=(
                    "mathematics",
                    "public-diagnostic",
                    "research-artifact",
                    *case["domains"],
                ),
                scored=False,
                instance={
                    "challenge_id": task_id,
                    "title": case["title"],
                    "problem_statement": case["problem_statement"],
                    "success_criteria": case["success_criteria"],
                    "fail_closed_conditions": case["fail_closed_conditions"],
                    "contamination": case["contamination"],
                    "sources": case["sources"],
                },
                expected={
                    "answer_visible": True,
                    "oracle": case["oracle"],
                    "allowed_conclusions": [
                        case["oracle"]["expected_conclusion"]
                    ],
                    "maximum_assurance": "UNVERIFIED",
                },
                admissible_for_publish=True,
                readiness=TaskReadiness.PUBLIC_DIAGNOSTIC,
                oracle_kind=OracleKind.PUBLIC_ANSWER,
                manual=True,
                limitations=("answer-visible diagnostic; exclude from scored metrics",),
            )


def _public_catalog_source_ids() -> frozenset[str]:
    catalog_ids = {source.source_id for source in load_sources()}
    return frozenset(
        source_id
        for spec in _public_tasks()
        for source_id in spec.source_ids
        if source_id in catalog_ids
    )


def task_specs(
    *,
    cache_dir: Path | None = None,
    offline: bool = False,
    full: bool = False,
    selected_source_ids: frozenset[str] = frozenset(),
) -> tuple[TaskSpec, ...]:
    sources = load_sources()
    handled = handled_source_ids() if cache_dir is not None else frozenset()
    public_catalog_ids = _public_catalog_source_ids()
    specs = tuple(
        _source_task(source)
        for source in sources
        if source.source_id not in handled
        and (cache_dir is None or source.source_id not in public_catalog_ids)
    )
    if cache_dir is not None:
        unhandled = tuple(
            source
            for source in sources
            if source.source_id not in handled
            and source.source_id not in public_catalog_ids
        )
        specs = manual_family_specs(
            unhandled,
            family_of=_family,
            partition_of=_partition,
        )
        handler_specs = materialize_handler_specs(
            cache_dir=cache_dir,
            offline=offline,
            full=full,
            selected_source_ids=selected_source_ids,
        )
        specs += handler_specs
        if selected_source_ids:
            covered_by_handlers = {
                source_id for spec in handler_specs for source_id in spec.source_ids
            }
            specs += tuple(
                _source_task(source)
                for source in sources
                if source.source_id in handled
                and source.source_id not in covered_by_handlers
                and source.source_id not in public_catalog_ids
            )
    specs += tuple(_public_tasks())
    ids = [spec.task_id for spec in specs]
    if len(ids) != len(set(ids)):
        raise ValueError("task IDs are not unique")
    covered = {source_id for spec in specs for source_id in spec.source_ids}
    missing = {source.source_id for source in sources} - covered
    if missing:
        raise ValueError(f"catalog sources lack TaskSpecs: {sorted(missing)}")
    return specs


def iter_full_task_specs(
    *,
    cache_dir: Path,
    offline: bool,
    source_ids: frozenset[str] = frozenset(),
) -> Iterator[TaskSpec]:
    sources = load_sources()
    handled = handled_source_ids()
    public_catalog_ids = _public_catalog_source_ids()
    unhandled = tuple(
        source
        for source in sources
        if source.source_id not in handled
        and source.source_id not in public_catalog_ids
    )
    manual_specs = manual_family_specs(
        unhandled,
        family_of=_family,
        partition_of=_partition,
    )
    yield from (
        spec
        for spec in manual_specs
        if not source_ids or source_ids.intersection(spec.source_ids)
    )
    yield from iter_materialized_handler_specs(
        cache_dir=cache_dir,
        offline=offline,
        full=True,
        selected_source_ids=source_ids,
    )
    yield from (
        spec
        for spec in _public_tasks()
        if not source_ids or source_ids.intersection(spec.source_ids)
    )


def select_tasks(
    *,
    split: Split,
    task_ids: frozenset[str] = frozenset(),
    source_ids: frozenset[str] = frozenset(),
    cache_dir: Path | None = None,
    offline: bool = False,
) -> tuple[TaskSpec, ...]:
    if split == Split.PUBLIC:
        selected = list(_public_tasks())
        if task_ids:
            selected = [spec for spec in selected if spec.task_id in task_ids]
        if source_ids:
            selected = [
                spec for spec in selected if source_ids.intersection(spec.source_ids)
            ]
        return tuple(sorted(selected, key=lambda spec: spec.task_id))
    specs = task_specs(
        cache_dir=cache_dir,
        offline=offline,
        full=split == Split.FULL,
        selected_source_ids=source_ids,
    )
    if split == Split.COVERAGE:
        selected = [spec for spec in specs if spec.split != Split.PUBLIC]
    elif split == Split.FULL:
        selected = list(specs)
    elif split == Split.SMOKE:
        selected = []
        seen: set[str] = set()
        for spec in specs:
            if spec.family not in seen:
                selected.append(spec)
                seen.add(spec.family)
    else:
        selected = [spec for spec in specs if spec.split == split]
    if task_ids:
        selected = [spec for spec in selected if spec.task_id in task_ids]
    if source_ids:
        selected = [
            spec for spec in selected if source_ids.intersection(spec.source_ids)
        ]
    return tuple(sorted(selected, key=lambda spec: spec.task_id))


def stable_task_name(spec: TaskSpec) -> str:
    source_digest = _digest("|".join(spec.source_ids))
    instance_payload = json.dumps(spec.instance, sort_keys=True, separators=(",", ":"))
    return f"jacobian-evals/{spec.family}-{source_digest}-{_digest(instance_payload)}"


def _toml_array(values: Iterable[str]) -> str:
    return "[" + ", ".join(json.dumps(value) for value in values) + "]"


def _task_toml(spec: TaskSpec) -> str:
    return f"""schema_version = "1.4"

artifacts = ["/app/submission.json", "/app/evidence"]

[task]
name = {json.dumps(stable_task_name(spec))}
version = "1.0.0"
description = "Independently score a frozen mathematical evaluation instance."
keywords = {_toml_array(spec.keywords)}

[metadata]
author_name = "Jacobian contributors"
author_email = "maintainers@jacobian.invalid"
difficulty = "research"
category = "mathematics"
tags = {_toml_array(spec.keywords)}

[agent]
timeout_sec = 1800.0

[verifier]
timeout_sec = 300.0
environment_mode = "separate"

[environment]
network_mode = "no-network"
build_timeout_sec = 600.0
cpus = 2
memory_mb = 4096
storage_mb = 10240

[verifier.environment]
network_mode = "no-network"
build_timeout_sec = 600.0
cpus = 1
memory_mb = 2048
storage_mb = 4096
"""


def _verifier_source() -> str:
    return '''"""Clean-room Reward Kit criteria for one generated task."""
import sys
from pathlib import Path
from rewardkit import criterion
sys.path.insert(0, str(Path(__file__).parent))
from verifier_runtime import score_submission

def _scores(workspace: Path):
    import json
    expected = json.loads(Path("/tests/expected.json").read_text())
    result = score_submission(workspace, expected)
    return (
        result.correctness,
        result.evidence_validity,
        result.scope_accuracy,
        result.assurance_calibration,
        result.false_certification,
    )

@criterion(shared=True)
def correctness(workspace: Path) -> float:
    return _scores(workspace)[0]

@criterion(shared=True)
def evidence_validity(workspace: Path) -> float:
    return _scores(workspace)[1]

@criterion(shared=True)
def scope_accuracy(workspace: Path) -> float:
    return _scores(workspace)[2]

@criterion(shared=True)
def assurance_calibration(workspace: Path) -> float:
    return _scores(workspace)[3]

@criterion(shared=True)
def aggregate_reward(workspace: Path) -> float:
    correctness, evidence, scope, assurance, false_certification = _scores(workspace)
    if correctness == 0 or false_certification:
        return 0.0
    return .7 * correctness + .1 * evidence + .1 * scope + .1 * assurance
'''


def _dimension_source(index: int) -> str:
    names = (
        "correctness",
        "evidence_validity",
        "scope_accuracy",
        "assurance_calibration",
    )
    return f"""from rewardkit import criteria
criteria.{names[index]}()
"""


def _write_task(root: Path, spec: TaskSpec) -> None:
    (root / "environment").mkdir(parents=True)
    (root / "solution").mkdir()
    tests = root / "tests"
    tests.mkdir()
    for dimension in (
        "correctness",
        "evidence_validity",
        "scope_accuracy",
        "assurance_calibration",
        "reward",
    ):
        (tests / dimension).mkdir()
    (root / "task.toml").write_text(_task_toml(spec), encoding="utf-8")
    (root / "instruction.md").write_text(spec.instruction + "\n", encoding="utf-8")
    source_json = json.dumps(spec.instance, indent=2, sort_keys=True) + "\n"
    submission_schema = (
        PACKAGE_ROOT / "schemas" / "submission.schema.json"
    ).read_text()
    (root / "source.json").write_text(source_json, encoding="utf-8")
    (root / "submission.schema.json").write_text(submission_schema, encoding="utf-8")
    (root / "environment" / "source.json").write_text(source_json, encoding="utf-8")
    (root / "environment" / "submission.schema.json").write_text(
        submission_schema, encoding="utf-8"
    )
    (root / "environment" / "Dockerfile").write_text(
        f"FROM {AGENT_IMAGE}\nWORKDIR /app\n"
        "COPY source.json submission.schema.json /app/input/\n"
        "ENV PYTHONDONTWRITEBYTECODE=1\n",
        encoding="utf-8",
    )
    evidence_text = (
        f"Oracle contract witness for {spec.task_id}; this does not independently "
        "establish the upstream mathematical claim.\n"
    )
    evidence_digest = hashlib.sha256(evidence_text.encode()).hexdigest()
    required_scope = spec.expected.get("required_scope_terms", [spec.task_id])
    oracle_submission = {
        "task_id": spec.task_id,
        "source_ids": list(spec.source_ids),
        "claimed_assurance": spec.expected["maximum_assurance"],
        "evidence": [
            {
                "path": "evidence/oracle-contract.txt",
                "sha256": f"sha256:{evidence_digest}",
            }
        ],
        "scope": " ".join(required_scope)
        + "; contract-only Oracle baseline with no stronger mathematical conclusion",
        "completeness": "UNKNOWN",
        "limitations": list(spec.limitations),
    }
    if "expected_answer" in spec.expected:
        oracle_submission["answer"] = spec.expected["expected_answer"]
    else:
        allowed = spec.expected.get(
            "allowed_conclusions",
            ["SUPPORTED", "REFUTED", "INCONCLUSIVE", "UNAVAILABLE"],
        )
        oracle_submission["conclusion"] = (
            "INCONCLUSIVE" if "INCONCLUSIVE" in allowed else allowed[0]
        )
    (root / "solution" / "submission.json").write_text(
        json.dumps(oracle_submission, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (root / "solution" / "oracle-contract.txt").write_text(
        evidence_text, encoding="utf-8"
    )
    (root / "solution" / "solve.sh").write_text(
        "#!/bin/sh\nset -eu\nmkdir -p /app/evidence\n"
        "cp /solution/submission.json /app/submission.json\n"
        "cp /solution/oracle-contract.txt /app/evidence/oracle-contract.txt\n",
        encoding="utf-8",
    )
    expected = dict(spec.expected)
    expected["task_id"] = spec.task_id
    expected["source_ids"] = list(spec.source_ids)
    if not spec.scored and "allowed_conclusions" not in expected:
        expected.update(
            {
                "allowed_conclusions": [
                    "SUPPORTED",
                    "REFUTED",
                    "INCONCLUSIVE",
                    "UNAVAILABLE",
                ],
                "required_scope_terms": [spec.task_id],
            }
        )
    (tests / "expected.json").write_text(
        json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (tests / "criteria.py").write_text(_verifier_source(), encoding="utf-8")
    (tests / "verifier_runtime.py").write_text(
        (PACKAGE_ROOT / "verifier_runtime.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    for index, dimension in enumerate(
        (
            "correctness",
            "evidence_validity",
            "scope_accuracy",
            "assurance_calibration",
        )
    ):
        (tests / dimension / "check.py").write_text(
            _dimension_source(index), encoding="utf-8"
        )
    (tests / "reward" / "check.py").write_text(
        "from rewardkit import criteria\ncriteria.aggregate_reward()\n",
        encoding="utf-8",
    )
    (tests / "test.sh").write_text(
        "#!/bin/sh\nset -eu\nrewardkit /tests\n",
        encoding="utf-8",
    )
    (tests / "Dockerfile").write_text(
        f"FROM {VERIFIER_IMAGE}\n"
        "RUN uv tool install 'harbor-rewardkit==0.1.7'\n"
        'ENV PATH="/root/.local/bin:$PATH"\n'
        "COPY . /tests\n"
        "RUN chmod +x /tests/test.sh\n",
        encoding="utf-8",
    )
    (root / "solution" / "solve.sh").chmod(0o755)
    (tests / "test.sh").chmod(0o755)


def compile_tasks(
    *,
    output_dir: Path,
    split: Split = Split.COVERAGE,
    limit: int | None = None,
    overwrite: bool = False,
    task_ids: frozenset[str] = frozenset(),
    source_ids: frozenset[str] = frozenset(),
    cache_dir: Path | None = None,
    offline: bool = False,
    strict_coverage: bool = False,
) -> tuple[Path, ...]:
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    report_cache_dir = (
        None
        if split in {Split.PUBLIC, Split.FULL}
        or (
            task_ids
            and task_ids
            <= frozenset(spec.task_id for spec in _public_tasks())
        )
        else cache_dir
    )
    all_specs = task_specs(
        cache_dir=report_cache_dir,
        offline=offline,
        full=False,
        selected_source_ids=source_ids,
    )
    report = coverage_report(load_sources(), all_specs)
    if strict_coverage and split != Split.PUBLIC:
        require_complete_coverage(report)
    if split == Split.FULL:
        if cache_dir is None:
            raise ValueError("full generation requires --cache-dir")
        selected_iter: Iterable[TaskSpec] = iter_full_task_specs(
            cache_dir=cache_dir,
            offline=offline,
            source_ids=source_ids,
        )
        if task_ids:
            selected_iter = (spec for spec in selected_iter if spec.task_id in task_ids)
        if limit is not None:
            selected_iter = itertools.islice(selected_iter, limit)
        selected: Iterable[TaskSpec] = selected_iter
    else:
        bounded = select_tasks(
            split=split,
            task_ids=task_ids,
            source_ids=source_ids,
            cache_dir=cache_dir,
            offline=offline,
        )
        selected = bounded[:limit] if limit is not None else bounded
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    manifest_tasks: list[dict[str, object]] = []
    full_records_path = output_dir / "generation-task-records.jsonl"
    if split == Split.FULL:
        full_records_path.write_text("", encoding="utf-8")
    dataset_hasher = hashlib.sha256()
    for spec in selected:
        destination = output_dir / stable_task_name(spec).split("/", 1)[1]
        if destination.exists():
            if not overwrite:
                raise FileExistsError(destination)
            shutil.rmtree(destination)
        _write_task(destination, spec)
        findings = scan_agent_bundle(destination)
        if findings:
            details = ", ".join(
                f"{finding.path}: {finding.reason}" for finding in findings
            )
            raise ValueError(f"agent bundle leakage detected: {details}")
        written.append(destination)
        task_record = {
            "task_id": spec.task_id,
            "name": stable_task_name(spec),
            "family": spec.family,
            "source_ids": list(spec.source_ids),
            "scored": spec.scored,
            "admissible_for_publish": spec.admissible_for_publish,
            "readiness": spec.readiness.value,
            "oracle_kind": spec.oracle_kind.value,
        }
        dataset_hasher.update(
            json.dumps(task_record, sort_keys=True, separators=(",", ":")).encode()
        )
        if split == Split.FULL:
            with full_records_path.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        task_record, sort_keys=True, separators=(",", ":")
                    )
                    + "\n"
                )
        else:
            manifest_tasks.append(task_record)
    manifest = {
        "adapter": "jacobian-math-evals",
        "schema_version": "1",
        "split": split.value,
        "task_count": len(written),
        "dataset_digest": "sha256:" + dataset_hasher.hexdigest(),
        "tasks": manifest_tasks,
        "task_records": (
            {
                "format": "jsonl",
                "path": full_records_path.name,
                "count": len(written),
            }
            if split == Split.FULL
            else None
        ),
        "coverage": {
            "complete": report.complete,
            "catalog_source_count": report.catalog_source_count,
            "referenced_source_count": report.referenced_source_count,
            "meaningful_source_count": report.meaningful_source_count,
            "ready_scored_task_count": report.ready_scored_task_count,
            "public_diagnostic_count": report.public_diagnostic_count,
            "manual_required_task_count": report.manual_required_task_count,
            "missing_source_ids": list(report.missing_source_ids),
            "merely_referenced_source_ids": list(report.merely_referenced_source_ids),
        },
    }
    (output_dir / "generation-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return tuple(written)
