"""Composition-only helpers for agent benchmark fixtures.

The benchmark cases need to attach a complete runtime to a copied immutable
template.  Keep that operation next to the composition tier instead of
putting a hidden ``create_runtime`` seam in the generic ``tests.support``
package.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from jacobian.runtime import CheckerAuthorityMode, create_runtime
from jacobian.runtime.model import JacobianRuntime


def _runtime_from_template(
    tmp_path: Path,
    template: Path,
    *,
    name: str = "state",
    checker_authority: CheckerAuthorityMode = CheckerAuthorityMode.INSTALL_BUNDLED,
) -> tuple[Path, JacobianRuntime]:
    """Copy a complete template and attach one test-owned runtime."""

    state_dir = tmp_path / name
    shutil.copytree(template, state_dir)
    return state_dir, create_runtime(
        state_dir,
        checker_authority=checker_authority,
    )
