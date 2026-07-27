from __future__ import annotations

import json
from pathlib import Path

from jacobian.eval_telemetry import parse_agent_transcript


def test_agent_telemetry_counts_response_bytes_and_repeated_calls(
    tmp_path: Path,
) -> None:
    events = [
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "tool": "capability.describe",
                "arguments": {},
                "status": "completed",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "capabilities": [
                                        {"capability_id": "sat.cnf.materialize"}
                                    ]
                                }
                            ),
                        }
                    ],
                    "isError": False,
                },
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "tool": "capability.describe",
                "arguments": {},
                "status": "completed",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "capabilities": [
                                        {"capability_id": "sat.cnf.materialize"}
                                    ]
                                }
                            ),
                        }
                    ],
                    "isError": False,
                },
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "tool": "capability.describe",
                "arguments": {"capability_id": "sat.cnf.materialize"},
                "status": "completed",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {"capability": {"capability_id": "sat.cnf.materialize"}}
                            ),
                        }
                    ],
                    "isError": False,
                },
            },
        },
    ]
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )

    telemetry = parse_agent_transcript(transcript)

    assert telemetry["mcp_response_bytes"] > 0
    assert (
        telemetry["mcp_response_bytes_by_tool"]["capability.describe"]
        == (telemetry["mcp_response_bytes"])
    )
    assert telemetry["repeated_mcp_call_count"] == 1
    assert telemetry["repeated_mcp_calls"][0]["tool"] == "capability.describe"
    assert telemetry["repeated_mcp_calls"][0]["count"] == 2
    assert telemetry["capability_describe_index_calls"] == 2
    assert telemetry["capability_describe_exact_calls"] == 1
