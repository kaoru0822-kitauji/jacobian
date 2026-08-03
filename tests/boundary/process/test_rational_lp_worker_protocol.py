from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "payload",
    (
        '{"program":{},"unexpected":true}',
        (
            '{"program":{"variables":["x"],'
            '"objective":[{"num":"01","den":"1"}],'
            '"coefficients":[[{"num":"1","den":"1"}]],'
            '"rhs":[{"num":"1","den":"1"}]},"wall_seconds":10}'
        ),
        '{"program":{},"program":{},"wall_seconds":10}',
    ),
)
def test_rational_lp_worker_rejects_malformed_protocol(payload: str) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "jacobian.domains.optimization.worker",
        ],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr == "invalid rational optimization worker request\n"
