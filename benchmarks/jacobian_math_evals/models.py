"""Typed contracts for the internal mathematical evaluation suite."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class Split(StrEnum):
    PUBLIC = "public"
    COVERAGE = "coverage"
    TRAIN = "train"
    DEV = "dev"
    TEST = "test"
    FULL = "full"
    SMOKE = "smoke"


class SourceState(StrEnum):
    PUBLIC = "public"
    GATED = "gated"
    INTERNAL_ONLY = "internal-only"
    UNAVAILABLE = "unavailable"
    MOVED = "moved"
    ARCHIVED = "archived"
    UNRESOLVED = "unresolved"


class TaskReadiness(StrEnum):
    READY = "ready"
    PUBLIC_DIAGNOSTIC = "public-diagnostic"
    MANUAL_REQUIRED = "manual-required"
    UNAVAILABLE = "unavailable"


class OracleKind(StrEnum):
    DETERMINISTIC = "deterministic"
    PROOF_REPLAY = "proof-replay"
    CERTIFICATE_CHECKER = "certificate-checker"
    PUBLIC_ANSWER = "public-answer"
    NONE = "none"


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    url: str
    canonical_url: str
    kind: str
    host: str
    source_type: str
    domain: str
    claim_type: str
    verification_level: str
    artifacts: str
    conjecture_name: str
    upstream_status: str
    usefulness: str
    notes: str
    acquisition_hint: str
    duplicate_urls: tuple[str, ...]
    access_state: SourceState = SourceState.UNRESOLVED
    immutable_revision: str | None = None
    license: str | None = None
    evidence_timestamp: str | None = None
    snapshot_sha256: str | None = None
    repository_url: str | None = None
    subresource_path: str | None = None
    redirect_from: tuple[str, ...] = ()
    configurations: tuple[str, ...] = ()
    splits: tuple[str, ...] = ()
    row_count: int | None = None
    gated: bool | None = None
    parquet_shards: tuple[str, ...] = ()

    @property
    def acquisition_ready(self) -> bool:
        return (
            self.access_state in {SourceState.PUBLIC, SourceState.GATED}
            and bool(self.immutable_revision)
            and bool(self.evidence_timestamp)
        )


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    family: str
    source_ids: tuple[str, ...]
    split: Split
    instruction: str
    keywords: tuple[str, ...]
    scored: bool
    instance: dict[str, Any]
    expected: dict[str, Any]
    admissible_for_publish: bool
    readiness: TaskReadiness = TaskReadiness.MANUAL_REQUIRED
    oracle_kind: OracleKind = OracleKind.NONE
    manual: bool = False
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceReference:
    path: str
    sha256: str


@dataclass(frozen=True)
class Submission:
    task_id: str
    source_ids: tuple[str, ...]
    claimed_assurance: str
    evidence: tuple[EvidenceReference, ...]
    scope: str
    completeness: str
    conclusion: str | None = None
    answer: str | int | float | bool | None = None
    limitations: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> Submission:
        required = {
            "task_id",
            "source_ids",
            "claimed_assurance",
            "evidence",
            "scope",
            "completeness",
            "limitations",
        }
        missing = required - value.keys()
        if missing:
            raise ValueError(f"submission is missing fields: {sorted(missing)}")
        if "conclusion" not in value and "answer" not in value:
            raise ValueError("submission requires conclusion or answer")
        evidence = tuple(
            EvidenceReference(path=item["path"], sha256=item["sha256"])
            for item in value["evidence"]
        )
        submission = cls(
            task_id=value["task_id"],
            source_ids=tuple(value["source_ids"]),
            claimed_assurance=value["claimed_assurance"],
            evidence=evidence,
            scope=value["scope"],
            completeness=value["completeness"],
            conclusion=value.get("conclusion"),
            answer=value.get("answer"),
            limitations=tuple(value["limitations"]),
        )
        submission.validate_paths()
        return submission

    def validate_paths(self) -> None:
        for item in self.evidence:
            path = Path(item.path)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(
                    f"evidence path must be workspace-relative: {item.path}"
                )
            if not item.sha256.startswith("sha256:") or len(item.sha256) != 71:
                raise ValueError(f"invalid evidence digest: {item.sha256}")
