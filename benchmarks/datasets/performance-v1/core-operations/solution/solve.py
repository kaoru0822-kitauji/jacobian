from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

APP = Path("/app")
RAW = APP / "evidence" / "pyperf.json"
ENVIRONMENT = APP / "evidence" / "environment.json"
TASK_ID = "jacobian/core-operations"
SUITE = "jacobian-v0.2-core"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


raw = json.loads(RAW.read_text())
benchmarks = raw.get("benchmarks")
if not isinstance(benchmarks, list) or not benchmarks:
    raise SystemExit("pyperf did not emit benchmark records")
ENVIRONMENT.write_text(
    json.dumps(
        {
            "python": sys.version,
            "platform": platform.platform(),
            "repository_revision": "6fd5fc5df6bc49f230484bc5c78cbd365941c78c",
            "driver_sha256": "sha256:34976a14407036a4e87f9d9347f2673dde28c1ca21b80021ad7cca93cdd1bd78",
        },
        sort_keys=True,
    )
    + "\n"
)
(APP / "submission.json").write_text(
    json.dumps(
        {
            "task_id": TASK_ID,
            "conclusion": "MEASURED",
            "result": {
                "suite": SUITE,
                "benchmark_count": len(benchmarks),
                "raw_format": "pyperf",
            },
            "claimed_assurance": "COMPUTED",
            "scope": "fixed repository driver and pinned runtime environment",
            "completeness": "COMPLETE",
            "evidence": [
                {"path": "evidence/pyperf.json", "sha256": digest(RAW)},
                {
                    "path": "evidence/environment.json",
                    "sha256": digest(ENVIRONMENT),
                },
            ],
            "limitations": [
                "timing thresholds are report-only",
                "measurements do not establish mathematical correctness",
            ],
        },
        sort_keys=True,
    )
    + "\n"
)
