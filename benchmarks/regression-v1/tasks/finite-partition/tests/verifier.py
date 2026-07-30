import hashlib
import json
from pathlib import Path

W = Path("/app")
E = Path("/tests")


def main():
    try:
        s = json.loads((W / "submission.json").read_text())
    except (OSError, ValueError):
        s = None
    x = json.loads((W / "input.json").read_text())
    e = json.loads((E / "expected.json").read_text())
    contract = (
        isinstance(s, dict)
        and all(
            k in s
            for k in (
                "task_id",
                "conclusion",
                "result",
                "claimed_assurance",
                "scope",
                "completeness",
                "evidence",
                "limitations",
            )
        )
        and s.get("task_id") == e["task_id"]
        and s.get("conclusion") == "TRUE"
        and s.get("completeness") == "COMPLETE"
        and isinstance(s.get("result"), dict)
        and isinstance(s.get("scope"), str)
        and isinstance(s.get("limitations"), list)
        and s.get("claimed_assurance")
        in {"UNVERIFIED", "COMPUTED", "CHECKED", "VERIFIED"}
    )
    groups = s.get("result", {}).get("cases", []) if contract else []
    members = []
    valid = isinstance(groups, list) and len(groups) == 3
    for g in groups:
        valid = (
            valid
            and isinstance(g, dict)
            and isinstance(g.get("name"), str)
            and isinstance(g.get("members"), list)
        )
        if valid:
            members.extend(g["members"])
    wanted = set(x["universe"])
    actual = {}
    if valid:
        try:
            for g in groups:
                if g["name"] in actual:
                    valid = False
                    break
                actual[g["name"]] = frozenset(g["members"])
        except TypeError:
            valid = False
    expected = {
        f"residue-{r}": frozenset(n for n in x["universe"] if int(n) % 3 == r)
        for r in range(3)
    }
    correct = bool(
        contract
        and s["claimed_assurance"] != "VERIFIED"
        and all(type(member) is str for member in members)
        and len(members) == len(set(members))
        and set(members) == wanted
        and actual == expected
    )
    good_evidence = False
    if contract and isinstance(s["evidence"], list) and s["evidence"]:
        good_evidence = True
        for i in s["evidence"]:
            if (
                not isinstance(i, dict)
                or not isinstance(i.get("path"), str)
                or not isinstance(i.get("sha256"), str)
            ):
                good_evidence = False
                continue
            p = Path(i["path"])
            t = (W / p).resolve()
            if (
                p.is_absolute()
                or p != Path("evidence/answer.txt")
                or ".." in p.parts
                or (W / p).is_symlink()
                or not t.is_relative_to(W.resolve())
                or not t.is_file()
            ):
                good_evidence = False
                continue
            h = hashlib.sha256(t.read_bytes()).hexdigest()
            good_evidence &= i.get("sha256") == "sha256:" + h
    scope = bool(contract and s["scope"] == " ".join(e["required_scope_terms"]))
    assurance = bool(contract and s["claimed_assurance"] == e["maximum_assurance"])
    false = bool(contract and s["claimed_assurance"] == "VERIFIED")
    reward = (
        0
        if not correct or false
        else 0.7 * correct + 0.1 * good_evidence + 0.1 * scope + 0.1 * assurance
    )
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    (Path("/logs/verifier/reward.json")).write_text(
        json.dumps(
            {
                "correctness": float(correct),
                "evidence_validity": float(good_evidence),
                "scope_accuracy": float(scope),
                "assurance_calibration": float(assurance),
                "reward": reward,
                "false_certification": false,
            }
        )
    )


if __name__ == "__main__":
    main()
