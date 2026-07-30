"""Explicit source-handler registry; no recursive or import-time discovery."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from ..catalog import PACKAGE_ROOT, load_sources
from ..models import TaskSpec
from .base import SourceHandler
from .github_data_rows import GitHubStructuredDataHandler
from .github_declarations import LANGUAGES, GitHubFormalDeclarationHandler
from .huggingface_rows import HuggingFaceExactAnswerHandler
from .huggingface_structured import HuggingFaceStructuredDiagnosticHandler
from .ineqmath import IneqMathHandler

PROBE_PATH = PACKAGE_ROOT / "catalog" / "handler-probes.json"
GITHUB_PROBE_PATH = PACKAGE_ROOT / "catalog" / "handler-probes-github.json"
STRUCTURED_PROBE_PATH = PACKAGE_ROOT / "catalog" / "handler-probes-structured.json"
GITHUB_DATA_PROBE_PATH = PACKAGE_ROOT / "catalog" / "handler-probes-github-data.json"


def _supported_ids(path: Path, handler: str) -> tuple[str, ...]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("probe_version") != 1:
        raise ValueError(f"unsupported {handler} probe version")
    sources = {source.source_id: source for source in load_sources()}
    supported: list[str] = []
    for record in report["records"]:
        if record.get("handler") != handler or record.get("status") != "supported":
            continue
        source = sources.get(record.get("source_id"))
        if (
            source is None
            or not source.immutable_revision
            or not source.snapshot_sha256
            or record.get("source_revision") != source.immutable_revision
            or record.get("snapshot_sha256") != source.snapshot_sha256
        ):
            continue
        if (
            handler == "github-formal-declarations-v1"
            and source.subresource_path
            and Path(source.subresource_path).suffix.lower() not in LANGUAGES
        ):
            continue
        supported.append(source.source_id)
    return tuple(supported)


def _supported_huggingface_ids() -> tuple[str, ...]:
    return _supported_ids(PROBE_PATH, "huggingface-scalar-exact-answer-v1")


def _supported_github_ids() -> tuple[str, ...]:
    return _supported_ids(GITHUB_PROBE_PATH, "github-formal-declarations-v1")


def _supported_structured_ids() -> tuple[str, ...]:
    if not STRUCTURED_PROBE_PATH.exists():
        return ()
    exact_ids = frozenset(_supported_huggingface_ids())
    return tuple(
        source_id
        for source_id in _supported_ids(
            STRUCTURED_PROBE_PATH, "huggingface-structured-diagnostic-v1"
        )
        if source_id not in exact_ids
    )


def _supported_github_data_ids() -> tuple[str, ...]:
    if not GITHUB_DATA_PROBE_PATH.exists():
        return ()
    return _supported_ids(GITHUB_DATA_PROBE_PATH, "github-structured-data-v1")


HANDLERS: tuple[SourceHandler, ...] = (
    IneqMathHandler(),
    *(
        HuggingFaceExactAnswerHandler(source_id)
        for source_id in _supported_huggingface_ids()
    ),
    *(
        GitHubFormalDeclarationHandler(source_id)
        for source_id in _supported_github_ids()
    ),
    *(
        HuggingFaceStructuredDiagnosticHandler(source_id)
        for source_id in _supported_structured_ids()
    ),
    *(
        GitHubStructuredDataHandler(source_id)
        for source_id in _supported_github_data_ids()
    ),
)


def handled_source_ids() -> frozenset[str]:
    ids = [handler.source_id for handler in HANDLERS]
    if len(ids) != len(set(ids)):
        raise ValueError("source handler ownership overlaps")
    return frozenset(ids)


def materialize_handler_specs(
    *,
    cache_dir: Path,
    offline: bool,
    full: bool,
    selected_source_ids: frozenset[str] = frozenset(),
) -> tuple[TaskSpec, ...]:
    return tuple(
        iter_materialized_handler_specs(
            cache_dir=cache_dir,
            offline=offline,
            full=full,
            selected_source_ids=selected_source_ids,
        )
    )


def iter_materialized_handler_specs(
    *,
    cache_dir: Path,
    offline: bool,
    full: bool,
    selected_source_ids: frozenset[str] = frozenset(),
) -> Iterator[TaskSpec]:
    sources = {source.source_id: source for source in load_sources()}
    for handler in HANDLERS:
        owned_source = sources.get(handler.source_id)
        if owned_source is None:
            raise ValueError(f"handler owns unknown source {handler.source_id}")
        if selected_source_ids and owned_source.source_id not in selected_source_ids:
            continue
        if full and isinstance(handler, HuggingFaceExactAnswerHandler):
            handler_specs = handler.iter_full_specs(
                owned_source,
                cache_dir=cache_dir,
                offline=offline,
            )
        else:
            snapshot = handler.acquire(
                owned_source, cache_dir=cache_dir, offline=offline
            )
            handler_specs = handler.iter_specs(owned_source, snapshot, full=full)
        yield from handler_specs
