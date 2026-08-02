"""Generate the deterministic output record for the Harbor adapter fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.tooling.harbor_digest import task_digest  # noqa: E402

DATASET = "agent-workflow-v1"
TASK_ID = "graph-counterexample"
SOURCE_ROW = "task-model-smoke/graph-counterexample"


def build_record() -> dict[str, str]:
    task = ROOT / "benchmarks" / "datasets" / DATASET / TASK_ID
    return {
        "adapter_id": "harbor-task-model-smoke",
        "dataset": DATASET,
        "generator_version": "1",
        "source_row": SOURCE_ROW,
        "task_digest": "sha256:" + task_digest(task).removeprefix("sha256:"),
        "task_id": TASK_ID,
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: generate.py OUTPUT")
    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build_record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
