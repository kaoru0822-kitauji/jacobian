"""Render the explicitly supported environment fields in a Harbor job template.

Resolves the single ``${JACOBIAN_MODEL}`` placeholder in a Harbor job config
before Harbor starts, and rejects any other ``${...}`` placeholder so that
Harbor's Docker compose mode never receives unresolved job-level env
templating. The heavy lifting lives in
:mod:`benchmarks.tooling.harbor_suite`; this script is the CLI entry point
used by ``make agent-eval``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.tooling.harbor_suite import (  # noqa: E402
    MODEL_PLACEHOLDER,
    get_suite,
    render_job_config,
    render_suite_job,
)

__all__ = ["MODEL_PLACEHOLDER", "render_job_config"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--dataset", help="short or full registered dataset id")
    parser.add_argument(
        "--role", choices=("oracle", "observation"), default="observation"
    )
    parser.add_argument(
        "--provider",
        help="restrict a suite job to tasks requiring this provider",
    )
    parser.add_argument(
        "--tasks",
        nargs="*",
        help="restrict a suite job to these canonical task IDs",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--model",
        required=True,
        help="model identifier to substitute for ${JACOBIAN_MODEL}",
    )
    args = parser.parse_args()
    if args.dataset:
        rendered = render_suite_job(
            get_suite(args.dataset),
            role=args.role,
            model=args.model,
            provider=args.provider,
            tasks=tuple(args.tasks) if args.tasks else None,
        )
    else:
        if args.provider:
            parser.error("--provider requires --dataset")
        if args.input is None:
            parser.error("--input or --dataset is required")
        config = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("job config must be a JSON object")
        rendered = render_job_config(config, model=args.model)
    args.output.write_text(
        json.dumps(rendered, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
