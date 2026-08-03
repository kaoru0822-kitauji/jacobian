"""Check Make and focused-test commands embedded in contributor documentation."""

from __future__ import annotations

import argparse
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCUMENTS = (
    Path("CONTRIBUTING.md"),
    Path("docs/reference/testing-strategy.md"),
    Path("docs/reference/agent-evaluations.md"),
    Path("docs/how-to/author-harbor-benchmark-task.md"),
    Path("docs/how-to/run-agent-evaluations.md"),
)
SHELL_FENCE_LANGUAGES = {"bash", "console", "sh", "shell"}
MAKE_TARGET = re.compile(r"[A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class CommandExample:
    line: int
    text: str
    in_fence: bool


def make_targets(makefile: Path) -> set[str]:
    """Return concrete targets declared by a Makefile."""

    target_names: set[str] = set()
    for line in makefile.read_text(encoding="utf-8").splitlines():
        if line[:1].isspace():
            continue
        name, separator, _ = line.partition(":")
        if separator and MAKE_TARGET.fullmatch(name):
            target_names.add(name)
    return target_names


_REQUIRED_VAR = re.compile(r'@?test\s+-n\s+"\$\((\w+)\)"')
_CHAINED_REQUIRED = re.compile(r'-a\s+-n\s+"\$\((\w+)\)"')


def required_variables(makefile: Path) -> dict[str, set[str]]:
    """Return targets mapped to their unconditionally required variables.

    A variable is required when the recipe begins with one or more
    ``test -n "$(VAR)"`` guards (without ``-o`` alternatives) before any
    conditional ``if`` block or non-test command.  Variables that appear
    inside ``if/else`` branches or have ``-o`` fallbacks are excluded.
    Guards chained with ``-a`` (AND) are all required.
    """

    result: dict[str, set[str]] = {}
    current_target: str | None = None
    recipe_lines: list[str] = []
    for line in makefile.read_text(encoding="utf-8").splitlines():
        if line[:1].isspace():
            if current_target is not None:
                recipe_lines.append(line)
            continue
        if current_target is not None:
            required = _leading_required_vars(recipe_lines)
            if required:
                result[current_target] = required
        name, separator, _ = line.partition(":")
        if separator and MAKE_TARGET.fullmatch(name):
            current_target = name
            recipe_lines = []
        else:
            current_target = None
            recipe_lines = []
    if current_target is not None:
        required = _leading_required_vars(recipe_lines)
        if required:
            result[current_target] = required
    return result


def _leading_required_vars(recipe_lines: list[str]) -> set[str]:
    """Collect required variables from leading test guards in a recipe."""

    required: set[str] = set()
    for line in recipe_lines:
        stripped = line.strip()
        if stripped.startswith(("@if ", "if ")):
            break
        match = _REQUIRED_VAR.match(stripped)
        if not match:
            break
        if " -o " in stripped:
            continue
        required.add(match.group(1))
        for chained in _CHAINED_REQUIRED.finditer(stripped):
            required.add(chained.group(1))
    return required


def _logical_shell_lines(lines: list[tuple[int, str]]) -> list[CommandExample]:
    examples: list[CommandExample] = []
    start_line = 0
    current: list[str] = []
    for line_number, line in lines:
        stripped = line.strip()
        if not current:
            start_line = line_number
        if stripped.endswith("\\"):
            current.append(stripped[:-1].rstrip())
            continue
        current.append(stripped)
        if any("make " in part for part in current):
            examples.append(CommandExample(start_line, " ".join(current), True))
        current = []
    if current and any("make " in part for part in current):
        examples.append(CommandExample(start_line, " ".join(current), True))
    return examples


def command_examples(document: Path) -> list[CommandExample]:
    """Extract shell fenced blocks and inline command examples from Markdown."""

    lines = document.read_text(encoding="utf-8").splitlines()
    examples: list[CommandExample] = []
    in_fence = False
    shell_fence = False
    shell_lines: list[tuple[int, str]] = []
    for line_number, line in enumerate(lines, start=1):
        fence = re.match(r"^\s*```\s*([^\s`]*)\s*$", line)
        if fence:
            if in_fence and shell_fence:
                examples.extend(_logical_shell_lines(shell_lines))
                shell_lines = []
            in_fence = not in_fence
            shell_fence = in_fence and fence.group(1).lower() in SHELL_FENCE_LANGUAGES
            continue
        if in_fence:
            if shell_fence:
                shell_lines.append((line_number, line))
            continue
        for match in re.finditer(r"`([^`\n]+)`", line):
            text = match.group(1)
            if "make " in text:
                examples.append(CommandExample(line_number, text, False))
    return examples


def _is_placeholder(value: str) -> bool:
    return "<" in value or ">" in value or "..." in value or "*" in value


def _commands(tokens: list[str]) -> list[str]:
    found: list[str] = []
    for index, token in enumerate(tokens):
        if token != "make" or index + 1 >= len(tokens):
            continue
        for candidate in tokens[index + 1 :]:
            if candidate.startswith("-"):
                continue
            if "=" in candidate:
                break
            if not MAKE_TARGET.fullmatch(candidate):
                break
            if not _is_placeholder(candidate):
                found.append(candidate)
    return found


def _test_paths(tokens: list[str]) -> list[str]:
    paths: list[str] = []
    for token in tokens:
        if not token.startswith("TESTS="):
            continue
        value = token.removeprefix("TESTS=")
        paths.extend(value.split())
    return paths


def _variable_names(tokens: list[str]) -> set[str]:
    """Extract Make variable names from VAR=value tokens in a command."""

    names: set[str] = set()
    for token in tokens:
        if token.startswith("-") or "=" not in token:
            continue
        key, _, _ = token.partition("=")
        if key.isidentifier():
            names.add(key)
    return names


def _check_example(
    example: CommandExample,
    tokens: list[str],
    targets: set[str],
    required_vars: dict[str, set[str]],
    root: Path,
    document: Path,
) -> list[str]:
    """Return diagnostics for a single command example."""

    failures: list[str] = []
    command_targets = _commands(tokens)
    for target in command_targets:
        if target not in targets:
            failures.append(f"{document}:{example.line}: unknown Make target: {target}")
    if example.in_fence:
        provided_vars = _variable_names(tokens)
        for target in command_targets:
            for var in sorted(required_vars.get(target, set())):
                if var not in provided_vars:
                    failures.append(
                        f"{document}:{example.line}: "
                        f"make target {target} requires {var}"
                    )
    for selector in _test_paths(tokens):
        path = selector.split("::", 1)[0]
        if _is_placeholder(path):
            continue
        candidate = root / path
        if not path.startswith("tests/") or not candidate.is_file():
            failures.append(
                f"{document}:{example.line}: TESTS path does not exist: {path}"
            )
    return failures


def validate_documents(
    root: Path = ROOT,
    documents: tuple[Path, ...] = DEFAULT_DOCUMENTS,
) -> list[str]:
    """Return stable diagnostics for invalid Make targets, TESTS paths, or missing required variables."""

    targets = make_targets(root / "Makefile")
    required_vars = required_variables(root / "Makefile")
    failures: list[str] = []
    for relative_document in documents:
        document = (
            relative_document
            if relative_document.is_absolute()
            else root / relative_document
        )
        if not document.is_file():
            failures.append(f"{document}: document does not exist")
            continue
        for example in command_examples(document):
            try:
                tokens = shlex.split(example.text, comments=True)
            except ValueError as exc:
                failures.append(
                    f"{document}:{example.line}: cannot parse command: {exc}"
                )
                continue
            failures.extend(
                _check_example(example, tokens, targets, required_vars, root, document)
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documents", nargs="*", type=Path)
    args = parser.parse_args()
    documents = tuple(args.documents) or DEFAULT_DOCUMENTS
    failures = validate_documents(documents=documents)
    if failures:
        print("Documentation command failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Documentation Make and TESTS examples are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
