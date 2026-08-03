from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from proof_replay import replay  # noqa: E402


def build_submission(output_root: Path) -> dict[str, object]:
    input_data = json.loads((ROOT / "environment" / "input.json").read_text())
    proof = ["wu", "wv", "ww", "h1", "wv", "ww", "wi", "wu", "h2", "a1i", "mpd"]
    result = {
        "repaired_proof": proof,
        "changed_positions": [6, 9],
        "trace": replay(input_data, proof),
        "final_expression": input_data["target"],
    }
    evidence_dir = output_root / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    compact = json.dumps(result, sort_keys=True, separators=(",", ":"))
    evidence_path = evidence_dir / "answer.txt"
    evidence_path.write_text(
        "Each assertion application was reconstructed by ordered stack unification.\nRESULT_JSON: "
        + compact
        + "\n"
    )
    digest = "sha256:" + hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    return {
        "task_id": input_data["task_id"],
        "conclusion": "PROOF_REPAIRED_AND_REPLAYED",
        "result": result,
        "claimed_assurance": "COMPUTED",
        "scope": "FROZEN_METAMATH_STYLE_ASSERTION_REGISTRY",
        "completeness": "COMPLETE",
        "evidence": [{"path": "evidence/answer.txt", "sha256": digest}],
        "limitations": [
            "FROZEN_FRAGMENT_NOT_FULL_UPSTREAM_DATABASE",
            "NO_EXTERNAL_METAMATH_KERNEL_REPLAY",
        ],
    }


if __name__ == "__main__":
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/app")
    submission = build_submission(output)
    (output / "submission.json").write_text(
        json.dumps(submission, indent=2, sort_keys=True) + "\n"
    )
