from __future__ import annotations

import json

from jacobian.adapters.mcp.projections import _capability_call_tool_result
from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityResult,
)
from jacobian.contracts.results import Execution, ExecutionStatus


def _large_result(*, durable: bool) -> CapabilityResult:
    return CapabilityResult(
        capability_id="test.large_result",
        capability_version="1",
        mode=CapabilityMode.EXPLORE,
        execution=Execution(status=ExecutionStatus.COMPLETED),
        output={
            "status": "FOUND",
            "rows": [{"index": index, "payload": "x" * 256} for index in range(64)],
        },
        assurance=CapabilityAssurance(
            level=CapabilityAssuranceLevel.COMPUTED,
            basis="exact fixture computation",
        ),
        episode_uri=("artifact://sha256/" + ("a" * 64) if durable else None),
    )


def test_standard_invocation_projection_is_compact_and_recoverable() -> None:
    result = _large_result(durable=True)

    call_result = _capability_call_tool_result(result, view="STANDARD")
    projection = json.loads(call_result.content[0].text)

    assert projection["output"] == {"status": "FOUND"}
    metadata = projection["mcp_projection"]
    assert metadata["output_complete"] is False
    assert metadata["full_result_episode_uri"] == result.episode_uri
    assert metadata["omitted_output_fields"] == [
        {
            "path": "/output/rows",
            "json_type": "array",
            "byte_count": metadata["omitted_output_fields"][0]["byte_count"],
            "sha256": metadata["omitted_output_fields"][0]["sha256"],
        }
    ]
    assert metadata["omitted_output_fields"][0]["byte_count"] > 8_192
    assert metadata["omitted_output_fields"][0]["sha256"].startswith("sha256:")
    assert call_result.structured_content == result.model_dump(mode="json")
    result_meta = call_result.meta["jacobian"]
    assert (
        result_meta["logical_payload_bytes"]
        > (result_meta["model_visible_payload_bytes"])
    )


def test_standard_invocation_does_not_drop_large_undurable_output() -> None:
    result = _large_result(durable=False)

    call_result = _capability_call_tool_result(result, view="STANDARD")
    projection = json.loads(call_result.content[0].text)

    assert projection["output"] == result.output
    assert projection["mcp_projection"]["output_complete"] is True
