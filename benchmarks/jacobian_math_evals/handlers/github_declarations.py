"""Pinned formal-declaration extraction from GitHub repositories."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import urllib.parse
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..models import (
    OracleKind,
    SourceRecord,
    Split,
    TaskReadiness,
    TaskSpec,
)

MAX_SOURCE_BYTES = 131_072
MAX_CANDIDATE_FILES = 40
EXCLUDED_PARTS = frozenset(
    {
        ".git",
        ".lake",
        "build",
        "deps",
        "dist",
        "generated",
        "lake-packages",
        "node_modules",
        "vendor",
    }
)

LANGUAGES = {
    ".lean": "lean",
    ".v": "rocq",
    ".thy": "isabelle",
    ".agda": "agda",
    ".mm": "metamath",
    ".ml": "hol-light",
}

PATTERNS = {
    "lean": re.compile(
        r"(?m)^\s*(?:private\s+|protected\s+|noncomputable\s+)*"
        r"(?:theorem|lemma|def|abbrev|structure|inductive|class)\s+"
        r"([A-Za-z_][A-Za-z0-9_'.]*)"
    ),
    "rocq": re.compile(
        r"(?m)^\s*(?:Theorem|Lemma|Fact|Corollary|Proposition|Definition|"
        r"Fixpoint|Inductive|Record|Class)\s+([A-Za-z_][A-Za-z0-9_']*)"
    ),
    "isabelle": re.compile(
        r"(?m)^\s*(?:theorem|lemma|corollary|proposition|definition|fun|"
        r"primrec|datatype|locale)\s+([A-Za-z_][A-Za-z0-9_'.]*)"
    ),
    "agda": re.compile(r"(?m)^\s*(?:data|record|postulate)\s+([A-Za-z_][^\s:]*)"),
    "metamath": re.compile(r"(?m)^\s*([A-Za-z0-9_.-]+)\s+\$(?:a|p)\s+"),
    "hol-light": re.compile(
        r"(?m)^\s*let\s+([a-zA-Z_][a-zA-Z0-9_']*)\s*=\s*(?:prove|new_definition)"
    ),
}


class NoFormalDeclarationsError(ValueError):
    """Repository snapshot has no bounded declaration-bearing source file."""


def _repo_name(source: SourceRecord) -> str:
    parts = urllib.parse.urlparse(source.canonical_url).path.strip("/").split("/")
    if len(parts) < 2:
        raise ValueError(f"not a GitHub repository URL: {source.canonical_url}")
    return "/".join(parts[:2]).removesuffix(".git")


def _gh_json(args: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        ["gh", "api", *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
    value: Any = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError("GitHub API returned non-object JSON")
    return value


def _gh_bytes(args: list[str]) -> bytes:
    result = subprocess.run(
        ["gh", "api", *args, "-H", "Accept: application/vnd.github.raw+json"],
        check=True,
        capture_output=True,
        timeout=90,
    )
    return result.stdout


def declarations(language: str, content: str) -> tuple[str, ...]:
    pattern = PATTERNS.get(language)
    if pattern is None:
        raise ValueError(f"unsupported formal language: {language}")
    values = pattern.findall(content)
    return tuple(dict.fromkeys(values))


def _candidate_paths(tree: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    items = tree.get("tree")
    if not isinstance(items, list):
        raise ValueError("GitHub tree response lacks tree")
    candidates: list[tuple[str, str]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "blob":
            continue
        path = item.get("path")
        size = item.get("size")
        if (
            not isinstance(path, str)
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size <= 0
            or size > MAX_SOURCE_BYTES
        ):
            continue
        parts = Path(path).parts
        if EXCLUDED_PARTS.intersection(parts):
            continue
        language = LANGUAGES.get(Path(path).suffix.lower())
        if language is not None:
            candidates.append((path, language))
    return tuple(sorted(candidates)[:MAX_CANDIDATE_FILES])


class GitHubFormalDeclarationHandler:
    """Create exact declaration tasks from one immutable repository snapshot."""

    def __init__(self, source_id: str) -> None:
        self.source_id = source_id

    def acquire(
        self,
        source: SourceRecord,
        *,
        cache_dir: Path,
        offline: bool,
    ) -> Path:
        if source.source_id != self.source_id:
            raise ValueError(f"handler does not own {source.source_id}")
        if source.immutable_revision is None:
            raise ValueError("GitHub source lacks immutable revision")
        destination = cache_dir / source.source_id / "formal-declarations.json"
        digest_path = destination.with_suffix(".sha256")
        if destination.exists() and digest_path.exists():
            actual = hashlib.sha256(destination.read_bytes()).hexdigest()
            expected = digest_path.read_text(encoding="utf-8").strip()
            if actual != expected:
                raise ValueError("cached GitHub declaration snapshot digest mismatch")
            return destination
        if offline:
            raise FileNotFoundError(
                f"offline GitHub declaration snapshot missing: {destination}"
            )
        repo = _repo_name(source)
        tree = _gh_json(
            [
                "--method",
                "GET",
                f"repos/{repo}/git/trees/{source.immutable_revision}",
                "-f",
                "recursive=1",
            ]
        )
        selected: dict[str, Any] | None = None
        for path, language in _candidate_paths(tree):
            payload = _gh_bytes(
                [
                    "--method",
                    "GET",
                    f"repos/{repo}/contents/{path}",
                    "-f",
                    f"ref={source.immutable_revision}",
                ]
            )
            try:
                content = payload.decode("utf-8")
            except UnicodeDecodeError:
                continue
            found = declarations(language, content)
            if found:
                selected = {
                    "source_id": source.source_id,
                    "repository": repo,
                    "revision": source.immutable_revision,
                    "path": path,
                    "language": language,
                    "content": content,
                    "content_sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
                    "declarations": list(found),
                }
                break
        if selected is None:
            raise NoFormalDeclarationsError(
                "no bounded formal source file contains recognized declarations"
            )
        payload = (
            json.dumps(
                selected,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode()
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".tmp")
        temporary.write_bytes(payload)
        temporary.replace(destination)
        digest_path.write_text(
            hashlib.sha256(payload).hexdigest() + "\n",
            encoding="utf-8",
        )
        return destination

    def iter_specs(
        self,
        source: SourceRecord,
        snapshot: Path,
        *,
        full: bool,
    ) -> Iterator[TaskSpec]:
        del full
        value: Any = json.loads(snapshot.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("GitHub declaration snapshot must be an object")
        language = value.get("language")
        content = value.get("content")
        expected_declarations = value.get("declarations")
        if (
            not isinstance(language, str)
            or not isinstance(content, str)
            or not isinstance(expected_declarations, list)
            or not expected_declarations
            or declarations(language, content) != tuple(expected_declarations)
        ):
            raise ValueError("GitHub declaration snapshot fails parser replay")
        snapshot_sha = hashlib.sha256(snapshot.read_bytes()).hexdigest()
        answer = json.dumps(
            expected_declarations,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        yield TaskSpec(
            task_id=f"declarations-{source.source_id[4:]}",
            family=(
                "formal-library" if source.kind == "formal_library" else "formal-proof"
            ),
            source_ids=(source.source_id,),
            split=Split.PUBLIC,
            instruction=(
                f"Inspect `{value['path']}`, a frozen {language} source file. "
                "List every top-level declaration recognized by the task's stated "
                "language grammar, in source order without duplicates. Write the "
                "compact JSON array to the `answer` field of `submission.json`. "
                "This public source task measures declaration discovery, not proof "
                "validity or theorem assurance."
            ),
            keywords=(
                "mathematics",
                "formal-library",
                "declaration",
                language,
                "public-diagnostic",
            ),
            scored=False,
            instance={
                "source_id": source.source_id,
                "repository": value["repository"],
                "revision": value["revision"],
                "path": value["path"],
                "language": language,
                "content": content,
                "content_sha256": value["content_sha256"],
                "snapshot_sha256": f"sha256:{snapshot_sha}",
                "contamination": "PUBLIC_ANSWER_DERIVABLE",
            },
            expected={
                "answer_visible": True,
                "expected_answer": answer,
                "maximum_assurance": "UNVERIFIED",
                "source_revision": source.immutable_revision,
                "snapshot_sha256": f"sha256:{snapshot_sha}",
            },
            admissible_for_publish=source.access_state.value == "public",
            readiness=TaskReadiness.PUBLIC_DIAGNOSTIC,
            oracle_kind=OracleKind.DETERMINISTIC,
            limitations=(
                "public answer-derivable declaration inventory",
                "parser replay does not establish proof correctness",
            ),
        )
