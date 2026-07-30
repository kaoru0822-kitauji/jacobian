"""Explicit source-handler registry; no recursive or import-time discovery."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

from ..catalog import PACKAGE_ROOT, load_sources
from ..models import TaskSpec
from ..partitions import FAMILY_ALIASES, source_family_key
from .base import SourceHandler
from .github_data_rows import GitHubStructuredDataHandler
from .github_declarations import GitHubFormalDeclarationHandler
from .huggingface_rows import HuggingFaceExactAnswerHandler
from .huggingface_structured import HuggingFaceStructuredDiagnosticHandler
from .ineqmath import IneqMathHandler

PROBE_PATH = PACKAGE_ROOT / "catalog" / "handler-probes.json"
GITHUB_PROBE_PATH = PACKAGE_ROOT / "catalog" / "handler-probes-github.json"
STRUCTURED_PROBE_PATH = PACKAGE_ROOT / "catalog" / "handler-probes-structured.json"
GITHUB_DATA_PROBE_PATH = PACKAGE_ROOT / "catalog" / "handler-probes-github-data.json"
SOURCE_RELATIONS_PATH = PACKAGE_ROOT / "catalog" / "source-relations.json"


def _supported_huggingface_ids() -> tuple[str, ...]:
    report = json.loads(PROBE_PATH.read_text(encoding="utf-8"))
    if report.get("probe_version") != 1:
        raise ValueError("unsupported handler probe version")
    return tuple(
        record["source_id"]
        for record in report["records"]
        if record.get("handler") == "huggingface-scalar-exact-answer-v1"
        and record.get("status") == "supported"
    )


def _supported_github_ids() -> tuple[str, ...]:
    report = json.loads(GITHUB_PROBE_PATH.read_text(encoding="utf-8"))
    if report.get("probe_version") != 1:
        raise ValueError("unsupported GitHub handler probe version")
    return tuple(
        record["source_id"]
        for record in report["records"]
        if record.get("handler") == "github-formal-declarations-v1"
        and record.get("status") == "supported"
    )


def _supported_structured_ids() -> tuple[str, ...]:
    if not STRUCTURED_PROBE_PATH.exists():
        return ()
    report = json.loads(STRUCTURED_PROBE_PATH.read_text(encoding="utf-8"))
    if report.get("probe_version") != 1:
        raise ValueError("unsupported structured handler probe version")
    exact_ids = frozenset(_supported_huggingface_ids())
    return tuple(
        record["source_id"]
        for record in report["records"]
        if record.get("handler") == "huggingface-structured-diagnostic-v1"
        and record.get("status") == "supported"
        and record["source_id"] not in exact_ids
    )


def _supported_github_data_ids() -> tuple[str, ...]:
    if not GITHUB_DATA_PROBE_PATH.exists():
        return ()
    report = json.loads(GITHUB_DATA_PROBE_PATH.read_text(encoding="utf-8"))
    if report.get("probe_version") != 1:
        raise ValueError("unsupported GitHub data handler probe version")
    return tuple(
        record["source_id"]
        for record in report["records"]
        if record.get("handler") == "github-structured-data-v1"
        and record.get("status") == "supported"
    )


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


def _source_relations() -> dict[str, tuple[str, ...]]:
    value = json.loads(SOURCE_RELATIONS_PATH.read_text(encoding="utf-8"))
    if value.get("relation_version") != 1:
        raise ValueError("unsupported source relation version")
    return {
        record["leader_source_id"]: tuple(record["related_source_ids"])
        for record in value["relations"]
    }


def handled_source_ids() -> frozenset[str]:
    ids = [handler.source_id for handler in HANDLERS]
    if len(ids) != len(set(ids)):
        raise ValueError("source handler ownership overlaps")
    handled = frozenset(ids)
    handled_families = {
        source_family_key(source)
        for source in load_sources()
        if source.source_id in handled and source_family_key(source) in FAMILY_ALIASES
    }
    expanded = {
        source.source_id
        for source in load_sources()
        if source.source_id in handled or source_family_key(source) in handled_families
    }
    relations = _source_relations()
    for leader, related_ids in relations.items():
        if leader in handled:
            expanded.update(related_ids)
    return frozenset(expanded)


def materialize_handler_specs(
    *,
    cache_dir: Path,
    offline: bool,
    full: bool,
) -> tuple[TaskSpec, ...]:
    return tuple(
        iter_materialized_handler_specs(
            cache_dir=cache_dir,
            offline=offline,
            full=full,
            selected_source_ids=frozenset(),
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
    related: dict[str, tuple[str, ...]] = {}
    for source in sources.values():
        family = source_family_key(source)
        if family in FAMILY_ALIASES:
            related[family] = tuple(
                sorted(
                    candidate.source_id
                    for candidate in sources.values()
                    if source_family_key(candidate) == family
                )
            )
    source_relations = _source_relations()
    for handler in HANDLERS:
        owned_source = sources.get(handler.source_id)
        if owned_source is None:
            raise ValueError(f"handler owns unknown source {handler.source_id}")
        family = source_family_key(owned_source)
        expanded_source_ids = tuple(
            sorted(
                {
                    *related.get(family, (owned_source.source_id,)),
                    *source_relations.get(owned_source.source_id, ()),
                }
            )
        )
        if selected_source_ids and not selected_source_ids.intersection(
            expanded_source_ids
        ):
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
        for spec in handler_specs:
            yield replace(spec, source_ids=expanded_source_ids)
