from __future__ import annotations

from pathlib import Path

from benchmarks.jacobian_math_evals.probe_reporting import probe_error_message


def test_probe_error_message_redacts_local_cache_root(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    snapshot = cache_dir / "src-example" / "snapshot.json"

    message = probe_error_message(
        FileNotFoundError(f"snapshot missing: {snapshot}"),
        cache_dir=cache_dir,
    )

    assert message == "snapshot missing: <cache-dir>/src-example/snapshot.json"
    assert str(tmp_path) not in message
