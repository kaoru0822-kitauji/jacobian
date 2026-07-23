## Problem
<!-- What issue does this PR address? Link the relevant issue. -->

## Solution
<!-- What change does this PR introduce? Summarize the approach. -->

## Testing
<!-- How was this change tested? List the exact commands and any manual verification. -->

```sh
uv sync --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv build
```

## Trust & Compatibility Impact
<!-- Does this change affect the verification kernel, checker registry, artifact format, or public API? Reference docs/threat-model.md if relevant. -->

## Checklist
- [ ] Tests pass locally (`uv run pytest`)
- [ ] Linting passes (`uv run ruff check .`)
- [ ] Type checking passes (`uv run mypy`)
- [ ] Formatting passes (`uv run ruff format --check .`)
- [ ] Build succeeds (`uv build`)
- [ ] Relevant documentation updated
