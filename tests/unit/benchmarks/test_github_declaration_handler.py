from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from benchmarks.jacobian_math_evals.catalog import load_sources
from benchmarks.jacobian_math_evals.handlers.github_declarations import (
    GitHubFormalDeclarationHandler,
    declarations,
)
from benchmarks.jacobian_math_evals.handlers.registry import HANDLERS
from benchmarks.jacobian_math_evals.models import (
    OracleKind,
    TaskReadiness,
)

FIXTURE = Path(__file__).parent / "fixtures" / "github_formal_declarations.json"


def _source():
    source = next(
        source
        for source in load_sources()
        if source.host == "github.com" and source.immutable_revision is not None
    )
    return replace(
        source,
        source_id="src-111111111111",
        canonical_url="https://github.com/example/formal",
        immutable_revision="1" * 40,
    )


@pytest.mark.parametrize(
    ("language", "content", "expected"),
    [
        ("lean", "def x := 1\nlemma y : True := by trivial\n", ("x", "y")),
        ("rocq", "Definition x := 1.\nTheorem y : True.\n", ("x", "y")),
        (
            "isabelle",
            'definition x where "x = 1"\nlemma y: "True"\n',
            ("x", "y"),
        ),
        ("metamath", "ax-1 $a |- ph $.\nth-1 $p |- ph $= x $.", ("ax-1", "th-1")),
        (
            "hol-light",
            "let X = new_definition `X = 1`;;\nlet Y = prove (`T`,TAUT_TAC);;",
            ("X", "Y"),
        ),
    ],
)
def test_language_declaration_parsers(
    language: str,
    content: str,
    expected: tuple[str, ...],
) -> None:
    assert declarations(language, content) == expected


def test_formal_snapshot_produces_exact_declaration_task() -> None:
    source = _source()
    [spec] = tuple(
        GitHubFormalDeclarationHandler(source.source_id).iter_specs(
            source,
            FIXTURE,
            full=False,
        )
    )
    assert spec.task_id == "declarations-111111111111"
    assert spec.family == "formal-proof"
    assert spec.expected["expected_answer"] == '["double","double_zero"]'
    assert spec.readiness == TaskReadiness.PUBLIC_DIAGNOSTIC
    assert spec.oracle_kind == OracleKind.DETERMINISTIC


def test_probe_registers_declaration_supported_github_sources() -> None:
    github_handlers = [
        handler
        for handler in HANDLERS
        if isinstance(handler, GitHubFormalDeclarationHandler)
    ]
    assert len(github_handlers) == 61
    assert len({handler.source_id for handler in github_handlers}) == 61


def test_formal_handler_offline_missing_snapshot_fails_closed(
    tmp_path: Path,
) -> None:
    source = _source()
    with pytest.raises(
        FileNotFoundError,
        match="offline GitHub declaration snapshot missing",
    ):
        GitHubFormalDeclarationHandler(source.source_id).acquire(
            source,
            cache_dir=tmp_path,
            offline=True,
        )
