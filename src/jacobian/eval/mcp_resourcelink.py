"""Frozen, credential-free gates for the MCP ResourceLink pilot.

This module schedules and scores evidence after an operator supplies model
traces.  It does not invoke a model, select a projection for an agent, or
authorize a production MCP contract.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Any, Literal

ResourceLinkProjection = Literal[
    "FULL_INLINE",
    "COMPACT_URI_TEXT",
    "COMPACT_URI_TEXT_RESOURCE_LINK",
]
ResourceLinkCaseKind = Literal[
    "SCALAR",
    "GRAPH_DISTANCE",
    "COUNTERMODEL_TABLE",
    "CERTIFICATE_VERIFICATION",
]

RESOURCE_LINK_PILOT_SEED = 104729
RESOURCE_LINK_PILOT_REPETITIONS = 3
RESOURCE_LINK_PILOT_EPISODE_COUNT = 36
RESOURCE_LINK_PROJECTIONS: tuple[ResourceLinkProjection, ...] = (
    "FULL_INLINE",
    "COMPACT_URI_TEXT",
    "COMPACT_URI_TEXT_RESOURCE_LINK",
)


@dataclass(frozen=True, slots=True)
class _PilotCase:
    case_id: str
    kind: ResourceLinkCaseKind
    capability_id: str
    large_artifact: bool
    baseline_structured_content_digest: str | None = None


_PILOT_CASES: tuple[_PilotCase, ...] = (
    _PilotCase(
        case_id="scalar-gcd",
        kind="SCALAR",
        capability_id="polynomial.compute.gcd",
        large_artifact=False,
    ),
    _PilotCase(
        case_id="graph-distance",
        kind="GRAPH_DISTANCE",
        capability_id="graph.distance_matrix.compute",
        large_artifact=True,
    ),
    _PilotCase(
        case_id="countermodel-table",
        kind="COUNTERMODEL_TABLE",
        capability_id="universal_algebra.search.countermodel",
        large_artifact=True,
    ),
    _PilotCase(
        case_id="certificate-verification",
        kind="CERTIFICATE_VERIFICATION",
        capability_id="sat.lrat.verify",
        large_artifact=True,
    ),
)


@dataclass(frozen=True, slots=True)
class ResourceLinkPilotEpisode:
    """One pre-registered case/projection/repetition assignment."""

    ordinal: int
    case_id: str
    case_kind: ResourceLinkCaseKind
    capability_id: str
    projection: ResourceLinkProjection
    repetition: int
    seed: int = RESOURCE_LINK_PILOT_SEED
    large_artifact: bool = False

    def __post_init__(self) -> None:
        if self.ordinal < 1 or self.repetition < 1:
            raise ValueError("pilot ordinals and repetitions must be positive")
        if self.seed != RESOURCE_LINK_PILOT_SEED:
            raise ValueError("the ResourceLink pilot seed is frozen")


def build_resource_link_pilot_schedule() -> tuple[ResourceLinkPilotEpisode, ...]:
    """Return the deterministic 3-by-4-by-3 pilot schedule."""

    cases_by_id = {case.case_id: case for case in _PILOT_CASES}
    rows = [
        (case, projection, repetition)
        for case in _PILOT_CASES
        for projection in RESOURCE_LINK_PROJECTIONS
        for repetition in range(1, RESOURCE_LINK_PILOT_REPETITIONS + 1)
    ]
    Random(RESOURCE_LINK_PILOT_SEED).shuffle(rows)
    episodes: list[ResourceLinkPilotEpisode] = []
    for ordinal, (case, projection, repetition) in enumerate(rows, start=1):
        resolved = cases_by_id[case.case_id]
        episodes.append(
            ResourceLinkPilotEpisode(
                ordinal=ordinal,
                case_id=resolved.case_id,
                case_kind=resolved.kind,
                capability_id=resolved.capability_id,
                projection=projection,
                repetition=repetition,
                large_artifact=resolved.large_artifact,
            )
        )
    return tuple(episodes)


@dataclass(frozen=True, slots=True)
class ResourceLinkPilotObservation:
    """Evidence collected for one scheduled episode."""

    episode_id: str
    case_id: str
    capability_id: str
    projection: ResourceLinkProjection
    structured_content_digest: str
    task_completed: bool
    false_certification: bool
    assurance_regression: bool
    read_attempted: bool
    uri_preserved: bool | None
    resource_read_succeeded: bool | None
    large_artifact: bool


@dataclass(frozen=True, slots=True)
class ResourceLinkPilotGate:
    """Fail-closed result of scoring a complete pilot evidence set."""

    passed: bool
    episode_count: int
    false_certifications: int
    assurance_regressions: int
    incomplete_tasks: int
    uri_preservation_failures: int
    large_artifact_followthrough: int
    failures: tuple[str, ...]


def _observation_record(observation: ResourceLinkPilotObservation) -> dict[str, Any]:
    return {
        "record_type": "jacobian.mcp-resourcelink.observation/v1",
        "episode_id": observation.episode_id,
        "case_id": observation.case_id,
        "capability_id": observation.capability_id,
        "projection": observation.projection,
        "structured_content_digest": observation.structured_content_digest,
        "task_completed": observation.task_completed,
        "false_certification": observation.false_certification,
        "assurance_regression": observation.assurance_regression,
        "read_attempted": observation.read_attempted,
        "uri_preserved": observation.uri_preserved,
        "resource_read_succeeded": observation.resource_read_succeeded,
        "large_artifact": observation.large_artifact,
    }


def write_resource_link_observations(
    path: Path,
    observations: tuple[ResourceLinkPilotObservation, ...],
) -> None:
    """Write normalized one-record-per-episode evidence in deterministic order."""

    records = sorted(observations, key=lambda item: item.episode_id)
    path.write_text(
        "".join(
            json.dumps(
                _observation_record(observation),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for observation in records
        ),
        encoding="utf-8",
    )


def _required_observation_string(
    record: dict[str, Any], key: str, line_number: int
) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(
            f"invalid ResourceLink observation field {key} at line {line_number}"
        )
    return value


def _required_observation_bool(
    record: dict[str, Any], key: str, line_number: int
) -> bool:
    value = record.get(key)
    if type(value) is not bool:
        raise ValueError(
            f"invalid ResourceLink observation field {key} at line {line_number}"
        )
    return value


def _optional_observation_bool(
    record: dict[str, Any], key: str, line_number: int
) -> bool | None:
    value = record.get(key)
    if value is not None and type(value) is not bool:
        raise ValueError(
            f"invalid ResourceLink observation field {key} at line {line_number}"
        )
    return value


def read_resource_link_observations(
    path: Path,
) -> tuple[ResourceLinkPilotObservation, ...]:
    """Read normalized pilot evidence without inferring missing gate facts."""

    observations: list[ResourceLinkPilotObservation] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid ResourceLink observation JSON at line {line_number}"
            ) from exc
        if not isinstance(record, dict):
            raise ValueError(
                f"ResourceLink observation at line {line_number} must be an object"
            )
        if record.get("record_type") != "jacobian.mcp-resourcelink.observation/v1":
            raise ValueError(
                f"unsupported ResourceLink observation at line {line_number}"
            )
        expected_fields = {
            "record_type",
            "episode_id",
            "case_id",
            "capability_id",
            "projection",
            "structured_content_digest",
            "task_completed",
            "false_certification",
            "assurance_regression",
            "read_attempted",
            "uri_preserved",
            "resource_read_succeeded",
            "large_artifact",
        }
        if set(record) != expected_fields:
            raise ValueError(
                f"unexpected ResourceLink observation fields at line {line_number}"
            )

        episode_id = _required_observation_string(record, "episode_id", line_number)
        if not episode_id.startswith("RLP-"):
            raise ValueError(f"invalid ResourceLink episode id at line {line_number}")
        projection = _required_observation_string(record, "projection", line_number)
        if projection not in RESOURCE_LINK_PROJECTIONS:
            raise ValueError(
                f"unsupported ResourceLink projection at line {line_number}"
            )
        observations.append(
            ResourceLinkPilotObservation(
                episode_id=episode_id,
                case_id=_required_observation_string(record, "case_id", line_number),
                capability_id=_required_observation_string(
                    record, "capability_id", line_number
                ),
                projection=projection,
                structured_content_digest=_required_observation_string(
                    record, "structured_content_digest", line_number
                ),
                task_completed=_required_observation_bool(
                    record, "task_completed", line_number
                ),
                false_certification=_required_observation_bool(
                    record, "false_certification", line_number
                ),
                assurance_regression=_required_observation_bool(
                    record, "assurance_regression", line_number
                ),
                read_attempted=_required_observation_bool(
                    record, "read_attempted", line_number
                ),
                uri_preserved=_optional_observation_bool(
                    record, "uri_preserved", line_number
                ),
                resource_read_succeeded=_optional_observation_bool(
                    record, "resource_read_succeeded", line_number
                ),
                large_artifact=_required_observation_bool(
                    record, "large_artifact", line_number
                ),
            )
        )
    episode_ids = [observation.episode_id for observation in observations]
    if len(episode_ids) != len(set(episode_ids)):
        raise ValueError("duplicate ResourceLink pilot episode")
    return tuple(sorted(observations, key=lambda item: item.episode_id))


def _binding_failure(
    observation: ResourceLinkPilotObservation,
    expected: ResourceLinkPilotEpisode | None,
) -> str | None:
    if expected is None:
        return None
    if (
        observation.case_id != expected.case_id
        or observation.capability_id != expected.capability_id
        or observation.projection != expected.projection
        or observation.large_artifact != expected.large_artifact
    ):
        return f"episode_binding:{observation.episode_id}"
    return None


def _gate_failures(
    *,
    episode_count: int,
    episode_identity_ok: bool,
    binding_failures: tuple[str, ...],
    false_certifications: int,
    assurance_regressions: int,
    incomplete_tasks: int,
    uri_preservation_failures: int,
    large_followthrough: int,
    structured_content_changed: bool,
    structured_content_baseline_failures: tuple[str, ...],
) -> tuple[str, ...]:
    failures = list(binding_failures)
    if episode_count != RESOURCE_LINK_PILOT_EPISODE_COUNT:
        failures.append("episode_count")
    if not episode_identity_ok:
        failures.append("episode_identity")
    if false_certifications:
        failures.append("false_certification")
    if assurance_regressions:
        failures.append("assurance_regression")
    if incomplete_tasks:
        failures.append("task_completion")
    if uri_preservation_failures:
        failures.append("uri_preservation")
    if large_followthrough < 8:
        failures.append("large_artifact_followthrough")
    if structured_content_changed:
        failures.append("structured_content_changed")
    failures.extend(structured_content_baseline_failures)
    return tuple(dict.fromkeys(failures))


def _baseline_failures(
    observations: tuple[ResourceLinkPilotObservation, ...],
    expected_digests: Mapping[str, str],
) -> tuple[str, ...]:
    case_ids = {case.case_id for case in _PILOT_CASES}
    failures: list[str] = []
    if set(expected_digests) != case_ids:
        failures.append("structured_content_baseline_missing")
    for case_id, expected_digest in expected_digests.items():
        observed = {
            observation.structured_content_digest
            for observation in observations
            if observation.case_id == case_id
        }
        if observed != {expected_digest}:
            failures.append(f"structured_content_baseline:{case_id}")
    return tuple(failures)


def evaluate_resource_link_pilot(
    observations: tuple[ResourceLinkPilotObservation, ...],
    *,
    expected_structured_content_digests: Mapping[str, str] | None = None,
) -> ResourceLinkPilotGate:
    """Score the frozen pilot without treating missing evidence as success."""

    schedule = build_resource_link_pilot_schedule()
    if expected_structured_content_digests is None:
        expected_structured_content_digests = {
            case.case_id: case.baseline_structured_content_digest
            for case in _PILOT_CASES
            if case.baseline_structured_content_digest is not None
        }
    expected_ids = {f"RLP-{episode.ordinal:03d}": episode for episode in schedule}
    expected_observations = [
        expected_ids.get(observation.episode_id) for observation in observations
    ]
    binding_failures = tuple(
        failure
        for observation, expected in zip(
            observations, expected_observations, strict=False
        )
        if (failure := _binding_failure(observation, expected)) is not None
    )
    by_case = {
        case_id: {
            observation.structured_content_digest
            for observation in observations
            if observation.case_id == case_id
        }
        for case_id in {observation.case_id for observation in observations}
    }
    false_certifications = sum(
        observation.false_certification for observation in observations
    )
    assurance_regressions = sum(
        observation.assurance_regression for observation in observations
    )
    incomplete_tasks = sum(
        not observation.task_completed for observation in observations
    )
    uri_preservation_failures = sum(
        observation.read_attempted and observation.uri_preserved is not True
        for observation in observations
    )
    large_followthrough = sum(
        observation.projection == "COMPACT_URI_TEXT_RESOURCE_LINK"
        and observation.large_artifact
        and observation.resource_read_succeeded is True
        for observation in observations
    )
    failures = _gate_failures(
        episode_count=len(observations),
        episode_identity_ok={observation.episode_id for observation in observations}
        == set(expected_ids),
        binding_failures=binding_failures,
        false_certifications=false_certifications,
        assurance_regressions=assurance_regressions,
        incomplete_tasks=incomplete_tasks,
        uri_preservation_failures=uri_preservation_failures,
        large_followthrough=large_followthrough,
        structured_content_changed=any(
            len(digests) != 1 for digests in by_case.values()
        ),
        structured_content_baseline_failures=_baseline_failures(
            observations, expected_structured_content_digests
        ),
    )

    return ResourceLinkPilotGate(
        passed=not failures,
        episode_count=len(observations),
        false_certifications=false_certifications,
        assurance_regressions=assurance_regressions,
        incomplete_tasks=incomplete_tasks,
        uri_preservation_failures=uri_preservation_failures,
        large_artifact_followthrough=large_followthrough,
        failures=failures,
    )
