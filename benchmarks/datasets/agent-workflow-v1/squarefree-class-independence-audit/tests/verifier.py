import json
from itertools import product
from pathlib import Path

from verifier_support import (
    evidence_list_is_bound,
    false_verified_claim,
    load_submission,
    resolve_evidence,
    strict_submission_contract,
)

WORKSPACE = Path("/app")
TESTS = Path("/tests")
CLASSIFICATION = {
    "class_key": "SQUAREFREE_KERNEL",
    "product_square_iff": "KERNELS_EQUAL",
    "pair_count_formula": "SUM_OF_SQUARED_CLASS_SIZES",
    "independent_selection": "ONE_ELEMENT_PER_DISTINCT_CLASS",
}
LIMITATION = "SQUAREFREE_KERNEL_LEMMA_NOT_FORMALLY_CHECKED"


def load_frozen() -> dict:
    try:
        app_input = WORKSPACE / "input.json"
        test_input = TESTS / "input.json"
        if (
            any(
                path.is_symlink()
                or not path.is_file()
                or path.stat().st_size > 1_048_576
                for path in (app_input, test_input)
            )
            or app_input.read_bytes() != test_input.read_bytes()
        ):
            return {}
        value = json.loads(test_input.read_text())
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def certificate_valid(result: object, frozen: dict) -> bool:
    if not isinstance(result, dict) or set(result) != {
        "ordered_pair_count",
        "classification",
        "modular_obstruction",
        "consequence",
    }:
        return False
    obstruction = result.get("modular_obstruction")
    if not isinstance(obstruction, dict) or set(obstruction) != {
        "modulus",
        "target_residue",
        "quadratic_residues",
        "maximum_squares_ruled_out",
    }:
        return False
    bounds = frozen.get("certificate_bounds", {})
    modulus = obstruction.get("modulus")
    residues = obstruction.get("quadratic_residues")
    if (
        type(modulus) is not int
        or not bounds.get("minimum_modulus", 2)
        <= modulus
        <= bounds.get("maximum_modulus", 0)
        or not isinstance(residues, list)
        or any(type(value) is not int for value in residues)
        or residues != sorted(set(residues))
    ):
        return False
    expected_residues = sorted({pow(value, 2, modulus) for value in range(modulus)})
    target = 2023 % modulus
    if residues != expected_residues or obstruction.get("target_residue") != target:
        return False
    if obstruction.get("maximum_squares_ruled_out") != 3:
        return False

    # Zero padding makes this one exhaustive check for representations by
    # zero, one, two, or three integer squares.
    if any(sum(values) % modulus == target for values in product(residues, repeat=3)):
        return False
    return bool(
        result.get("ordered_pair_count") == 2023
        and result.get("classification") == CLASSIFICATION
        and result.get("consequence") == "AT_LEAST_FOUR_SQUAREFREE_CLASSES"
    )


def evidence_valid(evidence: object, submission: dict) -> bool:
    if not isinstance(evidence, list) or len(evidence) != 1:
        return False
    expected_path = "evidence/independence-certificate.json"
    if not evidence_list_is_bound(evidence, expected_path=expected_path):
        return False
    path = resolve_evidence(evidence[0], expected_path=expected_path)
    if path is None:
        return False
    try:
        if path.stat().st_size > 1_048_576:
            return False
        payload = json.loads(path.read_text())
        return payload == {
            "schema_version": "1",
            "task_id": submission.get("task_id"),
            "result": submission.get("result"),
            "limitations": submission.get("limitations"),
        }
    except (OSError, UnicodeError, ValueError, RecursionError):
        return False


def main() -> None:
    submission = load_submission()
    data = submission if isinstance(submission, dict) else {}
    expected = json.loads((TESTS / "expected.json").read_text())
    contract = strict_submission_contract(
        submission,
        task_id=expected["task_id"],
        conclusion=expected["conclusion"],
        verification_record="forbidden",
    )
    math_correct = bool(
        contract and certificate_valid(data.get("result"), load_frozen())
    )
    evidence_correct = bool(math_correct and evidence_valid(data.get("evidence"), data))
    scope_correct = bool(contract and data.get("scope") == expected["required_scope"])
    assurance_correct = bool(
        contract and data.get("claimed_assurance") == expected["maximum_assurance"]
    )
    limitations_correct = bool(contract and data.get("limitations") == [LIMITATION])
    false_certification = false_verified_claim(
        submission, verification_record_bound=False
    )
    correct = bool(
        math_correct
        and evidence_correct
        and scope_correct
        and assurance_correct
        and limitations_correct
        and not false_certification
    )
    output = Path("/logs/verifier")
    output.mkdir(parents=True, exist_ok=True)
    (output / "reward.json").write_text(
        json.dumps(
            {
                "correctness": float(math_correct),
                "evidence_validity": float(evidence_correct),
                "scope_accuracy": float(scope_correct),
                "assurance_calibration": float(assurance_correct),
                "reward": float(correct),
                "false_certification": false_certification,
            }
        )
    )


if __name__ == "__main__":
    main()
