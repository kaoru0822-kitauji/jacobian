#!/usr/bin/env python3
"""Generate invocation-example coverage reports from the installed catalog."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from jacobian.kernel import JacobianKernel

_ARTIFACT_KEYS = re.compile(
    r"(?:artifact|checker|proof[_-]?state|plugin|experiment|workspace|session|uri)",
    re.IGNORECASE,
)
_RUNTIME_TERMS = re.compile(r"(?:lean|plugin|runtime|cvc5|cadical|drat|flint)", re.I)


def _schema_contains(schema: Any, pattern: re.Pattern[str]) -> bool:
    if isinstance(schema, dict):
        return any(
            (isinstance(key, str) and pattern.search(key))
            or _schema_contains(value, pattern)
            for key, value in schema.items()
        )
    if isinstance(schema, list):
        return any(_schema_contains(value, pattern) for value in schema)
    return False


def _evidence(capability_id: str, root: Path) -> list[str]:
    hits: list[str] = []
    for path in sorted((root / "tests" / "integration").glob("test_*.py")):
        try:
            if capability_id in path.read_text(encoding="utf-8"):
                hits.append(str(path.relative_to(root)))
        except OSError:
            continue
    return hits


def _row(descriptor: Any, root: Path) -> dict[str, Any]:
    input_schema = descriptor.input_schema
    artifact_dependent = _schema_contains(input_schema, _ARTIFACT_KEYS)
    runtime_dependent = bool(
        _RUNTIME_TERMS.search(descriptor.provider)
        or _RUNTIME_TERMS.search(descriptor.capability_id)
        or any(_RUNTIME_TERMS.search(tag) for tag in descriptor.tags)
    )
    exclusions: list[str] = []
    if artifact_dependent:
        exclusions.append("artifact-dependent input or runtime URI")
    if runtime_dependent:
        exclusions.append("provider/runtime/plugin-dependent")
    examples = descriptor.invocation_examples
    validation_errors: list[dict[str, str]] = []
    validator = Draft202012Validator(input_schema)
    for example in examples:
        errors = sorted(
            validator.iter_errors(example.input), key=lambda error: list(error.path)
        )
        for error in errors:
            validation_errors.append(
                {
                    "example": example.name,
                    "path": ".".join(map(str, error.path)),
                    "message": error.message,
                }
            )
    evidence = _evidence(descriptor.capability_id, root)
    return {
        "capability_id": descriptor.capability_id,
        "provider": descriptor.provider,
        "modes": [mode.value for mode in descriptor.modes],
        "directly_invocable": not artifact_dependent and not runtime_dependent,
        "requires_runtime_generated_artifacts": artifact_dependent,
        "runtime_or_plugin_dependent": runtime_dependent,
        "has_invocation_examples": bool(examples),
        "invocation_example_count": len(examples),
        "examples_schema_valid": not validation_errors,
        "integration_test_evidence": evidence,
        "covered_by_integration_tests": bool(evidence),
        "known_exclusions": exclusions,
        "validation_errors": validation_errors,
    }


def build_report(root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="jacobian-example-coverage-") as directory:
        catalog = JacobianKernel(Path(directory)).capabilities.catalog()
    capabilities = [_row(descriptor, root) for descriptor in catalog.capabilities]
    capabilities.sort(key=lambda row: row["capability_id"])
    summary = {
        "total_capabilities": len(capabilities),
        "directly_invocable": sum(row["directly_invocable"] for row in capabilities),
        "artifact_dependent": sum(
            row["requires_runtime_generated_artifacts"] for row in capabilities
        ),
        "runtime_or_plugin_dependent": sum(
            row["runtime_or_plugin_dependent"] for row in capabilities
        ),
        "with_examples": sum(row["has_invocation_examples"] for row in capabilities),
        "missing_examples": sum(
            not row["has_invocation_examples"] for row in capabilities
        ),
        "schema_validation_failures": sum(
            not row["examples_schema_valid"] for row in capabilities
        ),
        "known_exclusions": sum(bool(row["known_exclusions"]) for row in capabilities),
    }
    return {"report_version": "1", "summary": summary, "capabilities": capabilities}


def _table(title: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Capability | Provider | Examples | Integration evidence | Notes |",
        "|---|---|---:|---|---|",
    ]
    for row in rows:
        evidence = ", ".join(row["integration_test_evidence"]) or "—"
        notes = ", ".join(row["known_exclusions"]) or "—"
        lines.append(
            f"| `{row['capability_id']}` | `{row['provider']}` | {row['invocation_example_count']} | {evidence} | {notes} |"
        )
    return [*lines, ""]


def to_markdown(report: dict[str, Any]) -> str:
    rows = report["capabilities"]
    summary = report["summary"]
    lines = [
        "# Capability Example Coverage",
        "",
        "Generated from the installed catalog; counts are not hand-maintained.",
        "",
        "| Metric | Count |",
        "|---|---:|",
    ]
    for key, value in summary.items():
        lines.append(f"| {key.replace('_', ' ').title()} | {value} |")
    lines.append("")
    lines += _table(
        "Missing examples", [row for row in rows if not row["has_invocation_examples"]]
    )
    lines += _table(
        "Already covered", [row for row in rows if row["has_invocation_examples"]]
    )
    lines += _table(
        "Artifact-dependent",
        [row for row in rows if row["requires_runtime_generated_artifacts"]],
    )
    lines += _table(
        "Runtime/plugin dependent",
        [row for row in rows if row["runtime_or_plugin_dependent"]],
    )
    lines += _table(
        "Known exclusions", [row for row in rows if row["known_exclusions"]]
    )
    lines += _table(
        "Validation failures", [row for row in rows if not row["examples_schema_valid"]]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--json", type=Path, default=Path("reports/capability-example-coverage.json")
    )
    parser.add_argument(
        "--markdown", type=Path, default=Path("reports/capability-example-coverage.md")
    )
    args = parser.parse_args()
    report = build_report(args.root.resolve())
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.markdown.write_text(to_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
