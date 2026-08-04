import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / "benchmarks/datasets/agent-workflow-v1/grid-independent-set-transfer"


def load_verifier():
    sys.path.insert(0, str(TASK / "tests"))
    spec = importlib.util.spec_from_file_location(
        "grid_transfer_verifier", TASK / "tests/verifier.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_independent_transfer_derivation():
    result = load_verifier().derive()
    assert [case["independent_set_count"] for case in result["cases"]] == [
        7,
        63,
        1234,
        55447,
    ]
    assert result["total"] == 56751


def test_state_and_transition_traces_are_material():
    result = load_verifier().derive()
    assert [len(case["valid_row_masks"]) for case in result["cases"]] == [3, 5, 8, 13]
    assert [case["compatible_pair_count"] for case in result["cases"]] == [
        7,
        17,
        41,
        99,
    ]


def test_corrupt_intermediate_layer_is_rejected():
    verifier = load_verifier()
    result = verifier.derive()
    result["cases"][-1]["layer_totals"][2] += 1
    assert not verifier.matches(result)


def test_contract_has_no_verified_upgrade():
    schema = json.loads((TASK / "environment/submission_schema.json").read_text())
    assert schema["properties"]["claimed_assurance"] == {"const": "COMPUTED"}
