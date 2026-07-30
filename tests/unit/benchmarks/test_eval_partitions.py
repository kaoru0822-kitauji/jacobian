from __future__ import annotations

from collections import defaultdict

from benchmarks.jacobian_math_evals.catalog import load_sources
from benchmarks.jacobian_math_evals.compiler import (
    _family,
    _partition,
    _public_catalog_source_ids,
)
from benchmarks.jacobian_math_evals.handlers.registry import handled_source_ids
from benchmarks.jacobian_math_evals.manual_specs import manual_family_specs
from benchmarks.jacobian_math_evals.partitions import (
    source_family_key,
    source_family_split,
)


def test_related_source_families_never_cross_rl_splits() -> None:
    assignments: dict[str, set[str]] = defaultdict(set)
    for source in load_sources():
        assignments[source_family_key(source)].add(source_family_split(source).value)
    assert all(len(splits) == 1 for splits in assignments.values())


def test_known_duplicate_benchmark_families_share_partition() -> None:
    sources = load_sources()
    for family in ("minif2f", "putnambench", "proofnet", "leantree"):
        members = [source for source in sources if source_family_key(source) == family]
        assert len(members) >= 2
        assert len({source_family_split(source) for source in members}) == 1


def test_public_catalog_sources_are_excluded_from_scored_partitions() -> None:
    public_ids = _public_catalog_source_ids()
    handled = handled_source_ids()
    manual_sources = tuple(
        source
        for source in load_sources()
        if source.source_id not in handled and source.source_id not in public_ids
    )
    scored_ids = {
        source_id
        for spec in manual_family_specs(
            manual_sources,
            family_of=_family,
            partition_of=_partition,
        )
        for source_id in spec.source_ids
    }
    assert not public_ids.intersection(scored_ids)
