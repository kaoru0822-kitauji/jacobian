from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_runtime_rejects_a_base_installation_without_flint(
    tmp_path: Path,
) -> None:
    script = """
import importlib.abc
import sys
from pathlib import Path

class BlockFlint(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "flint" or fullname.startswith("flint."):
            raise ImportError("python-flint intentionally unavailable")
        return None

sys.meta_path.insert(0, BlockFlint())

from jacobian.runtime import create_runtime

create_runtime(Path(sys.argv[1]))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "runtime")],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.returncode != 0
    assert "required Python provider python-flint is unavailable" in completed.stderr


def test_runtime_rejects_a_base_installation_without_z3(
    tmp_path: Path,
) -> None:
    script = """
import importlib.abc
import sys
from pathlib import Path

class BlockZ3(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "z3" or fullname.startswith("z3."):
            raise ImportError("z3-solver intentionally unavailable")
        return None

sys.meta_path.insert(0, BlockZ3())

from jacobian.runtime import create_runtime

create_runtime(Path(sys.argv[1]))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "runtime")],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.returncode != 0
    assert "required Python provider jacobian.z3 is unavailable" in completed.stderr
