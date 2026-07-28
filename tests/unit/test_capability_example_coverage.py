from pathlib import Path
from types import SimpleNamespace

from scripts.capability_example_coverage import _row, build_report, to_markdown

from jacobian.contracts.capabilities import CapabilityInvocationExample, CapabilityMode
from jacobian.kernel import JacobianKernel


def test_report_runs_and_matches_installed_descriptors(tmp_path: Path) -> None:
    report = build_report(Path.cwd())
    catalog = JacobianKernel(tmp_path).capabilities.catalog()
    rows = {row["capability_id"]: row for row in report["capabilities"]}
    descriptors = {
        descriptor.capability_id: descriptor for descriptor in catalog.capabilities
    }
    assert set(rows) == set(descriptors)
    assert report["summary"]["total_capabilities"] == len(descriptors)
    assert all(
        row["invocation_example_count"]
        == len(descriptors[capability_id].invocation_examples)
        for capability_id, row in rows.items()
    )
    assert "# Capability Example Coverage" in to_markdown(report)


def test_schema_validation_failures_are_reported() -> None:
    descriptor = SimpleNamespace(
        capability_id="test.compute.value",
        provider="test.provider",
        modes=(CapabilityMode.EXPLORE,),
        tags=(),
        input_schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
        },
        invocation_examples=(
            CapabilityInvocationExample(
                name="bad",
                description="An intentionally invalid test example.",
                mode=CapabilityMode.EXPLORE,
                input={"value": "not-an-integer"},
            ),
        ),
    )
    row = _row(descriptor, Path.cwd())
    assert row["invocation_example_count"] == 1
    assert row["examples_schema_valid"] is False
    assert row["validation_errors"][0]["example"] == "bad"
