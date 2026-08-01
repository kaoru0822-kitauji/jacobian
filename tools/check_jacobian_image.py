#!/usr/bin/env python3
"""Bind a digest-pinned Jacobian image to trusted, external source identity."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_DIGEST_IMAGE = re.compile(r"^.+@(sha256:[0-9a-f]{64})$")
IDENTITY_SCHEMA = "jacobian-image-identity-v1"
REVISION_LABEL = "org.opencontainers.image.revision"
VERSION_LABEL = "org.opencontainers.image.version"


def _repository_version(repo: Path) -> str:
    """Return the same normalized version used by the image build."""

    return subprocess.run(
        ["uv", "version", "--project", str(repo), "--short"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def inspect_image(
    image: str,
    *,
    identity: Mapping[str, Any],
    expected_revision: str,
    expected_version: str,
    pull: bool,
) -> dict[str, Any]:
    """Compare a local image with an independently supplied identity record."""

    image_match = _DIGEST_IMAGE.fullmatch(image)
    if image_match is None:
        raise ValueError("image must be pinned by @sha256:<64 lowercase hex digits>")
    expected_identity = {
        "schema_version": IDENTITY_SCHEMA,
        "image_digest": image_match.group(1),
        "git_revision": expected_revision,
        "package_version": expected_version,
    }
    for field, expected in expected_identity.items():
        actual = identity.get(field)
        if not isinstance(actual, str):
            raise ValueError(f"image identity field {field!r} must be a string")
        if actual != expected:
            raise ValueError(
                f"image identity field {field!r} is {actual!r}; expected {expected!r}"
            )
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
        "identity_digest_matches": True,
        "identity_revision_matches": True,
        "identity_version_matches": True,
        "revision_label_matches": revision == expected_revision,
        "version_label_matches": version == expected_version,
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
    parser.add_argument(
        "--identity-lock",
        required=True,
        type=Path,
        help="trusted JSON record binding the image digest to source identity",
    )
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
            version = _repository_version(repo)
        else:
            version = args.expected_version
        with args.identity_lock.open(encoding="utf-8") as stream:
            identity = json.load(stream)
        if not isinstance(identity, dict):
            raise ValueError("image identity lock must contain a JSON object")
        report = inspect_image(
            args.image,
            identity=identity,
            expected_revision=revision,
            expected_version=version,
            pull=args.pull,
        )
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        KeyError,
        OSError,
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
