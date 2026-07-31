from __future__ import annotations

import hashlib
import json
from pathlib import Path

APP = Path("/app")
REPORT = APP / "evidence" / "provider-report.json"
TASK_ID = "jacobian/provider-feasibility-v1-lean-repl"
PROVIDER = "lean-repl"
CONTRACT = "leanprover-community/repl@v4.31.0"
PIN = "sha256:7910ac2367d19cd57fc0d4ea6152605e8e085228c4083c6b1a0ed37ee0b18209"

report = json.loads(REPORT.read_text())
complete = (
    report.get("protocol") == "leanprover-community/repl"
    and report.get("task_count") == 2
    and report.get("completed_count") == 2
    and report.get("parameter_error_count") == 0
    and report.get("return_code") == 0
)
status = "COMPLETED" if complete else "ERROR"
(APP / "submission.json").write_text(
    json.dumps(
        {
            "task_id": TASK_ID,
            "conclusion": "FEASIBLE" if complete else "NO_CONCLUSION",
            "result": {
                "provider": PROVIDER,
                "contract": CONTRACT,
                "status": status,
                "pin_sha256": PIN,
            },
            "claimed_assurance": "COMPUTED" if complete else "UNVERIFIED",
            "scope": "pinned bounded provider reproduction",
            "completeness": "COMPLETE" if complete else "UNKNOWN",
            "evidence": [
                {
                    "path": "evidence/provider-report.json",
                    "sha256": "sha256:"
                    + hashlib.sha256(REPORT.read_bytes()).hexdigest(),
                }
            ],
            "limitations": [
                "provider output is not an operator-authorized independent verification",
                "task failure is a non-conclusion for Jacobian core availability",
            ],
        },
        sort_keys=True,
    )
    + "\n"
)
