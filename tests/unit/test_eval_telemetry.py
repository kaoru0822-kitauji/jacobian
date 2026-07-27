from __future__ import annotations

import json
from pathlib import Path

from jacobian.eval_telemetry import parse_agent_transcript


def _tool_event(
    tool: str,
    arguments: dict[str, object],
    response: dict[str, object],
) -> dict[str, object]:
    return {
        "type": "item.completed",
        "item": {
            "type": "mcp_tool_call",
            "tool": tool,
            "arguments": arguments,
            "status": "completed",
            "result": {
                "isError": False,
                "content": [{"type": "text", "text": json.dumps(response)}],
            },
        },
    }


def test_agent_telemetry_preserves_discovery_to_invocation_dataflow(
    tmp_path: Path,
) -> None:
    events = [
        _tool_event(
            "capability.describe",
            {
                "query": "find a graph counterexample",
                "domain": "graph",
                "mode": "EXPLORE",
            },
            {
                "kind": "discovery",
                "matches": [
                    {"capability_id": "graph.search.atlas"},
                    {"capability_id": "graph.compute.properties"},
                ],
            },
        ),
        _tool_event(
            "capability.describe",
            {"capability_id": "graph.search.atlas"},
            {
                "kind": "capability",
                "capability": {"capability_id": "graph.search.atlas"},
            },
        ),
        _tool_event(
            "capability.invoke",
            {
                "capability_id": "graph.search.atlas",
                "mode": "EXPLORE",
                "payload": {"order": 7},
            },
            {
                "capability_id": "graph.search.atlas",
                "execution": {"status": "COMPLETED"},
                "output": {"status": "FOUND"},
                "artifact_uris": [],
                "assurance": {"level": "COMPUTED"},
                "completeness": {"status": "COMPLETE"},
            },
        ),
    ]
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    telemetry = parse_agent_transcript(transcript)

    assert telemetry["capability_descriptions"] == [
        {
            "kind": "discovery",
            "query": "find a graph counterexample",
            "domain": "graph",
            "mode": "EXPLORE",
            "capability_id": None,
            "match_ids": [
                "graph.search.atlas",
                "graph.compute.properties",
            ],
        },
        {
            "kind": "capability",
            "query": None,
            "domain": None,
            "mode": None,
            "capability_id": "graph.search.atlas",
            "match_ids": [],
        },
    ]
    assert telemetry["capability_attempt_ids"] == ["graph.search.atlas"]
    assert telemetry["capability_ids"] == ["graph.search.atlas"]
