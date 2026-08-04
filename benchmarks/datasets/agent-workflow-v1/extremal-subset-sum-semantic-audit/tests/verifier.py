import itertools
import json
from pathlib import Path

from verifier_support import (
    evidence_list_is_bound,
    false_verified_claim,
    load_submission,
    resolve_evidence,
    strict_submission_contract,
)

W = Path("/app")
E = Path("/tests")
MAX_EVIDENCE_BYTES = 1_048_576
REQUIRED_DEFECTS = {
    "OUTER_PARAMETER_SHADOWED",
    "WHOLE_SET_SUM_REPLACES_SUBSET_SUM",
}


def _load_frozen_input():
    try:
        workspace = W / "input.json"
        frozen = E / "input.json"
        if workspace.is_symlink() or frozen.is_symlink():
            return {}
        frozen_bytes = frozen.read_bytes()
        if workspace.read_bytes() != frozen_bytes:
            return {}
        value = json.loads(frozen_bytes)
    except (OSError, ValueError, UnicodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _subsets(values):
    return [
        tuple(combination)
        for size in range(len(values) + 1)
        for combination in itertools.combinations(values, size)
    ]


def _canonical_set(value, universe):
    return bool(
        isinstance(value, list)
        and all(type(entry) is int for entry in value)
        and value == sorted(set(value))
        and set(value) <= set(universe)
    )


def _legacy_valid(candidate, target):
    return sum(candidate) != target


def _intended_valid(candidate, target):
    return all(sum(subset) != target for subset in _subsets(candidate))


def _extremum(universe, target, predicate):
    candidates = _subsets(universe)
    return max(
        len(candidate) for candidate in candidates if predicate(candidate, target)
    )


def _shadow_extremum(multiplier, target):
    return _extremum(list(range(1, multiplier * target + 1)), target, _legacy_valid)


def _shadowing_certified(value, source):
    if not isinstance(value, dict) or set(value) != {
        "target",
        "first_multiplier",
        "second_multiplier",
        "first_extremum",
        "second_extremum",
    }:
        return False
    target = source.get("shadow_instance", {}).get("target")
    allowed = source.get("shadow_instance", {}).get("allowed_cutoff_multipliers")
    first = value.get("first_multiplier")
    second = value.get("second_multiplier")
    if not all(type(item) is int for item in (first, second)):
        return False
    if (
        value.get("target") != target
        or first == second
        or first not in allowed
        or second not in allowed
    ):
        return False
    first_actual = _shadow_extremum(first, target)
    second_actual = _shadow_extremum(second, target)
    return bool(
        value.get("first_extremum") == first_actual
        and value.get("second_extremum") == second_actual
        and first_actual != second_actual
    )


def _predicate_certified(value, source):
    if not isinstance(value, dict) or set(value) != {
        "target",
        "universe",
        "legacy_extremum",
        "intended_extremum",
        "legacy_witness",
        "intended_witness",
        "blocking_subset",
    }:
        return False
    instance = source.get("predicate_instance", {})
    target = instance.get("target")
    universe = instance.get("universe")
    if value.get("target") != target or value.get("universe") != universe:
        return False
    legacy = value.get("legacy_witness")
    intended = value.get("intended_witness")
    blocker = value.get("blocking_subset")
    if not all(
        _canonical_set(candidate, universe) for candidate in (legacy, intended, blocker)
    ):
        return False
    legacy_max = _extremum(universe, target, _legacy_valid)
    intended_max = _extremum(universe, target, _intended_valid)
    return bool(
        value.get("legacy_extremum") == legacy_max
        and value.get("intended_extremum") == intended_max
        and len(legacy) == legacy_max
        and _legacy_valid(legacy, target)
        and len(intended) == intended_max
        and _intended_valid(intended, target)
        and set(blocker) <= set(legacy)
        and sum(blocker) == target
        and legacy_max > intended_max
    )


def _valid_audit(result, source):
    if not isinstance(result, dict) or set(result) != {
        "semantic_status",
        "defects",
        "shadowing_certificate",
        "predicate_certificate",
    }:
        return False
    defects = result.get("defects")
    return bool(
        source.get("audit_scope", {}).get("lean_compilation") is False
        and result.get("semantic_status") == "NOT_EQUIVALENT"
        and isinstance(defects, list)
        and len(defects) == 2
        and all(type(defect) is str for defect in defects)
        and set(defects) == REQUIRED_DEFECTS
        and _shadowing_certified(result.get("shadowing_certificate"), source)
        and _predicate_certified(result.get("predicate_certificate"), source)
    )


def _evidence_matches(evidence, result):
    if not evidence_list_is_bound(evidence, expected_path="evidence/answer.txt"):
        return False
    target = resolve_evidence(evidence[0], expected_path="evidence/answer.txt")
    if target is None:
        return False
    try:
        if target.stat().st_size > MAX_EVIDENCE_BYTES:
            return False
        text = target.read_text()
        marker = next(
            line.removeprefix("RESULT_JSON:").strip()
            for line in text.splitlines()
            if line.startswith("RESULT_JSON:")
        )
        prose = " ".join(
            line for line in text.splitlines() if not line.startswith("RESULT_JSON:")
        ).casefold()
        return bool(
            json.loads(marker) == result
            and "shadow" in prose
            and "subset" in prose
            and ("not assessed" in prose or "not verified" in prose)
        )
    except (OSError, StopIteration, UnicodeError, ValueError):
        return False


def main():
    submission = load_submission()
    source = _load_frozen_input()
    expected = json.loads((E / "expected.json").read_text())
    contract = strict_submission_contract(
        submission,
        task_id=expected["task_id"],
        conclusion=expected["conclusion"],
        verification_record="forbidden",
    )
    math_correct = bool(contract and _valid_audit(submission.get("result"), source))
    evidence_valid = bool(
        contract
        and _evidence_matches(submission.get("evidence"), submission.get("result"))
    )
    scope_correct = bool(
        contract and submission.get("scope") == expected["required_scope"]
    )
    assurance_correct = bool(
        contract
        and submission.get("claimed_assurance") == expected["maximum_assurance"]
    )
    limitations = submission.get("limitations", []) if contract else []
    limitations_correct = bool(
        isinstance(limitations, list)
        and any(
            isinstance(item, str)
            and "not assessed" in item.casefold()
            and "lean" in item.casefold()
            for item in limitations
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
