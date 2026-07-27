from __future__ import annotations

import json
import os
import shutil
import sys

import pytest

from jacobian.bounded_process import ProcessResourceLimits, run_bounded_process


@pytest.mark.skipif(
    os.name != "posix" or shutil.which("prlimit") is None,
    reason="pre-exec resource limits require util-linux prlimit",
)
def test_target_observes_resource_limits_at_startup() -> None:
    address_space = 512 * 1024 * 1024
    completed = run_bounded_process(
        [
            sys.executable,
            "-c",
            (
                "import json, resource; "
                "print(json.dumps({'cpu': resource.getrlimit(resource.RLIMIT_CPU), "
                "'memory': resource.getrlimit(resource.RLIMIT_AS)}))"
            ),
        ],
        input_bytes=b"",
        timeout_seconds=5,
        environment=dict(os.environ),
        stdout_limit=4096,
        stderr_limit=4096,
        resource_limits=ProcessResourceLimits(
            cpu_seconds=2,
            address_space_bytes=address_space,
        ),
    )

    assert completed.returncode == 0
    observed = json.loads(completed.stdout)
    assert observed == {"cpu": [2, 2], "memory": [address_space, address_space]}


@pytest.mark.skipif(
    os.name != "posix" or shutil.which("prlimit") is None,
    reason="pre-exec resource limits require util-linux prlimit",
)
def test_address_space_exhaustion_stops_worker() -> None:
    completed = run_bounded_process(
        [sys.executable, "-c", "bytearray(512 * 1024 * 1024)"],
        input_bytes=b"",
        timeout_seconds=5,
        environment=dict(os.environ),
        stdout_limit=4096,
        stderr_limit=4096,
        resource_limits=ProcessResourceLimits(
            cpu_seconds=2,
            address_space_bytes=256 * 1024 * 1024,
        ),
    )

    assert completed.returncode != 0
    assert not completed.timed_out
