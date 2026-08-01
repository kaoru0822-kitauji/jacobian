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
    assert len(call_result.content) == 2
    link = call_result.content[1]
    assert link.type == "resource_link"
    assert link.uri == result.episode_uri
    assert link.mime_type == "application/json"
    assert link.size == len(
        json.dumps(
            result.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )
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
    assert len(call_result.content) == 1


def test_resource_link_comparison_strategies_keep_structured_content_canonical() -> (
    None
):
    result = _large_result(durable=True)

    full_inline = _capability_call_tool_result(
        result,
        view="STANDARD",
        projection_strategy="FULL_INLINE",
    )
    compact_uri_text = _capability_call_tool_result(
        result,
        view="STANDARD",
        projection_strategy="COMPACT_URI_TEXT",
    )
    compact_with_link = _capability_call_tool_result(
        result,
        view="STANDARD",
        projection_strategy="COMPACT_URI_TEXT_RESOURCE_LINK",
    )

    assert len(full_inline.content) == 1
    assert json.loads(full_inline.content[0].text)["output"] == result.output
    assert len(compact_uri_text.content) == 1
    assert json.loads(compact_uri_text.content[0].text)["output"] == {"status": "FOUND"}
    assert len(compact_with_link.content) == 2
    assert compact_with_link.content[1].type == "resource_link"
    for call_result in (full_inline, compact_uri_text, compact_with_link):
        assert call_result.structured_content == result.model_dump(mode="json")


def test_full_invocation_view_is_honored_by_every_projection_strategy() -> None:
    result = _large_result(durable=True)

    for strategy in (
        "FULL_INLINE",
        "COMPACT_URI_TEXT",
        "COMPACT_URI_TEXT_RESOURCE_LINK",
    ):
        call_result = _capability_call_tool_result(
            result,
            view="FULL",
            projection_strategy=strategy,
        )

        assert call_result.is_error is False
        assert json.loads(call_result.content[0].text)["output"] == result.output
        assert "mcp_projection" not in json.loads(call_result.content[0].text)
