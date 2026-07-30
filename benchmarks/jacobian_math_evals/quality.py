"""Fail-closed semantic readiness and source-coverage gates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import SourceRecord, TaskReadiness, TaskSpec


@dataclass(frozen=True)
class CoverageReport:
    catalog_source_count: int
    referenced_source_count: int
    meaningful_source_count: int
    ready_scored_task_count: int
    public_diagnostic_count: int
    manual_required_task_count: int
    missing_source_ids: tuple[str, ...]
    merely_referenced_source_ids: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return (
            self.meaningful_source_count == self.catalog_source_count
            and not self.missing_source_ids
            and not self.merely_referenced_source_ids
        )


class CoverageGateError(ValueError):
    """Raised when catalog references are mistaken for meaningful task coverage."""


@dataclass(frozen=True)
class LeakageFinding:
    path: str
    reason: str


def scan_agent_bundle(task_root: Path) -> tuple[LeakageFinding, ...]:
    """Scan files mounted or prompted to the agent, excluding verifier/solution."""

    visible = (
        task_root / "instruction.md",
        task_root / "task.toml",
        task_root / "source.json",
        task_root / "submission.schema.json",
    )
    environment = task_root / "environment"
    files = [path for path in visible if path.is_file()]
    if environment.is_dir():
        files.extend(path for path in environment.rglob("*") if path.is_file())
    forbidden = {
        "expected_answer": "oracle answer key",
        "accepted_answers": "oracle alternative key",
        "oracle-contract": "oracle solution artifact",
        "/tests/expected.json": "verifier answer path",
        "/solution/": "solution mount path",
    }
    findings: list[LeakageFinding] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for needle, reason in forbidden.items():
            if needle in text:
                findings.append(
                    LeakageFinding(
                        path=str(path.relative_to(task_root)),
                        reason=reason,
                    )
                )
    return tuple(findings)


def coverage_report(
    sources: tuple[SourceRecord, ...],
    specs: tuple[TaskSpec, ...],
) -> CoverageReport:
    catalog_ids = {source.source_id for source in sources}
    referenced_ids = {
        source_id
        for spec in specs
        for source_id in spec.source_ids
        if source_id in catalog_ids
    }
    meaningful_ids = {
        source_id
        for spec in specs
        if spec.readiness in {TaskReadiness.READY, TaskReadiness.PUBLIC_DIAGNOSTIC}
        and spec.oracle_kind != "none"
        for source_id in spec.source_ids
        if source_id in catalog_ids
    }
    return CoverageReport(
        catalog_source_count=len(catalog_ids),
        referenced_source_count=len(referenced_ids),
        meaningful_source_count=len(meaningful_ids),
        ready_scored_task_count=sum(
            spec.scored and spec.readiness == TaskReadiness.READY for spec in specs
        ),
        public_diagnostic_count=sum(
            spec.readiness == TaskReadiness.PUBLIC_DIAGNOSTIC for spec in specs
        ),
        manual_required_task_count=sum(
            spec.readiness == TaskReadiness.MANUAL_REQUIRED for spec in specs
        ),
        missing_source_ids=tuple(sorted(catalog_ids - referenced_ids)),
        merely_referenced_source_ids=tuple(sorted(referenced_ids - meaningful_ids)),
    )


def require_complete_coverage(report: CoverageReport) -> None:
    if report.complete:
        return
    raise CoverageGateError(
        "semantic coverage incomplete: "
        f"{report.meaningful_source_count}/{report.catalog_source_count} sources "
        f"meaningfully covered; {len(report.missing_source_ids)} unreferenced; "
        f"{len(report.merely_referenced_source_ids)} placeholder-only"
    )
