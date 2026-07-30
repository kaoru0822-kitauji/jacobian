"""Measure the inexpensive startup/storage phases independently.

Run with::

    uv run python benchmarks/performance/benchmark_startup_phases.py

The complete-runtime benchmark intentionally remains separate: this module
keeps storage bootstrap and schema meta-validation visible without hiding them
inside one portfolio-construction number.  A caller can compare these phases
with the composition benchmark while changing one seam at a time.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pyperf

from jacobian.canonical import canonicalize_json
from jacobian.schema_registry import _validated_schema
from jacobian.schema_validation import check_draft202012_schema
from jacobian.store import ArtifactStore

_BENCHMARK_SCHEMA = canonicalize_json(
    {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
        "additionalProperties": False,
    }
)


def _store_bootstrap() -> None:
    with (
        tempfile.TemporaryDirectory(prefix="jacobian-store-startup-") as directory,
        ArtifactStore(Path(directory)),
    ):
        pass


def _store_bootstrap_normal() -> None:
    """Measure the disposable-store baseline without weakening the default.

    ``FULL`` is the production durability policy.  Keeping an explicit
    ``NORMAL`` comparison in this benchmark makes the fsync cost visible
    without turning a machine-local timing into a correctness assertion.
    """

    with (
        tempfile.TemporaryDirectory(
            prefix="jacobian-store-startup-normal-"
        ) as directory,
        ArtifactStore(Path(directory), synchronous="NORMAL"),
    ):
        pass


def _schema_validation_cold() -> None:
    _validated_schema.cache_clear()
    check_draft202012_schema.cache_clear()
    _validated_schema(_BENCHMARK_SCHEMA)


def _schema_validation_warm() -> None:
    _validated_schema(_BENCHMARK_SCHEMA)


def _fresh_materialization() -> None:
    """Materialize a complete portfolio into a new state directory."""

    from jacobian.runtime import CheckerAuthorityMode, create_runtime

    with tempfile.TemporaryDirectory(
        prefix="jacobian-fresh-materialization-"
    ) as directory:
        runtime = create_runtime(
            Path(directory),
            checker_authority=CheckerAuthorityMode.INSTALL_BUNDLED,
        )
        runtime.close()


def _attachment(root: Path) -> None:
    """Attach to an already materialized state without checker hydration."""

    from jacobian.runtime import create_runtime

    runtime = create_runtime(root)
    runtime.close()


def _authorized_reference_hydration(root: Path) -> None:
    """Attach while hydrating operator-authorized reference records."""

    from jacobian.runtime import CheckerAuthorityMode, create_runtime

    runtime = create_runtime(
        root,
        checker_authority=CheckerAuthorityMode.HYDRATE_EXISTING,
    )
    runtime.close()


def _one_domain_installation() -> None:
    """Install one literal domain bundle through production seams."""

    from jacobian.domains.builtins import build_builtin_domain_bundles
    from jacobian.installation.context import create_installation_context
    from jacobian.portfolio.domain_installation import DomainBundleInstaller
    from jacobian.portfolio.model import PortfolioPlan
    from jacobian.runtime.bootstrap import bootstrap_services
    from jacobian.runtime.config import RuntimeOptions
    from jacobian.runtime.services import build_application_services

    with tempfile.TemporaryDirectory(prefix="jacobian-domain-install-") as directory:
        options = RuntimeOptions()
        core = bootstrap_services(Path(directory), options)
        try:
            application = build_application_services(core)
            context = create_installation_context(core, application, options)
            DomainBundleInstaller(context).install(
                PortfolioPlan(domain_bundles=(build_builtin_domain_bundles()[0],))
            )
        finally:
            core.close()


def _core_service_assembly() -> None:
    """Assemble core and application services without portfolio installation."""

    from jacobian.runtime.bootstrap import bootstrap_services
    from jacobian.runtime.config import RuntimeOptions
    from jacobian.runtime.services import build_application_services

    with tempfile.TemporaryDirectory(prefix="jacobian-core-assembly-") as directory:
        core = bootstrap_services(Path(directory), RuntimeOptions())
        try:
            build_application_services(core)
        finally:
            core.close()


def main() -> None:
    runner = pyperf.Runner(processes=1, values=1, loops=1, warmups=0)
    runner.metadata["suite"] = "jacobian-startup-phases"
    runner.bench_func("store-bootstrap", _store_bootstrap)
    runner.bench_func("store-bootstrap-normal", _store_bootstrap_normal)
    runner.bench_func("schema-validation-cold", _schema_validation_cold)
    # Prime the cache after the cold benchmark because pyperf may execute
    # benchmarks in one worker process.
    check_draft202012_schema(_BENCHMARK_SCHEMA)
    runner.bench_func("schema-validation-warm", _schema_validation_warm)

    runner.bench_func("fresh-materialization", _fresh_materialization)
    runner.bench_func("core-service-assembly", _core_service_assembly)
    # Populate a private benchmark state outside the timed attachment phases.
    from jacobian.runtime import CheckerAuthorityMode, create_runtime

    with tempfile.TemporaryDirectory(prefix="jacobian-attachment-state-") as directory:
        populated = Path(directory)
        seed = create_runtime(
            populated,
            checker_authority=CheckerAuthorityMode.INSTALL_BUNDLED,
        )
        seed.close()
        runner.bench_func("attachment", lambda: _attachment(populated))
        runner.bench_func(
            "authorized-reference-hydration",
            lambda: _authorized_reference_hydration(populated),
        )
    runner.bench_func("one-domain-installation", _one_domain_installation)


if __name__ == "__main__":
    main()
