import json
from pathlib import Path

from verifier_support import (
    evidence_list_is_bound,
    false_verified_claim,
    load_submission,
    resolve_evidence,
    strict_submission_contract,
)

E = Path("/tests")


def _valid_cover(result, bounds):
    n = result.get("modulus")
    step = result.get("subgroup_step")
    if (
        type(n) is not int
        or type(step) is not int
        or not bounds["minimum_modulus"] <= n <= bounds["maximum_modulus"]
    ):
        return False
    if (
        step < bounds["minimum_cosets"]
        or n % step
        or n // step < bounds["minimum_coset_size"]
    ):
        return False
    subgroup = list(range(0, n, step))
    representatives = list(range(step))
    cosets = [
        sorted((representative + value) % n for value in subgroup)
        for representative in representatives
    ]
    return bool(
        result.get("subgroup") == subgroup
        and result.get("representatives") == representatives
        and result.get("cosets") == cosets
        and len({value for coset in cosets for value in coset}) == n
        and sum(len(coset) for coset in cosets) == n
    )


def _valid_predicates(result):
    artifact = result.get("part_artifact")
    references = result.get("covering_part_references")
    cosets = result.get("cosets")
    pair = result.get("duplicate_indices")
    if (
        not isinstance(artifact, dict)
        or set(artifact) != {"id", "kind", "elements"}
        or artifact.get("id") != 0
        or artifact.get("kind") != "SUBGROUP"
        or artifact.get("elements") != result.get("subgroup")
        or not isinstance(references, list)
        or not isinstance(cosets, list)
        or len(references) != len(cosets)
        or any(type(reference) is not int or reference != 0 for reference in references)
    ):
        return False
    if (
        not isinstance(pair, list)
        or len(pair) != 2
        or not all(type(index) is int for index in pair)
    ):
        return False
    left, right = pair
    if not 0 <= left < right < len(references):
        return False
    unique_parts = list(dict.fromkeys(references))
    sizes = {part: len(cosets[references.index(part)]) for part in unique_parts}
    range_pairwise = all(
        sizes[a] != sizes[b]
        for i, a in enumerate(unique_parts)
        for b in unique_parts[i + 1 :]
    )
    indexed_pairwise = all(
        len(cosets[i]) != len(cosets[j])
        for i in range(len(cosets))
        for j in range(i + 1, len(cosets))
    )
    return bool(
        result.get("range_pairwise_truth") is range_pairwise is True
        and result.get("indexed_pairwise_truth") is indexed_pairwise is False
        and references[left] == references[right] == artifact["id"]
        and len(cosets[left]) == len(cosets[right])
    )


def _valid_result(result, source):
    required = {
        "modulus",
        "subgroup_step",
        "subgroup",
        "representatives",
        "cosets",
        "part_artifact",
        "covering_part_references",
        "range_pairwise_truth",
        "indexed_pairwise_truth",
        "duplicate_indices",
    }
    return bool(
        isinstance(result, dict)
        and set(result) == required
        and _valid_cover(result, source["bounds"])
        and _valid_predicates(result)
    )


def _evidence_valid(evidence):
    if not evidence_list_is_bound(evidence, expected_path="evidence/answer.txt"):
        return False
    target = resolve_evidence(evidence[0], expected_path="evidence/answer.txt")
    if target is None:
        return False
    try:
        text = target.read_text().casefold()
    except (OSError, UnicodeError):
        return False
    return all(term in text for term in ("exact cover", "set.range", "vacuously"))


def main():
    submission = load_submission()
    source = json.loads((E / "input.json").read_text())
    expected = json.loads((E / "expected.json").read_text())
    contract = strict_submission_contract(
        submission,
        task_id=expected["task_id"],
        conclusion=expected["conclusion"],
        verification_record="forbidden",
    )
    math_correct = bool(contract and _valid_result(submission.get("result"), source))
    evidence_valid = bool(contract and _evidence_valid(submission.get("evidence")))
    scope_correct = bool(
        contract and submission.get("scope") == expected["required_scope"]
    )
    assurance_correct = bool(
        contract
        and submission.get("claimed_assurance") == expected["maximum_assurance"]
    )
    limitations_correct = bool(
        contract
        and any(
            "open conjecture" in item.casefold()
            for item in submission.get("limitations", [])
            if isinstance(item, str)
        )
    )
    false_certification = false_verified_claim(
        submission, verification_record_bound=False
    )
    correct = bool(
        contract and math_correct and limitations_correct and not false_certification
    )
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
