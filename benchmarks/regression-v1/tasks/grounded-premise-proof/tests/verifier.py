import json
from pathlib import Path

from verifier_support import (
    evidence_list_is_bound,
    false_verified_claim,
    load_submission,
    strict_submission_contract,
)

W = Path("/app")
E = Path("/tests")

REQUIRED_PREMISES = {
    "subgroup_of_abelian_is_normal",
    "coset_product_definition",
}
RULES = {
    "APPLY_NORMALITY_PREMISE": (
        {"G_ABELIAN", "N_SUBGROUP"},
        "N_NORMAL",
        "subgroup_of_abelian_is_normal",
    ),
    "FORM_QUOTIENT": ({"N_NORMAL"}, "QUOTIENT_EXISTS", None),
    "EXPAND_XY_COSET_PRODUCT": (
        {"QUOTIENT_EXISTS", "X_EQ_xN", "Y_EQ_yN"},
        "XY_EQ_xyN",
        "coset_product_definition",
    ),
    "COMMUTE_REPRESENTATIVES": (
        {"G_ABELIAN", "XY_EQ_xyN"},
        "XY_EQ_yxN",
        None,
    ),
    "COLLAPSE_YX_COSET_PRODUCT": (
        {"QUOTIENT_EXISTS", "Y_EQ_yN", "X_EQ_xN"},
        "yxN_EQ_YX",
        "coset_product_definition",
    ),
    "CHAIN_EQUALITIES": (
        {"XY_EQ_yxN", "yxN_EQ_YX"},
        "XY_EQ_YX",
        None,
    ),
}


def _replay_proof(result, source):
    if not isinstance(result, dict) or set(result) != {
        "selected_premises",
        "proof_steps",
        "target_fact",
    }:
        return False
    selected = result["selected_premises"]
    if (
        not isinstance(selected, list)
        or not all(type(premise) is str for premise in selected)
        or len(selected) != len(REQUIRED_PREMISES)
        or set(selected) != REQUIRED_PREMISES
    ):
        return False
    available_premises = {
        premise["id"] for premise in source.get("candidate_premises", [])
    }
    if not set(selected) <= available_premises:
        return False

    facts = set(source.get("initial_facts", []))
    used_premises = set()
    step_ids = set()
    steps = result["proof_steps"]
    if not isinstance(steps, list):
        return False
    for step in steps:
        if not isinstance(step, dict) or set(step) != {
            "id",
            "rule",
            "inputs",
            "output",
        }:
            return False
        if (
            type(step["id"]) is not str
            or type(step["rule"]) is not str
            or type(step["output"]) is not str
        ):
            return False
        if step["id"] in step_ids or step["rule"] not in RULES:
            return False
        inputs = step["inputs"]
        if (
            not isinstance(inputs, list)
            or not all(type(value) is str for value in inputs)
            or len(inputs) != len(set(inputs))
            or not set(inputs) <= facts
        ):
            return False
        required_inputs, output, premise = RULES[step["rule"]]
        if set(inputs) != required_inputs or step["output"] != output:
            return False
        if output in facts:
            return False
        if premise is not None:
            if premise not in selected:
                return False
            used_premises.add(premise)
        step_ids.add(step["id"])
        facts.add(output)

    target = source.get("target_fact")
    return bool(
        type(result["target_fact"]) is str
        and result["target_fact"] == target
        and target in facts
        and used_premises == REQUIRED_PREMISES
    )


def main():
    submission = load_submission()
    source = json.loads((W / "input.json").read_text())
    expected = json.loads((E / "expected.json").read_text())
    contract = strict_submission_contract(
        submission,
        task_id=expected["task_id"],
        conclusion=expected["conclusion"],
        verification_record="forbidden",
    )
    math_correct = bool(contract and _replay_proof(submission.get("result"), source))
    evidence_valid = bool(
        contract
        and evidence_list_is_bound(
            submission.get("evidence"), expected_path="evidence/answer.txt"
        )
    )
    scope_correct = bool(
        contract and submission.get("scope") == expected["required_scope"]
    )
    assurance_correct = bool(
        contract
        and submission.get("claimed_assurance") == expected["maximum_assurance"]
    )
    false_certification = false_verified_claim(
        submission, verification_record_bound=False
    )
    correct = bool(contract and math_correct and not false_certification)
    reward = (
        0
        if not correct
        else 0.7 + 0.1 * evidence_valid + 0.1 * scope_correct + 0.1 * assurance_correct
    )

    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    (Path("/logs/verifier/reward.json")).write_text(
        json.dumps(
            {
                "correctness": float(math_correct),
                "evidence_validity": float(evidence_valid),
                "scope_accuracy": float(scope_correct),
                "assurance_calibration": float(assurance_correct),
                "reward": reward,
                "false_certification": false_certification,
            }
        )
    )


if __name__ == "__main__":
    main()
