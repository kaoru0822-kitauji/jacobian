from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from jsonschema import Draft202012Validator

from jacobian.contracts.graph_invariant_operations import GraphInvariantRequest
from jacobian.contracts.polynomial_operations import PolynomialGcdRequest
from jacobian.contracts.universal_algebra import (
    UniversalAlgebraCountermodelSearchRequest,
)
from jacobian.eval.mcp_resourcelink import (
    RESOURCE_LINK_PILOT_EPISODE_COUNT,
    ResourceLinkPilotObservation,
    build_resource_link_pilot_schedule,
    evaluate_resource_link_pilot,
    read_resource_link_observations,
    write_resource_link_observations,
)

ROOT = Path(__file__).parents[3]
EVALUATION = ROOT / "research" / "evaluations" / "mcp-resourcelink-v1"


def _load(name: str) -> dict[str, object]:
    payload = json.loads((EVALUATION / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_resource_link_plan_is_fail_closed_and_matches_schedule() -> None:
    plan = _load("pilot-plan.json")
    schema = _load("pilot-plan.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(plan)

    schedule = build_resource_link_pilot_schedule()
    assert len(schedule) == RESOURCE_LINK_PILOT_EPISODE_COUNT
    assert (
        len(
            {
                (episode.case_id, episode.projection, episode.repetition)
                for episode in schedule
            }
        )
        == RESOURCE_LINK_PILOT_EPISODE_COUNT
    )
    assert [episode.ordinal for episode in schedule] == list(
        range(1, RESOURCE_LINK_PILOT_EPISODE_COUNT + 1)
    )
    assert plan["episode_count"] == len(schedule)
    assert plan["execution_gate"]["model_execution_allowed"] is False


def test_resource_link_schedule_is_reproducible() -> None:
    assert build_resource_link_pilot_schedule() == build_resource_link_pilot_schedule()


def test_resource_link_cases_are_frozen_and_domain_validated() -> None:
    plan = _load("pilot-plan.json")
    cases = plan["cases"]
    assert isinstance(cases, list)
    for case in cases:
        assert isinstance(case, dict)
        case_id = case["case_id"]
        input_path = EVALUATION / "cases" / str(case_id) / "input.json"
        expected_path = EVALUATION / "cases" / str(case_id) / "expected_digest.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        assert payload["capability_id"] == case["capability_id"]
        assert expected == {
            "status": "UNMEASURED",
            "structured_content_digest": None,
            "reason": expected["reason"],
        }
        if case_id == "scalar-gcd":
            PolynomialGcdRequest.model_validate(payload["input"])
        elif case_id == "graph-distance":
            GraphInvariantRequest.model_validate(payload["input"])
        elif case_id == "countermodel-table":
            UniversalAlgebraCountermodelSearchRequest.model_validate(payload["input"])
        else:
            assert payload["setup"]
            assert payload["input"]["cnf_uri"].startswith("<setup:")


def _observations(
    *,
    large_successes: int = 8,
    false_certification: bool = False,
) -> tuple[ResourceLinkPilotObservation, ...]:
    observations: list[ResourceLinkPilotObservation] = []
    large_link_episode = 0
    for episode in build_resource_link_pilot_schedule():
        link = episode.projection == "COMPACT_URI_TEXT_RESOURCE_LINK"
        read_attempted = link
        read_succeeded: bool | None = None
        if link and episode.large_artifact:
            read_succeeded = large_link_episode < large_successes
            large_link_episode += 1
        elif link:
            read_succeeded = True
        observations.append(
            ResourceLinkPilotObservation(
                episode_id=f"RLP-{episode.ordinal:03d}",
                case_id=episode.case_id,
                capability_id=episode.capability_id,
                projection=episode.projection,
                structured_content_digest=f"sha256:{episode.case_id}",
                task_completed=True,
                false_certification=false_certification,
                assurance_regression=False,
                read_attempted=read_attempted,
                uri_preserved=True if read_attempted else None,
                resource_read_succeeded=read_succeeded,
                large_artifact=episode.large_artifact,
            )
        )
    return tuple(observations)


def test_resource_link_gate_accepts_the_preregistered_threshold() -> None:
    result = evaluate_resource_link_pilot(
        _observations(),
        expected_structured_content_digests={
            case_id: f"sha256:{case_id}"
            for case_id in {
                episode.case_id for episode in build_resource_link_pilot_schedule()
            }
        },
    )

    assert result.passed is True
    assert result.episode_count == 36
    assert result.large_artifact_followthrough == 8
    assert result.failures == ()


def test_resource_link_gate_rejects_false_certification() -> None:
    result = evaluate_resource_link_pilot(
        _observations(false_certification=True),
        expected_structured_content_digests={
            case_id: f"sha256:{case_id}"
            for case_id in {
                episode.case_id for episode in build_resource_link_pilot_schedule()
            }
        },
    )

    assert result.passed is False
    assert result.false_certifications == RESOURCE_LINK_PILOT_EPISODE_COUNT
    assert "false_certification" in result.failures


def test_resource_link_gate_rejects_changed_canonical_content() -> None:
    observations = list(_observations())
    observations[1] = replace(
        observations[1],
        structured_content_digest="sha256:changed",
    )

    result = evaluate_resource_link_pilot(
        tuple(observations),
        expected_structured_content_digests={
            case_id: f"sha256:{case_id}"
            for case_id in {
                episode.case_id for episode in build_resource_link_pilot_schedule()
            }
        },
    )

    assert result.passed is False
    assert "structured_content_changed" in result.failures


def test_resource_link_gate_rejects_missing_baseline() -> None:
    result = evaluate_resource_link_pilot(_observations())

    assert result.passed is False
    assert "structured_content_baseline_missing" in result.failures


def test_resource_link_observation_jsonl_round_trip_is_deterministic(
    tmp_path: Path,
) -> None:
    observations = _observations()
    path = tmp_path / "observations.jsonl"

    write_resource_link_observations(path, tuple(reversed(observations)))

    assert read_resource_link_observations(path) == observations
    episode_ids = [
        json.loads(line)["episode_id"]
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert episode_ids == sorted(episode_ids)
