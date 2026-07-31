from __future__ import annotations

import subprocess
import sys


def test_native_namespace_does_not_import_runtime_or_transport() -> None:
    forbidden = (
        "jacobian.runtime",
        "jacobian.mcp",
        "jacobian.operation_installation",
        "jacobian.providers",
    )
    script = "import jacobian.math, sys; print('\\n'.join(sys.modules))"
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    imported = set(completed.stdout.splitlines())
    assert not any(
        name == prefix or name.startswith(f"{prefix}.")
        for name in imported
        for prefix in forbidden
    )
