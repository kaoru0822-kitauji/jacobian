from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

import pytest
from tests.sharding import partition_items, shard_for_node, validate_shard


@dataclass
class _Item:
    nodeid: str


def test_node_shards_are_stable() -> None:
    nodeid = "tests/integration/test_kernel.py::test_create"

    assert shard_for_node(nodeid, 3) == 0
    assert shard_for_node(nodeid, 3) == shard_for_node(nodeid, 3)


def test_partitions_are_disjoint_and_complete() -> None:
    items = [
        _Item(f"tests/integration/test_{index}.py::test_case") for index in range(50)
    ]

    partitions = [
        partition_items(items, shard_count=3, shard_index=index)[0]
        for index in range(3)
    ]

    nodeids = [{item.nodeid for item in partition} for partition in partitions]
    assert set.union(*nodeids) == {item.nodeid for item in items}
    assert all(left.isdisjoint(right) for left, right in pairwise(nodeids))


@pytest.mark.parametrize(("shard_count", "shard_index"), [(0, 0), (3, -1), (3, 3)])
def test_invalid_shard_options_fail_collection(
    shard_count: int,
    shard_index: int,
) -> None:
    with pytest.raises(pytest.UsageError):
        validate_shard(shard_count, shard_index)
