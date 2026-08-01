import json
from pathlib import Path

from verifier_support import (
    evidence_list_is_bound,
    load_submission,
    resolve_evidence,
    strict_submission_contract,
)

W = Path("/app")
E = Path("/tests")

RULES = {
    "workshop-equation-status": {
        "classification": "PROBLEM_LISTED_STATUS_UNSUPPORTED",
        "required": {"W2007"},
        "unsupported": {"NEGATIVE_SEARCH_PROVES_CURRENT_STATUS"},
    },
    "vanishing-conjecture-status": {
        "classification": "HISTORICALLY_OPEN_CURRENT_STATUS_NOT_ESTABLISHED",
        "required": {"Z2004", "Z2008"},
        "unsupported": {"HISTORICAL_OPENNESS_PROVES_2026_OPENNESS"},
    },
    "binomial-equation-resolution": {
        "classification": "RESOLVED_BY_CITED_WORK",
        "required": {"BMSS2019"},
        "unsupported": set(),
    },
    "lebesgue-nagell-progress": {
        "classification": "PARTIAL_PROGRESS_NO_FULL_RESOLUTION",
        "required": {"B2004", "KP2025"},
        "unsupported": set(),
    },
}


def citation_semantics_are_present(case):
    texts = {item["id"]: item["text"].lower() for item in case["citations"]}
    cid = case["case_id"]
    if cid == "workshop-equation-status":
        return "problem 1" in texts.get("W2007", "")
    if cid == "vanishing-conjecture-status":
        return (
            "open problems" in texts.get("Z2008", "")
            and max(item["year"] for item in case["citations"]) < 2026
        )
    if cid == "binomial-equation-resolution":
        return "all integer solutions" in texts.get(
            "BMSS2019", ""
        ) and "not including" in texts.get("SW1999", "")
    if cid == "lebesgue-nagell-progress":
        return "does not claim a complete resolution" in texts.get(
            "KP2025", ""
        ) and "ranges" in texts.get("B2004", "")
    return False


def cases_valid(result, frozen):
    submitted = result.get("cases")
    if not isinstance(submitted, list) or len(submitted) != len(RULES):
        return False
    frozen_by_id = {case["case_id"]: case for case in frozen["cases"]}
    seen = set()
    for item in submitted:
        if not isinstance(item, dict) or set(item) != {
            "case_id",
            "classification",
            "selected_evidence_ids",
            "unsupported_inferences",
        }:
            return False
        cid = item.get("case_id")
        if cid in seen or cid not in RULES:
            return False
        seen.add(cid)
        rule = RULES[cid]
        selected = item.get("selected_evidence_ids")
        unsupported = item.get("unsupported_inferences")
        if (
            not isinstance(selected, list)
            or any(type(value) is not str for value in selected)
            or len(selected) != len(set(selected))
            or not isinstance(unsupported, list)
            or any(type(value) is not str for value in unsupported)
            or len(unsupported) != len(set(unsupported))
        ):
            return False
        available = {citation["id"] for citation in frozen_by_id[cid]["citations"]}
        if (
            item.get("classification") != rule["classification"]
            or not rule["required"].issubset(set(selected))
            or not set(selected).issubset(available)
            or set(unsupported) != rule["unsupported"]
            or not citation_semantics_are_present(frozen_by_id[cid])
        ):
            return False
    return seen == set(RULES)


def evidence_valid(evidence):
    if not evidence_list_is_bound(evidence):
        return False
    target = resolve_evidence(evidence[0], expected_path="evidence/answer.txt")
    if target is None:
        return False
    try:
        text = target.read_text().lower()
    except OSError:
        return False
    return all(
        term in text
        for term in ("resolution", "partial-progress", "historical", "problem listing")
    )


def main():
    submission = load_submission()
    frozen = json.loads((W / "input.json").read_text())
    expected = json.loads((E / "expected.json").read_text())
    mathematical_contract = strict_submission_contract(
        submission,
        task_id=expected["task_id"],
        conclusion=expected["conclusion"],
        verification_record="optional",
    )
    public_contract = strict_submission_contract(
        submission,
        task_id=expected["task_id"],
        conclusion=expected["conclusion"],
        allowed_assurances=frozenset({"UNVERIFIED", "COMPUTED", "CHECKED"}),
        verification_record="forbidden",
    )
    result = submission.get("result") if isinstance(submission, dict) else {}
    math_correct = bool(
        mathematical_contract
        and isinstance(result, dict)
        and cases_valid(result, frozen)
    )
    evidence = bool(
        mathematical_contract and evidence_valid(submission.get("evidence"))
    )
    scope = bool(
        mathematical_contract and submission.get("scope") == expected["required_scope"]
    )
    assurance = bool(
        mathematical_contract
        and submission.get("claimed_assurance") == expected["maximum_assurance"]
    )
    false_certification = bool(
        isinstance(submission, dict)
        and submission.get("claimed_assurance") == "VERIFIED"
    )
    reward = (
        0.0
        if not public_contract or not math_correct or false_certification
        else (0.7 + 0.1 * evidence + 0.1 * scope + 0.1 * assurance)
    )
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    Path("/logs/verifier/reward.json").write_text(
        json.dumps(
            {
                "correctness": float(math_correct),
                "evidence_validity": float(evidence),
                "scope_accuracy": float(scope),
                "assurance_calibration": float(assurance),
                "reward": reward,
                "false_certification": false_certification,
            }
        )
    )


if __name__ == "__main__":
    main()
