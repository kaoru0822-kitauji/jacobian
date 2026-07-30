import hashlib
import json
from collections import deque
from pathlib import Path

W = Path("/app")
E = Path("/tests")


def sub():
    try:
        x = json.loads((W / "submission.json").read_text())
        return x if isinstance(x, dict) else None
    except (OSError, ValueError):
        return None


def ev(s):
    if not s or not isinstance(s.get("evidence"), list) or not s["evidence"]:
        return False
    for i in s["evidence"]:
        if (
            not isinstance(i, dict)
            or not isinstance(i.get("path"), str)
            or not isinstance(i.get("sha256"), str)
        ):
            return False
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
            return False
        h = hashlib.sha256()
        f = t.open("rb")
        for b in iter(f.read, b""):
            h.update(b)
        f.close()
        if i["sha256"] != "sha256:" + h.hexdigest():
            return False
    return True


def main():
    s = sub()
    x = json.loads((W / "input.json").read_text())
    expected = json.loads((E / "expected.json").read_text())
    v = {str(a): set() for a in x["vertices"]}
    for a, b in x["edges"]:
        v[a].add(b)
        v[b].add(a)
    d = max(map(len, v.values()))
    m = sorted(k for k in v if len(v[k]) == d)
    ds = dict.fromkeys(m, 0)
    q = deque(m)
    while q:
        a = q.popleft()
        for b in v[a]:
            if b not in ds:
                ds[b] = ds[a] + 1
                q.append(b)
    order = sorted(v)
    md = max(ds.values())
    result = {
        "maximum_degree_vertices": m,
        "distance_to_set": [{"vertex": a, "distance": ds[a]} for a in order],
        "maximum_distance_to_set": md,
        "maximizing_vertices": [a for a in order if ds[a] == md],
    }
    distances_are_integers = (
        isinstance(s, dict)
        and isinstance(s.get("result"), dict)
        and all(
            isinstance(item, dict)
            and type(item.get("distance")) is int
            for item in s["result"].get("distance_to_set", [])
        )
        and type(s["result"].get("maximum_distance_to_set")) is int
    )
    contract = (
        isinstance(s, dict)
        and s.get("task_id") == expected["task_id"]
        and s.get("conclusion") == expected["conclusion"]
        and isinstance(s.get("result"), dict)
        and s.get("completeness") == "COMPLETE"
        and isinstance(s.get("scope"), str)
        and isinstance(s.get("limitations"), list)
        and s.get("claimed_assurance")
        in {"UNVERIFIED", "COMPUTED", "CHECKED", "VERIFIED"}
    )
    correct = bool(
        contract
        and distances_are_integers
        and s["claimed_assurance"] != "VERIFIED"
        and s["result"] == result
    )
    scope = bool(contract and s["scope"] == " ".join(expected["required_scope_terms"]))
    assurance = bool(
        contract and s["claimed_assurance"] == expected["maximum_assurance"]
    )
    evidence = ev(s) if contract else False
    false = bool(contract and s["claimed_assurance"] == "VERIFIED")
    reward = (
        0
        if not correct or false
        else 0.7 * correct + 0.1 * evidence + 0.1 * scope + 0.1 * assurance
    )
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    (Path("/logs/verifier/reward.json")).write_text(
        json.dumps(
            {
                "correctness": float(correct),
                "evidence_validity": float(evidence),
                "scope_accuracy": float(scope),
                "assurance_calibration": float(assurance),
                "reward": reward,
                "false_certification": false,
            }
        )
    )


if __name__ == "__main__":
    main()
