"""Check or update the self-contained Harbor verifier support copies."""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
DATASET = ROOT / "benchmarks" / "regression-v1"
SOURCE = DATASET / "verifier_support.py"
TASKS = DATASET / "tasks"
CHECKSUM_PATTERN = re.compile(r'jacobian\.checksum="[0-9a-f]{64}"')


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _targets() -> tuple[Path, ...]:
    return tuple(
        task / "tests" / "verifier_support.py"
        for task in sorted(TASKS.iterdir())
        if task.is_dir()
    )


def _dockerfile_for(target: Path) -> Path:
    return target.with_name("Dockerfile")


def _dockerfile_content(target: Path) -> str:
    dockerfile = _dockerfile_for(target)
    content = dockerfile.read_text()
    checksum = _digest(target.with_name("verifier.py"))
    content, replacements = CHECKSUM_PATTERN.subn(
        f'jacobian.checksum="{checksum}"',
        content,
    )
    if replacements != 1:
        raise ValueError(
            f"{dockerfile.relative_to(ROOT)} must declare one verifier checksum"
        )
    lines = content.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith("COPY ") and "verifier.py" in line and " /tests/" in line:
            if "verifier_support.py" not in line:
                lines[index] = line.replace(
                    " /tests/",
                    " verifier_support.py /tests/",
                )
            break
    else:
        raise ValueError(
            f"{dockerfile.relative_to(ROOT)} must copy verifier.py into /tests"
        )
    return "".join(lines)


def check() -> int:
    expected = _digest(SOURCE)
    stale: list[Path] = []
    for target in _targets():
        if not target.is_file() or _digest(target) != expected:
            stale.append(target)
        dockerfile = _dockerfile_for(target)
        try:
            expected_dockerfile = _dockerfile_content(target)
        except (OSError, ValueError) as exc:
            print(exc, file=sys.stderr)
            return 1
        if dockerfile.read_text() != expected_dockerfile:
            stale.append(dockerfile)
    if stale:
        print("Harbor verifier support or image metadata drift:", file=sys.stderr)
        for target in stale:
            print(target.relative_to(ROOT), file=sys.stderr)
        return 1
    print(
        f"Harbor verifier support and image metadata match for "
        f"{len(_targets())} tasks."
    )
    return 0


def write() -> int:
    for target in _targets():
        shutil.copyfile(SOURCE, target)
        dockerfile = _dockerfile_for(target)
        dockerfile.write_text(_dockerfile_content(target))
    print(
        f"Updated Harbor verifier support and image metadata for "
        f"{len(_targets())} tasks."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    return check() if args.check else write()


if __name__ == "__main__":
    raise SystemExit(main())
