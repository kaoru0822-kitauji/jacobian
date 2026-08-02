from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

from verifier_support import (
    evidence_list_is_bound,
    false_verified_claim,
    load_submission,
    resolve_evidence,
    strict_submission_contract,
)

WORKSPACE = Path("/app")
TESTS = Path("/tests")
ORDER = 7
VERTICES = frozenset(range(ORDER))
PAIRS = tuple(itertools.combinations(range(ORDER), 2))
PAIR_INDEX = {pair: index for index, pair in enumerate(PAIRS)}
LIMITATIONS = ["ORDER_SEVEN_SCOPE_ONLY"]


def _input_is_frozen() -> bool:
    try:
        workspace_input = WORKSPACE / "input.json"
        verifier_input = TESTS / "agent-workflow-v1-graph-atlas-enumeration-input.json"
        return bool(
            all(
                path.is_file()
                and not path.is_symlink()
                and path.stat().st_size <= 1_048_576
                for path in (workspace_input, verifier_input)
            )
            and workspace_input.read_bytes() == verifier_input.read_bytes()
        )
    except OSError:
        return False


def _graph_mask(value: object) -> int | None:
    if not isinstance(value, dict) or set(value) != {"vertices", "edges"}:
        return None
    raw_vertices = value.get("vertices")
    raw_edges = value.get("edges")
    if not isinstance(raw_vertices, list) or not isinstance(raw_edges, list):
        return None
    try:
        vertices = {int(item) for item in raw_vertices if type(item) in {str, int}}
    except ValueError:
        return None
    if len(raw_vertices) != ORDER or vertices != VERTICES:
        return None
    mask = 0
    for raw_edge in raw_edges:
        if not isinstance(raw_edge, list) or len(raw_edge) != 2:
            return None
        try:
            left, right = (int(item) for item in raw_edge if type(item) in {str, int})
        except (ValueError, TypeError):
            return None
        if left == right or left not in VERTICES or right not in VERTICES:
            return None
        index = PAIR_INDEX[tuple(sorted((left, right)))]
        bit = 1 << index
        if mask & bit:
            return None
        mask |= bit
    return mask


def _adjacency(mask: int) -> list[int]:
    adjacency = [0] * ORDER
    remaining = mask
    while remaining:
        bit = remaining & -remaining
        left, right = PAIRS[bit.bit_length() - 1]
        adjacency[left] |= 1 << right
        adjacency[right] |= 1 << left
        remaining ^= bit
    return adjacency


def _is_connected(adjacency: list[int]) -> bool:
    seen = 1
    frontier = 1
    while frontier:
        neighbors = 0
        remaining = frontier
        while remaining:
            bit = remaining & -remaining
            neighbors |= adjacency[bit.bit_length() - 1]
            remaining ^= bit
        frontier = neighbors & ~seen
        seen |= frontier
    return seen == (1 << ORDER) - 1


def _is_triangle_free(adjacency: list[int]) -> bool:
    for vertex, neighbors in enumerate(adjacency):
        remaining = neighbors
        while remaining:
            bit = remaining & -remaining
            neighbor = bit.bit_length() - 1
            if adjacency[neighbor] & neighbors & ~(1 << vertex):
                return False
            remaining ^= bit
    return True


def _is_non_bipartite(adjacency: list[int]) -> bool:
    colors = [-1] * ORDER
    colors[0] = 0
    pending = [0]
    while pending:
        vertex = pending.pop()
        remaining = adjacency[vertex]
        while remaining:
            bit = remaining & -remaining
            neighbor = bit.bit_length() - 1
            if colors[neighbor] == colors[vertex]:
                return True
            if colors[neighbor] == -1:
                colors[neighbor] = 1 - colors[vertex]
                pending.append(neighbor)
            remaining ^= bit
    return False


def _satisfies_constraints(mask: int) -> bool:
    edge_count = mask.bit_count()
    if edge_count < ORDER or edge_count > 12:
        return False
    adjacency = _adjacency(mask)
    return bool(
        all(neighbors.bit_count() >= 2 for neighbors in adjacency)
        and _is_connected(adjacency)
        and _is_triangle_free(adjacency)
        and _is_non_bipartite(adjacency)
    )


def _orbit(mask: int) -> set[int]:
    edges = [PAIRS[index] for index in range(len(PAIRS)) if mask & (1 << index)]
    orbit: set[int] = set()
    for permutation in itertools.permutations(range(ORDER)):
        relabelled = 0
        for left, right in edges:
            pair = tuple(sorted((permutation[left], permutation[right])))
            relabelled |= 1 << PAIR_INDEX[pair]
        orbit.add(relabelled)
    return orbit


def _complete_enumeration(result: object) -> bool:
    if not isinstance(result, dict) or set(result) != {
        "class_count",
        "representatives",
    }:
        return False
    representatives = result.get("representatives")
    if (
        type(result.get("class_count")) is not int
        or not isinstance(representatives, list)
        or result["class_count"] != len(representatives)
    ):
        return False
    masks = [_graph_mask(value) for value in representatives]
    if any(mask is None for mask in masks):
        return False

    covered: set[int] = set()
    for raw_mask in masks:
        assert raw_mask is not None
        if not _satisfies_constraints(raw_mask):
            return False
        orbit = _orbit(raw_mask)
        if covered & orbit:
            return False
        covered.update(orbit)

    return all(
        not _satisfies_constraints(mask) or mask in covered
        for mask in range(1 << len(PAIRS))
    )


def _evidence_is_valid(evidence: object, submission: dict[str, Any]) -> bool:
    expected_path = "evidence/enumeration-certificate.json"
    if not isinstance(evidence, list) or len(evidence) != 1:
        return False
    if not evidence_list_is_bound(evidence, expected_path=expected_path):
        return False
    target = resolve_evidence(evidence[0], expected_path=expected_path)
    if target is None:
        return False
    try:
        if target.stat().st_size > 2_097_152:
            return False
        payload = json.loads(target.read_text())
    except (OSError, UnicodeError, ValueError, RecursionError):
        return False
    return payload == {
        "schema_version": "1",
        "task_id": submission.get("task_id"),
        "result": submission.get("result"),
        "limitations": submission.get("limitations"),
    }


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
    input_integrity = _input_is_frozen()
    math_correct = bool(contract and _complete_enumeration(data.get("result")))
    evidence_valid = bool(
        math_correct and _evidence_is_valid(data.get("evidence"), data)
    )
    scope_correct = bool(contract and data.get("scope") == expected["required_scope"])
    assurance_correct = bool(
        contract and data.get("claimed_assurance") == expected["maximum_assurance"]
    )
    limitations_correct = bool(contract and data.get("limitations") == LIMITATIONS)
    false_certification = false_verified_claim(
        submission, verification_record_bound=False
    )
    passed = bool(
        math_correct
        and input_integrity
        and evidence_valid
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
                "evidence_validity": float(evidence_valid),
                "scope_accuracy": float(scope_correct),
                "assurance_calibration": float(assurance_correct),
                "input_integrity": float(input_integrity),
                "reward": float(passed),
                "false_certification": false_certification,
            }
        )
    )


if __name__ == "__main__":
    main()
