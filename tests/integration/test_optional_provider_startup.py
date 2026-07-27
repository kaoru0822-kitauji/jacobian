from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_kernel_starts_and_exposes_unrelated_capabilities_without_flint(
    tmp_path: Path,
) -> None:
    script = """
import importlib
import sys
from pathlib import Path

real_import_module = importlib.import_module

def import_without_flint(name, package=None):
    if name == "flint":
        raise ImportError("python-flint intentionally unavailable")
    return real_import_module(name, package)

importlib.import_module = import_without_flint

from jacobian.kernel import JacobianKernel

kernel = JacobianKernel(Path(sys.argv[1]))
ids = {
    descriptor.capability_id
    for descriptor in kernel.capabilities.catalog().capabilities
}
assert "integer.compute.gcd" in ids
assert "probability.finite_distribution.raw_moment.compute" not in ids
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "kernel")],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stderr
