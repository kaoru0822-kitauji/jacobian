from __future__ import annotations

import json
from pathlib import Path

from benchmarks.validation.mathematical_benchmarks_v1 import _fixtures, _verifier

TASK = "ratio-test-boundary-separation"


def test_result_protocol(tmp_path: Path) -> None:
    _fixtures.assert_result_witness_protocol(tmp_path, TASK)


def test_rejects_formula_string(tmp_path: Path) -> None:
    task, app, logs = _fixtures._prepare_case(tmp_path, TASK, "computed")
    path = app / "submission.json"
    submission = json.loads(path.read_text())
    submission["result"]["divergent_witness"]["term"] = "1/n"
    _fixtures._write_json(path, submission)
    assert _verifier._run_verifier(task, app, logs).reward == 0.0


def test_accepts_equivalent_unreduced_rational(tmp_path: Path) -> None:
    task, app, logs = _fixtures._prepare_case(tmp_path, TASK, "computed")
    path = app / "submission.json"
    submission = json.loads(path.read_text())
    value = submission["result"]["divergent_witness"]["blocks"][0]["block_lower_bound"]
    value["numerator"] *= 2
    value["denominator"] *= 2
    _fixtures._write_json(path, submission)
    assert _verifier._run_verifier(task, app, logs).reward == 1.0


def test_accepts_equivalent_rational_functions_and_reordered_telescope(
    tmp_path: Path,
) -> None:
    task, app, logs = _fixtures._prepare_case(tmp_path, TASK, "computed")
    path = app / "submission.json"
    submission = json.loads(path.read_text())
    witness = submission["result"]["divergent_witness"]
    witness["term"] = {
        "numerator_coefficients": [2],
        "denominator_coefficients": [0, 2, 0],
    }
    telescope = submission["result"]["convergent_witness"]["telescoping_identity"]
    submission["result"]["convergent_witness"]["telescoping_identity"] = list(
        reversed(telescope)
    )
    _fixtures._write_json(path, submission)
    assert _verifier._run_verifier(task, app, logs).reward == 1.0
