"""Repeatable local measurements for exact installed provider identities."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from jacobian.contracts.capabilities import CapabilityProviderRuntime
from jacobian.contracts.provider_measurements import (
    ProviderMeasurement,
    ProviderMeasurementSample,
    ProviderMeasurementStatus,
)

_PROBE_TIMEOUT_SECONDS = 120
_COLD_INSTALL_TIMEOUT_SECONDS = 600
_MAX_DIAGNOSTIC_BYTES = 64 * 1024
_PYTHON_PROBE = r"""
import json
import resource
import sys
import time

provider = sys.argv[1]
operation = sys.argv[2]
started = time.perf_counter()

if provider == "jacobian.networkx":
    import networkx as backend
    if operation == "reproduction":
        graph = backend.path_graph(32)
        assert backend.is_connected(graph)
elif provider == "jacobian.sympy":
    import sympy as backend
    if operation == "reproduction":
        x, y = backend.symbols("x y")
        matrix = backend.Matrix([x**2 + y, x * y])
        assert matrix.jacobian((x, y)).shape == (2, 2)
elif provider == "jacobian.z3":
    import z3 as backend
    if operation == "reproduction":
        x = backend.Real("x")
        solver = backend.Solver()
        solver.add(x == 1)
        assert solver.check() == backend.sat
elif provider == "cvc5":
    import cvc5 as backend
    if operation == "reproduction":
        solver = backend.Solver()
        solver.setOption("produce-proofs", "true")
        solver.setOption("proof-format-mode", "alethe")
        parser = backend.InputParser(solver)
        parser.setStringInput(
            backend.InputLanguage.SMT_LIB_2_6,
            "(set-logic QF_UF)\n"
            "(declare-fun p () Bool)\n"
            "(assert p)\n"
            "(assert (not p))\n"
            "(check-sat)\n",
            "provider-measure.smt2",
        )
        result = None
        while True:
            command = parser.nextCommand()
            if command.isNull():
                break
            output = command.invoke(solver, parser.getSymbolManager())
            if command.getCommandName() == "check-sat":
                result = output.strip()
        assert result == "unsat"
        proofs = solver.getProof(backend.ProofComponent.FULL)
        assert len(proofs) == 1
        assert solver.proofToString(proofs[0], backend.ProofFormat.ALETHE)
else:
    import jacobian.canonical as backend
    if operation == "reproduction":
        assert backend.canonicalize_json({"value": 1})

elapsed = time.perf_counter() - started
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
if sys.platform != "darwin":
    rss *= 1024
print(json.dumps({"seconds": elapsed, "peak_rss_bytes": rss}))
"""
_EXTERNAL_PROBE = r"""
import json
import resource
import subprocess
import sys
import time

started = time.perf_counter()
process = subprocess.run(
    sys.argv[1:],
    check=True,
    capture_output=True,
    timeout=105,
)
elapsed = time.perf_counter() - started
rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
if sys.platform != "darwin":
    rss *= 1024
print(json.dumps({
    "seconds": elapsed,
    "peak_rss_bytes": rss,
    "output_bytes": len(process.stdout) + len(process.stderr),
}))
"""


def _process_environment() -> dict[str, str]:
    names = (
        "HOME",
        "PATH",
        "ELAN_HOME",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "no_proxy",
        "SSL_CERT_FILE",
    )
    return {
        **{name: os.environ[name] for name in names if name in os.environ},
        "LC_ALL": "C.UTF-8",
        "PYTHONHASHSEED": "0",
    }


def _measure_command(command: list[str]) -> ProviderMeasurementSample:
    try:
        process = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
            env=_process_environment(),
        )
        if len(process.stdout.encode()) > _MAX_DIAGNOSTIC_BYTES:
            raise RuntimeError("provider probe output exceeded 64 KiB")
        payload = json.loads(process.stdout)
        return ProviderMeasurementSample(
            status=ProviderMeasurementStatus.COMPLETED,
            seconds=float(payload["seconds"]),
            peak_rss_bytes=int(payload["peak_rss_bytes"]),
            output_bytes=(
                int(payload["output_bytes"])
                if "output_bytes" in payload
                else len(process.stdout.encode())
            ),
        )
    except (
        KeyError,
        OSError,
        RuntimeError,
        ValueError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ):
        return ProviderMeasurementSample(
            status=ProviderMeasurementStatus.ERROR,
            detail="The provider measurement failed.",
        )


def _python_probe(
    runtime: CapabilityProviderRuntime,
    operation: str,
) -> ProviderMeasurementSample:
    return _measure_command(
        [sys.executable, "-c", _PYTHON_PROBE, runtime.provider, operation]
    )


def _lean_probe(*, reproduction: bool) -> ProviderMeasurementSample:
    from jacobian_checkers import lean4

    try:
        executable, _ = lean4.inspect_runtime(require_mathlib=False)
    except RuntimeError:
        return ProviderMeasurementSample(
            status=ProviderMeasurementStatus.ERROR,
            detail="The pinned Lean runtime is unavailable.",
        )
    if not reproduction:
        command = [str(executable), "-V"]
        return _measure_command([sys.executable, "-c", _EXTERNAL_PROBE, *command])
    with tempfile.TemporaryDirectory(prefix="jacobian-lean-measure-") as directory:
        source = Path(directory) / "Main.lean"
        source.write_text(
            "theorem jacobian_provider_probe : (1 : Nat) = 1 := by rfl\n",
            encoding="utf-8",
        )
        command = [str(executable), str(source)]
        return _measure_command([sys.executable, "-c", _EXTERNAL_PROBE, *command])


def _file_size(path: Path) -> int:
    try:
        if path.is_file() and not path.is_symlink():
            return path.stat().st_size
    except OSError:
        return 0
    return 0


def _tree_size(root: Path) -> int:
    return sum(_file_size(path) for path in root.rglob("*"))


def _installed_bytes(runtime: CapabilityProviderRuntime) -> int:
    distribution_name = runtime.configuration.get("distribution")
    if isinstance(distribution_name, str):
        distribution = importlib.metadata.distribution(distribution_name)
        total = 0
        for package_path in distribution.files or ():
            total += _file_size(Path(str(distribution.locate_file(package_path))))
        return total
    if runtime.provider == "jacobian.lean4":
        from jacobian_checkers import lean4

        executable, mathlib = lean4.inspect_runtime(require_mathlib=True)
        roots = {executable.parent.parent.resolve()}
        if mathlib is not None:
            roots.add(mathlib.resolve())
        return sum(_tree_size(root) for root in roots)
    module = importlib.import_module("jacobian")
    module_path = Path(str(module.__file__)).resolve().parent
    return _tree_size(module_path)


def _cold_install_spec(runtime: CapabilityProviderRuntime) -> str | None:
    distribution_name = runtime.configuration.get("distribution")
    if isinstance(distribution_name, str) and runtime.version is not None:
        return f"{distribution_name}=={runtime.version}"
    return None


def _measure_cold_install(
    runtime: CapabilityProviderRuntime,
    *,
    enabled: bool,
) -> ProviderMeasurementSample:
    if not enabled:
        return ProviderMeasurementSample(
            status=ProviderMeasurementStatus.SKIPPED,
            detail="Cold install was not requested.",
        )
    spec = _cold_install_spec(runtime)
    uv = shutil.which("uv")
    if spec is None or uv is None:
        return ProviderMeasurementSample(
            status=ProviderMeasurementStatus.SKIPPED,
            detail="This provider has no automated cold-install probe.",
        )
    with tempfile.TemporaryDirectory(prefix="jacobian-provider-install-") as directory:
        root = Path(directory)
        target = root / "target"
        environment = {
            **_process_environment(),
            "UV_CACHE_DIR": str(root / "cache"),
        }
        started = time.perf_counter()
        try:
            subprocess.run(
                [
                    uv,
                    "pip",
                    "install",
                    "--python",
                    sys.executable,
                    "--target",
                    str(target),
                    "--no-deps",
                    spec,
                ],
                cwd=Path.cwd(),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=_COLD_INSTALL_TIMEOUT_SECONDS,
                env=environment,
            )
        except (OSError, subprocess.SubprocessError):
            return ProviderMeasurementSample(
                status=ProviderMeasurementStatus.ERROR,
                detail="The cold install measurement failed.",
            )
        return ProviderMeasurementSample(
            status=ProviderMeasurementStatus.COMPLETED,
            seconds=time.perf_counter() - started,
            output_bytes=_tree_size(target),
        )


def measure_provider(
    runtime: CapabilityProviderRuntime,
    *,
    include_cold_install: bool = False,
) -> ProviderMeasurement:
    """Measure one exact available runtime without changing the capability catalog."""

    if runtime.provider == "jacobian.lean4":
        cold_start = _lean_probe(reproduction=False)
        reproduction = _lean_probe(reproduction=True)
    else:
        cold_start = _python_probe(runtime, "cold-start")
        reproduction = _python_probe(runtime, "reproduction")
    return ProviderMeasurement(
        provider_runtime=runtime,
        installed_bytes=_installed_bytes(runtime),
        cold_install=_measure_cold_install(
            runtime,
            enabled=include_cold_install,
        ),
        cold_start=cold_start,
        reproduction_case=reproduction,
    )
