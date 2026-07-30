"""Validate and execute the repository's semantic pytest topology.

This module is deliberately a small control plane.  It reads
``tests/topology.toml``, validates ownership, and delegates collection and
execution to pytest.  Selection, filtering, retries, and fixture resolution
remain pytest concerns.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "tests" / "topology.toml"
_DISTRIBUTIONS = {"none", "load", "loadscope", "loadfile", "loadgroup", "worksteal"}
_CI_TARGETS = {"pull_request", "merge_queue", "main", "scheduled"}


class TopologyError(ValueError):
    """Raised when a topology manifest is malformed or incomplete."""


@dataclass(frozen=True)
class Lane:
    """One independently scheduled pytest resource lane."""

    name: str
    tier: str
    paths: tuple[str, ...]
    workers: int
    distribution: str
    timeout_seconds: int
    required_environment: tuple[str, ...]
    required_provider: str | None
    timing_sharding: bool
    ci: Mapping[str, bool]


@dataclass(frozen=True)
class Topology:
    """A validated topology and the repository root it belongs to."""

    manifest: Path
    root: Path
    lanes: tuple[Lane, ...]

    def lane(self, name: str) -> Lane:
        for lane in self.lanes:
            if lane.name == name:
                return lane
        raise TopologyError(f"unknown topology lane: {name}")


def _as_string_list(
    value: Any, field: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TopologyError(f"{field} must be an array of strings")
    if not allow_empty and not value:
        raise TopologyError(f"{field} must not be empty")
    return tuple(value)


def _tracked_files(root: Path) -> set[str]:
    """Return tracked paths, with a filesystem fallback for extracted trees."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
    return {line for line in result.stdout.splitlines() if line}


def _test_files(root: Path, tracked: set[str]) -> set[str]:
    return {
        path
        for path in tracked
        if path.startswith("tests/")
        and Path(path).name.startswith("test_")
        and Path(path).suffix == ".py"
        and (root / path).is_file()
    }


def _matches(root: Path, pattern: str) -> set[str]:
    """Expand one ownership path into relative files.

    Paths may name a file, directory, or a normal pathlib glob.  Directory
    ownership is recursive, which keeps the manifest readable as tests grow.
    """
    if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
        raise TopologyError(f"lane path must be repository-relative: {pattern}")
    candidates = (
        list(root.glob(pattern))
        if any(char in pattern for char in "*?[")
        else [root / pattern]
    )
    if not candidates:
        raise TopologyError(f"lane path does not resolve: {pattern}")
    files: set[str] = set()
    for candidate in candidates:
        if not candidate.exists():
            continue
        if candidate.is_dir():
            files.update(
                path.relative_to(root).as_posix()
                for path in candidate.rglob("test_*.py")
                if path.is_file()
            )
        elif (
            candidate.is_file()
            and candidate.name.startswith("test_")
            and candidate.suffix == ".py"
        ):
            files.add(candidate.relative_to(root).as_posix())
    if not files:
        raise TopologyError(f"lane path resolves without test files: {pattern}")
    return files


def validate_topology(
    data: Mapping[str, Any], *, root: Path, manifest: Path
) -> Topology:
    """Validate raw TOML data and return typed topology metadata."""
    if data.get("version") != 1:
        raise TopologyError("topology version must be 1")
    raw_lanes = data.get("lanes")
    if not isinstance(raw_lanes, list) or not raw_lanes:
        raise TopologyError("topology must define a non-empty [[lanes]] array")

    lanes: list[Lane] = []
    names: set[str] = set()
    for index, raw in enumerate(raw_lanes):
        if not isinstance(raw, dict):
            raise TopologyError(f"lane {index} must be a table")
        try:
            name = raw["name"]
            tier = raw["tier"]
            paths = _as_string_list(
                raw["paths"], f"lane {index}.paths", allow_empty=False
            )
            workers = raw["workers"]
            distribution = raw["distribution"]
            timeout = raw["timeout_seconds"]
            environment = _as_string_list(
                raw["required_environment"], f"lane {index}.required_environment"
            )
            provider = raw["required_provider"]
            timing = raw["timing_sharding"]
            ci = raw["ci"]
        except KeyError as exc:
            raise TopologyError(f"lane {index} missing field: {exc.args[0]}") from exc
        if not isinstance(name, str) or not name or name in names:
            raise TopologyError(f"lane {index} has duplicate or invalid name")
        if not isinstance(tier, str) or not tier:
            raise TopologyError(f"lane {name}.tier must be a string")
        if not isinstance(workers, int) or workers < 0:
            raise TopologyError(f"lane {name}.workers must be a non-negative integer")
        if not isinstance(distribution, str) or distribution not in _DISTRIBUTIONS:
            raise TopologyError(f"lane {name}.distribution is invalid")
        if workers == 0 and distribution != "none":
            raise TopologyError(f"lane {name}: workers=0 requires distribution='none'")
        if workers > 0 and distribution == "none":
            raise TopologyError(
                f"lane {name}: workers>0 requires an xdist distribution"
            )
        if not isinstance(timeout, int) or timeout <= 0:
            raise TopologyError(f"lane {name}.timeout_seconds must be positive")
        if provider is not None and not isinstance(provider, str):
            raise TopologyError(f"lane {name}.required_provider must be a string")
        if provider == "":
            provider = None
        if not isinstance(timing, bool):
            raise TopologyError(f"lane {name}.timing_sharding must be boolean")
        if (
            not isinstance(ci, dict)
            or set(ci) != _CI_TARGETS
            or not all(isinstance(value, bool) for value in ci.values())
        ):
            raise TopologyError(f"lane {name}.ci must define {_CI_TARGETS} as booleans")
        names.add(name)
        lanes.append(
            Lane(
                name,
                tier,
                paths,
                workers,
                distribution,
                timeout,
                environment,
                provider,
                timing,
                dict(ci),
            )
        )

    tracked = _tracked_files(root)
    test_files = _test_files(root, tracked)
    ownership: dict[str, list[str]] = {path: [] for path in test_files}
    for lane in lanes:
        for pattern in lane.paths:
            matches = _matches(root, pattern)
            untracked = matches - tracked
            if untracked:
                raise TopologyError(
                    f"lane {lane.name} owns untracked paths: {sorted(untracked)}"
                )
            for path in matches:
                if path in ownership:
                    ownership[path].append(lane.name)
    missing = sorted(path for path, owners in ownership.items() if not owners)
    overlapping = sorted(
        (path, owners) for path, owners in ownership.items() if len(owners) != 1
    )
    if overlapping:
        details = "; ".join(
            f"{path} ({', '.join(owners)})" for path, owners in overlapping
        )
        raise TopologyError(f"test files belong to multiple lanes: {details}")
    if missing:
        raise TopologyError(f"test files have no lane: {', '.join(missing)}")
    return Topology(manifest, root, tuple(lanes))


def load_topology(path: Path = DEFAULT_MANIFEST) -> Topology:
    """Load and validate a topology TOML file."""
    manifest = path.resolve()
    try:
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TopologyError(f"cannot read topology manifest {manifest}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise TopologyError(f"invalid topology TOML: {exc}") from exc
    return validate_topology(data, root=manifest.parent.parent, manifest=manifest)


def pytest_command(
    topology: Topology,
    lane_name: str,
    selectors: list[str] | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Build one pytest invocation without interpreting selectors."""
    lane = topology.lane(lane_name)
    command = [sys.executable, "-m", "pytest"]
    command.extend(selectors if selectors else list(lane.paths))
    command.extend(extra_args or ())
    if lane.workers:
        command.extend(["-n", str(lane.workers), "--dist", lane.distribution])
    command.extend(["--timeout", str(lane.timeout_seconds)])
    return command


def run_lane(
    topology: Topology,
    lane_name: str,
    selectors: list[str] | None = None,
    extra_args: list[str] | None = None,
) -> int:
    """Execute pytest without retaining an extra POSIX control-plane process."""
    command = pytest_command(topology, lane_name, selectors, extra_args)
    environment = os.environ.copy()
    environment.setdefault("JACOBIAN_TEST_LANE", lane_name)
    if os.name == "nt":  # pragma: no cover - exercised by Windows CI
        return subprocess.run(
            command, cwd=topology.root, env=environment, check=False
        ).returncode
    os.chdir(topology.root)
    os.execvpe(command[0], command, environment)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lane", help="topology lane to execute")
    parser.add_argument("selectors", nargs="*", help="exact pytest paths or node IDs")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--dry-run", action="store_true", help="print the pytest command"
    )
    args, extra_args = parser.parse_known_args(argv)
    try:
        topology = load_topology(args.manifest)
        command = pytest_command(topology, args.lane, args.selectors, extra_args)
    except TopologyError as exc:
        parser.error(str(exc))
    if args.dry_run:
        print(shlex.join(command))
        return 0
    return run_lane(topology, args.lane, args.selectors, extra_args)


if __name__ == "__main__":
    raise SystemExit(main())
