from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time

import pytest

from jacobian.bounded_process import (
    ProcessResourceLimits,
    bounded_process_cancellation,
    run_bounded_process,
)


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
                "'memory': resource.getrlimit(resource.RLIMIT_AS), "
                "'file': resource.getrlimit(resource.RLIMIT_FSIZE)}))"
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
            file_size_bytes=1024 * 1024,
        ),
    )

    assert completed.returncode == 0
    observed = json.loads(completed.stdout)
    assert observed == {
        "cpu": [2, 2],
        "memory": [address_space, address_space],
        "file": [1024 * 1024, 1024 * 1024],
    }


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


def test_cancellation_stops_worker_before_its_wall_time_budget() -> None:
    cancellation_event = threading.Event()
    timer = threading.Timer(0.2, cancellation_event.set)
    started = time.monotonic()
    timer.start()
    try:
        with bounded_process_cancellation(cancellation_event):
            completed = run_bounded_process(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                input_bytes=b"",
                timeout_seconds=20,
                environment=dict(os.environ),
                stdout_limit=4096,
                stderr_limit=4096,
            )
    finally:
        timer.cancel()

    assert completed.cancelled
    assert not completed.timed_out
    assert time.monotonic() - started < 3
