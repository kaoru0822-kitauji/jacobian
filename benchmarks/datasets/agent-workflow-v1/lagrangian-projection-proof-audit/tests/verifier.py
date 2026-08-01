import json
from fractions import Fraction
from pathlib import Path

from verifier_support import (
    evidence_list_is_bound,
    load_submission,
    resolve_evidence,
    strict_submission_contract,
)

W = Path("/app")
E = Path("/tests")


def canonical(value):
    if type(value) is not str:
        raise ValueError
    number = Fraction(value)
    expected = str(number.numerator)
    if number.denominator != 1:
        expected += f"/{number.denominator}"
    if value != expected or abs(number.numerator) > 50 or number.denominator > 20:
        raise ValueError
    return number


def matrix(value, rows, columns):
    if not isinstance(value, list) or len(value) != rows:
        raise ValueError
    result = []
    for row in value:
        if not isinstance(row, list) or len(row) != columns:
            raise ValueError
        result.append([canonical(item) for item in row])
    return result


def transpose(a):
    return [list(row) for row in zip(*a, strict=True)]


def multiply(a, b):
    bt = transpose(b)
    return [
        [sum(x * y for x, y in zip(row, col, strict=True)) for col in bt] for row in a
    ]


def add(a, b):
    return [
        [x + y for x, y in zip(arow, brow, strict=True)]
        for arow, brow in zip(a, b, strict=True)
    ]


def negate(a):
    return [[-value for value in row] for row in a]


def inverse_2x2(a):
    determinant = a[0][0] * a[1][1] - a[0][1] * a[1][0]
    if determinant == 0:
        raise ValueError
    return [
        [a[1][1] / determinant, -a[0][1] / determinant],
        [-a[1][0] / determinant, a[0][0] / determinant],
    ]


def nonzero(a):
    return any(value != 0 for row in a for value in row)


def certificate_valid(result, frozen):
    try:
        if (
            not isinstance(result, dict)
            or result.get("error_location") != "ARBITRARY_D_ASSUMED_LAGRANGIAN"
        ):
            return False
        d = matrix(result.get("D"), 4, 2)
        p = matrix(result.get("P"), 2, 2)
        q = matrix(result.get("Q"), 2, 2)
        submitted_w = matrix(result.get("W"), 4, 2)
        submitted_g = matrix(result.get("gram"), 2, 2)
        submitted_n = matrix(result.get("inverse_gram"), 2, 2)
        submitted_l = matrix(result.get("lagrangian_defect"), 2, 2)
        submitted_np = matrix(result.get("naive_P"), 2, 2)
        submitted_nq = matrix(result.get("naive_Q"), 2, 2)
        submitted_c1 = matrix(result.get("corrected_first_projection"), 2, 2)
        submitted_c2 = matrix(result.get("corrected_second_projection"), 2, 2)
        j = [
            [Fraction(value) for value in row]
            for row in frozen["frozen_claim"]["standard_symplectic_matrix"]
        ]

        dt = transpose(d)
        g = multiply(dt, d)
        n = inverse_2x2(g)
        lagrangian_defect = multiply(multiply(dt, j), d)
        jdnq = multiply(multiply(multiply(j, d), n), q)
        rebuilt_w = add(multiply(d, p), jdnq)
        naive_p = multiply(multiply(n, dt), rebuilt_w)
        naive_q = negate(multiply(multiply(dt, j), rebuilt_w))
        corrected_1 = add(
            p,
            multiply(multiply(multiply(n, lagrangian_defect), n), q),
        )
        corrected_2 = add(negate(multiply(lagrangian_defect, p)), q)
    except (ValueError, ZeroDivisionError, TypeError, KeyError):
        return False

    return bool(
        nonzero(lagrangian_defect)
        and nonzero(p)
        and nonzero(q)
        and naive_p != p
        and naive_q != q
        and rebuilt_w == submitted_w
        and g == submitted_g
        and n == submitted_n
        and lagrangian_defect == submitted_l
        and naive_p == submitted_np == corrected_1 == submitted_c1
        and naive_q == submitted_nq == corrected_2 == submitted_c2
    )


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
        for term in (
            "lagrangian defect",
            "naive projections",
            "corrected coupled identities",
        )
    )


def main():
    submission = load_submission()
    frozen = json.loads((W / "input.json").read_text())
    expected = json.loads((E / "expected.json").read_text())
    source = frozen.get("source") if isinstance(frozen, dict) else {}
    source_bound = bool(
        isinstance(source, dict)
        and source.get("revision") == "86c2b07ec545c0bd37feac10d4fc03675a85a6f6"
        and source.get("row_sha256")
        == "sha256:094bc10d13dd610b5f2a17f69203641a0cc05fbca5982df06d9e07c8d189a559"
        and source.get("license") == "CC 4.0"
    )
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
    correctness = bool(
        mathematical_contract and source_bound and certificate_valid(result, frozen)
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
        if not public_contract or not correctness or false_certification
        else 0.7 + 0.1 * evidence + 0.1 * scope + 0.1 * assurance
    )
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    Path("/logs/verifier/reward.json").write_text(
        json.dumps(
            {
                "correctness": float(correctness),
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
