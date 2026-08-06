"""Inventory ratchet: leaky weighted-reward formulas must not grow.

The historical leaky template soft-weights evidence (and other mandatory
dimensions) into aggregate reward so invalid digests still score ~0.9. Phase 1
migrations shrink this inventory; this module fails if any *new* task reintroduces
the pattern outside the frozen known set.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASETS = ROOT / "benchmarks" / "datasets"
TEMPLATE_SUPPORT = (
    ROOT / "benchmarks" / "templates" / "task" / "tests" / "verifier_support.py"
)
TEMPLATE_VERIFIER = ROOT / "benchmarks" / "templates" / "task" / "tests" / "verifier.py"

# Soft-weighted aggregate that does not hard-gate evidence (RC1 / A1).
_LEAKY_WEIGHTED = re.compile(
    r"0\.7\s*\*\s*(?:correct|math_correct|float\(\s*correct)"
    r".{0,120}?"
    r"0\.1\s*\*\s*(?:good|evidence)",
    re.DOTALL,
)
_LEAKY_WEIGHTED_ALT = re.compile(
    r"0\.7\s*\*\s*(?:correct|math_correct).{0,200}?0\.1\s*\*\s*(?:good|evidence_ok|evidence_valid)",
    re.DOTALL,
)

# Frozen inventory at the start of the fail-closed reward migration.
# Remove entries only when the task migrates to aggregate_reward / min-gate.
# Do not add entries without an explicit migration exception review.
# Empty after Phase 1 migration: no verifier may reintroduce the leaky pattern.
KNOWN_LEAKY_REWARD_VERIFIERS: frozenset[str] = frozenset()

_REQUIRED_TEMPLATE_EXPORTS = frozenset(
    {
        "aggregate_reward",
        "evidence_list_is_bound",
        "load_submission",
        "strict_submission_contract",
    }
)


def _is_leaky(text: str) -> bool:
    return bool(_LEAKY_WEIGHTED.search(text) or _LEAKY_WEIGHTED_ALT.search(text))


def _leaky_task_ids() -> set[str]:
    found: set[str] = set()
    for path in sorted(DATASETS.rglob("tests/verifier.py")):
        relative = path.relative_to(DATASETS)
        # datasets/<dataset>/<task>/tests/verifier.py
        if len(relative.parts) < 4:
            continue
        task_id = f"{relative.parts[0]}/{relative.parts[1]}"
        if _is_leaky(path.read_text(encoding="utf-8", errors="replace")):
            found.add(task_id)
    return found


def test_template_support_exports_fail_closed_aggregate_helper() -> None:
    text = TEMPLATE_SUPPORT.read_text(encoding="utf-8")
    assert "def aggregate_reward(" in text
    assert not _is_leaky(text)
    for name in _REQUIRED_TEMPLATE_EXPORTS:
        assert f'"{name}"' in text or f"'{name}'" in text
    # Template verifier remains a stub; it must not ship the leaky formula.
    assert not _is_leaky(TEMPLATE_VERIFIER.read_text(encoding="utf-8"))


def test_leaky_reward_inventory_does_not_grow() -> None:
    found = _leaky_task_ids()
    unexpected = sorted(found - KNOWN_LEAKY_REWARD_VERIFIERS)
    missing = sorted(KNOWN_LEAKY_REWARD_VERIFIERS - found)
    assert not unexpected, (
        "New leaky 0.7/0.1 reward formulas appeared; migrate them to "
        f"aggregate_reward or get an explicit review exception: {unexpected}"
    )
    # Allow inventory shrinkage as tasks migrate; fail only if the frozen list
    # still claims a task that no longer matches (stale inventory).
    assert not missing, (
        "Known leaky inventory is stale (tasks already migrated). Remove them "
        f"from KNOWN_LEAKY_REWARD_VERIFIERS: {missing}"
    )
