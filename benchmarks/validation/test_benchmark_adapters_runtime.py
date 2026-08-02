from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import check_benchmark_adapters
from tools.check_benchmark_adapters import _failures

ROOT = Path(__file__).parents[2]


@unittest.skipUnless(
    importlib.util.find_spec("harbor") is not None,
    "the pinned Harbor runtime owns this integration test",
)
class PinnedHarborAdapterDigestTests(unittest.TestCase):
    def test_adapter_output_uses_real_harbor_task_digest(self) -> None:
        from benchmarks.tooling.harbor_suite import task_digest

        source_task = (
            ROOT / "benchmarks" / "datasets" / "public-reproductions-v1" / "sat-small"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = root / "benchmarks" / "adapters" / "source"
            task = root / "benchmarks" / "datasets" / "suite" / "case"
            adapter.mkdir(parents=True)
            shutil.copytree(source_task, task)
            (adapter / "generate.py").write_text("", encoding="utf-8")
            (adapter / "check.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            digest = "sha256:" + task_digest(task).removeprefix("sha256:")
            lock = {
                "schema_version": "1",
                "adapter_id": "source",
                "source": {
                    "url": "https://example.invalid/data.json",
                    "revision": "v1",
                    "sha256": "sha256:" + "a" * 64,
                    "license": "MIT",
                    "redistribution": "allowed",
                },
                "selection": {
                    "included_rows": ["row-1"],
                    "excluded_rows": [],
                    "rule": "all",
                },
                "dependencies": {"converter": "==1.0.0"},
                "outputs": [
                    {
                        "task_id": "case",
                        "dataset": "suite",
                        "source_row": "row-1",
                        "task_digest": digest,
                        "oracle_evidence_digest": "sha256:" + "c" * 64,
                        "parity_evidence_digest": "sha256:" + "d" * 64,
                    }
                ],
            }
            (adapter / "source.lock.json").write_text(
                json.dumps(lock), encoding="utf-8"
            )

            with patch.object(check_benchmark_adapters, "ROOT", root):
                self.assertEqual(_failures(adapter), [])


if __name__ == "__main__":
    unittest.main()
