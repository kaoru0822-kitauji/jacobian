#!/usr/bin/env python3
"""Audit a source-bound Jacobian agent installation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import jacobian
from jacobian.adapters.mcp.projections import _catalog_digest
from jacobian.contracts.capabilities import CapabilityProviderAvailability
from jacobian.runtime import CheckerAuthorityMode, create_runtime

PROFILES = ("core", "full-python", "lean", "external-proof")
_PROFILE_PROVIDERS = {
    "core": ("sympy",),
    "full-python": (
        "sympy",
        "python-flint",
        "python-flint-hnf",
        "cvc5",
    ),
    "lean": (
        "sympy",
        "python-flint",
        "python-flint-hnf",
        "cvc5",
        "lean",
    ),
    "external-proof": (
        "sympy",
        "python-flint",
        "python-flint-hnf",
        "cvc5",
        "cadical",
        "drat-trim",
        "carcara",
    ),
}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _provider_report(runtime: Any) -> dict[str, dict[str, Any]]:
    portfolio = runtime.portfolio
    fields = {
        "cadical": "cadical_runtime",
        "carcara": "carcara_runtime",
        "cvc5": "cvc5_runtime",
        "drat-trim": "drat_trim_runtime",
        "python-flint": "python_flint_runtime",
        "python-flint-hnf": "python_flint_hnf_runtime",
        "sympy": "sympy_polynomial_normalization_runtime",
        "lean": "lean_runtime",
    }
    report: dict[str, dict[str, Any]] = {}
    for name, field in fields.items():
        provider_runtime = getattr(portfolio, field)
        if provider_runtime is None:
            report[name] = {
                "availability": "UNAVAILABLE",
                "provider": None,
                "version": None,
                "digest": None,
                "diagnostic": "provider runtime was not resolved",
            }
            continue
        report[name] = {
            "availability": provider_runtime.availability.value,
            "provider": provider_runtime.provider,
            "version": provider_runtime.version,
            "digest": provider_runtime.digest,
            "digest_kind": (
                provider_runtime.digest_kind.value
                if provider_runtime.digest_kind is not None
                else None
            ),
            "diagnostic": provider_runtime.diagnostic,
        }
    return dict(sorted(report.items()))


def inspect_installation(
    *, repo: Path, state_dir: Path, profile: str, expected_revision: str
) -> dict[str, Any]:
    """Return a source, catalog, and provider identity report."""

    repo = repo.resolve(strict=True)
    state_dir = state_dir.resolve()
    revision = _git(repo, "rev-parse", "HEAD")
    dirty = bool(_git(repo, "status", "--porcelain"))
    package_source = Path(jacobian.__file__).resolve()
    expected_source = (repo / "src" / "jacobian").resolve()
    source_matches = package_source.is_relative_to(expected_source)
    with (repo / "pyproject.toml").open("rb") as stream:
        expected_version = tomllib.load(stream)["project"]["version"]

    state_dir.mkdir(parents=True, exist_ok=True)
    with create_runtime(
        state_dir,
        checker_authority=CheckerAuthorityMode.INSTALL_BUNDLED,
    ) as runtime:
        catalog = runtime.core.capabilities.catalog()
        providers = _provider_report(runtime)
        digest = _catalog_digest(catalog.catalog_version, catalog.capabilities)
        diagnostics = [
            {
                "code": item.code,
                "component_id": item.component_id,
                "stage": item.stage,
                "message": item.message,
            }
            for item in runtime.portfolio.portfolio_diagnostics
        ]

    missing = [
        provider
        for provider in _PROFILE_PROVIDERS[profile]
        if providers.get(provider, {}).get("availability")
        != CapabilityProviderAvailability.AVAILABLE.value
    ]
    checks = {
        "git_clean": not dirty,
        "revision_matches": revision == expected_revision,
        "package_version_matches": jacobian.__version__ == expected_version,
        "source_checkout_matches": source_matches,
        "profile_providers_available": not missing,
    }
    return {
        "status": "ok" if all(checks.values()) else "error",
        "profile": profile,
        "repo": str(repo),
        "state_dir": str(state_dir),
        "git_revision": revision,
        "expected_git_revision": expected_revision,
        "git_dirty": dirty,
        "package_version": jacobian.__version__,
        "expected_package_version": expected_version,
        "package_source": str(package_source),
        "catalog_digest": digest,
        "catalog_size": len(catalog.capabilities),
        "policy_profile": catalog.policy_profile,
        "policy_digest": catalog.policy_digest,
        "providers": providers,
        "missing_profile_providers": missing,
        "portfolio_diagnostics": diagnostics,
        "checks": checks,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        report = inspect_installation(
            repo=args.repo,
            state_dir=args.state_dir,
            profile=args.profile,
            expected_revision=args.expected_revision,
        )
    except (
        OSError,
        RuntimeError,
        subprocess.CalledProcessError,
        KeyError,
        ValueError,
    ) as error:
        print(f"source-agent doctor failed: {error}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    if args.json:
        print(rendered, end="")
    else:
        marker = "✓" if report["status"] == "ok" else "✗"
        print(f"{marker} source checkout: {report['git_revision']}")
        print(f"{marker} package: {report['package_version']}")
        print(
            f"{marker} catalog: {report['catalog_digest']} "
            f"({report['catalog_size']} capabilities)"
        )
        for provider, status in report["providers"].items():
            available = status["availability"] == "AVAILABLE"
            print(
                f"{'✓' if available else '-'} provider {provider}: "
                f"{status['availability']} ({status['version'] or 'not installed'})"
            )
        if report["missing_profile_providers"]:
            print(
                "missing providers for profile: "
                + ", ".join(report["missing_profile_providers"]),
                file=sys.stderr,
            )
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
