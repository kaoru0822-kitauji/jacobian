import itertools
import json
from pathlib import Path

from verifier_support import evidence_list_is_bound
from verifier_support import load_submission as load_strict_submission

W = Path("/app")
E = Path("/tests")
VERTICES = {str(index) for index in range(7)}
PAIRS = tuple(itertools.combinations(range(7), 2))


def _graph(value):
    if not isinstance(value, dict) or set(value) != {"vertices", "edges"}:
        return None
    vertices = (
        {str(item) for item in value["vertices"]}
        if isinstance(value["vertices"], list)
        else set()
    )
    if vertices != VERTICES or not isinstance(value["edges"], list):
        return None
    edges = set()
    for raw in value["edges"]:
        if not isinstance(raw, list) or len(raw) != 2:
            return None
        left, right = sorted(map(str, raw))
        if left == right or {left, right} - VERTICES or (left, right) in edges:
            return None
        edges.add((left, right))
    return {(int(left), int(right)) for left, right in edges}


def _adjacency(edges):
    adjacency = {vertex: set() for vertex in range(7)}
    for left, right in edges:
        adjacency[left].add(right)
        adjacency[right].add(left)
    return adjacency


def _is_connected(adjacency):
    seen, pending = set(), [0]
    while pending:
        vertex = pending.pop()
        if vertex in seen:
            continue
        seen.add(vertex)
        pending.extend(adjacency[vertex] - seen)
    return len(seen) == 7


def _is_triangle_free(adjacency):
    return not any(
        right in adjacency[left]
        for left, middle, right in itertools.combinations(range(7), 3)
        if middle in adjacency[left] and right in adjacency[middle]
    )


def _is_non_bipartite(adjacency):
    colors = {}
    for start in range(7):
        if start in colors:
            continue
        colors[start] = 0
        pending = [start]
        while pending:
            vertex = pending.pop()
            for neighbor in adjacency[vertex]:
                if neighbor in colors and colors[neighbor] == colors[vertex]:
                    return True
                if neighbor not in colors:
                    colors[neighbor] = 1 - colors[vertex]
                    pending.append(neighbor)
    return False


def _satisfies_constraints(edges):
    adjacency = _adjacency(edges)
    return bool(
        min(map(len, adjacency.values()), default=0) >= 2
        and _is_connected(adjacency)
        and _is_triangle_free(adjacency)
        and _is_non_bipartite(adjacency)
    )


def _canonical_label(edges):
    labels = []
    for permutation in itertools.permutations(range(7)):
        mapped = {
            tuple(sorted((permutation[left], permutation[right])))
            for left, right in edges
        }
        labels.append("".join("1" if pair in mapped else "0" for pair in PAIRS))
    return min(labels)


def _mathematics_ok(submission, expected):
    result = submission.get("result")
    if not isinstance(result, dict) or set(result) != {
        "class_count",
        "representatives",
    }:
        return False
    representatives = result["representatives"]
    if result["class_count"] != expected["class_count"] or not isinstance(
        representatives, list
    ):
        return False
    graphs = [_graph(value) for value in representatives]
    if any(graph is None for graph in graphs):
        return False
    if not all(_satisfies_constraints(graph) for graph in graphs):
        return False
    labels = sorted(_canonical_label(graph) for graph in graphs)
    return labels == expected["canonical_labels"]


def main():
    submission = load_strict_submission()
    expected = json.loads((E / "expected.json").read_text())
    required = {
        "task_id",
        "conclusion",
        "result",
        "claimed_assurance",
        "scope",
        "completeness",
        "evidence",
        "limitations",
    }
    valid = bool(
        isinstance(submission, dict)
        and set(submission) == required
        and submission["task_id"] == expected["task_id"]
        and submission["conclusion"] == expected["conclusion"]
        and isinstance(submission["claimed_assurance"], str)
        and isinstance(submission["scope"], str)
        and isinstance(submission["result"], dict)
        and isinstance(submission["evidence"], list)
        and isinstance(submission["limitations"], list)
        and submission["completeness"] == "COMPLETE"
    )
    math_correct = bool(valid and _mathematics_ok(submission, expected))
    evidence = bool(valid and evidence_list_is_bound(submission.get("evidence")))
    scope = bool(valid and submission["scope"] == expected["required_scope"])
    assurance = bool(
        valid and submission["claimed_assurance"] == expected["maximum_assurance"]
    )
    false_certification = bool(
        isinstance(submission, dict)
        and submission.get("claimed_assurance") == "VERIFIED"
    )
    correct = math_correct and not false_certification
    reward = (
        0.0 if not correct else 0.7 + 0.1 * evidence + 0.1 * scope + 0.1 * assurance
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
