#!/usr/bin/env python3
"""Require a digest-pinned Jacobian image built from the selected checkout."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

_DIGEST_IMAGE = re.compile(r"^.+@sha256:[0-9a-f]{64}$")
REVISION_LABEL = "org.opencontainers.image.revision"
VERSION_LABEL = "org.opencontainers.image.version"


def inspect_image(
    image: str,
    *,
    expected_revision: str,
    expected_version: str,
    pull: bool,
) -> dict[str, Any]:
    """Inspect local OCI labels and return their exact comparison."""

    if not _DIGEST_IMAGE.fullmatch(image):
        raise ValueError("image must be pinned by @sha256:<64 lowercase hex digits>")
    if pull:
        subprocess.run(["docker", "pull", image], check=True)
    completed = subprocess.run(
        ["docker", "image", "inspect", image],
        check=True,
        capture_output=True,
        text=True,
    )
    inspected = json.loads(completed.stdout)
    if not isinstance(inspected, list) or len(inspected) != 1:
        raise ValueError("docker returned an unexpected image inspection document")
    labels = inspected[0].get("Config", {}).get("Labels") or {}
    revision = labels.get(REVISION_LABEL)
    version = labels.get(VERSION_LABEL)
    checks = {
        "revision_matches": revision == expected_revision,
        "version_matches": version == expected_version,
    }
    return {
        "status": "ok" if all(checks.values()) else "error",
        "image": image,
        "image_revision": revision,
        "expected_revision": expected_revision,
        "image_version": version,
        "expected_version": expected_version,
        "checks": checks,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--expected-revision")
    parser.add_argument("--expected-version")
    parser.add_argument("--pull", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    repo = args.repo.resolve()
    try:
        dirty = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if dirty:
            raise ValueError(
                "the selected checkout is dirty; image identity requires a clean Git tree"
            )
        revision = (
            args.expected_revision
            or subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        if args.expected_version is None:
            with (repo / "pyproject.toml").open("rb") as stream:
                version = tomllib.load(stream)["project"]["version"]
        else:
            version = args.expected_version
        report = inspect_image(
            args.image,
            expected_revision=revision,
            expected_version=version,
            pull=args.pull,
        )
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        KeyError,
        subprocess.CalledProcessError,
        ValueError,
    ) as error:
        print(f"Jacobian image preflight failed: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"image revision: {report['image_revision'] or 'missing'} "
            f"(expected {report['expected_revision']})"
        )
        print(
            f"image version: {report['image_version'] or 'missing'} "
            f"(expected {report['expected_version']})"
        )
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
