from __future__ import annotations

import subprocess
import sys


def test_smt_parser_state_guards_survive_optimized_python() -> None:
    script = """
from jacobian.contracts import smt as contract_smt
from jacobian_checkers import smt as checker_smt

if __debug__:
    raise SystemExit("optimized Python was not enabled")

for module, opener_name in (
    (contract_smt, "_open_smtlib_command"),
    (checker_smt, "_smtlib_open_paren"),
):
    setattr(module, opener_name, lambda depth, direct_atoms: (1, None))
    try:
        module._top_level_commands("(x")
    except ValueError as exc:
        if str(exc) != "SMT-LIB parser state is inconsistent":
            raise
    else:
        raise SystemExit(f"{module.__name__} accepted inconsistent parser state")
"""

    completed = subprocess.run(
        [sys.executable, "-O", "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
