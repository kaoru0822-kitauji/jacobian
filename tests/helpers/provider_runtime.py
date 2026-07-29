from __future__ import annotations

from functools import lru_cache

from jacobian_checkers import lean4

PINNED_MATHLIB_RUNTIME_UNAVAILABLE_REASON = (
    "the pinned Lean and Mathlib runtime is unavailable"
)


@lru_cache(maxsize=1)
def pinned_mathlib_runtime_available() -> bool:
    """Return whether the exact pinned Lean and Mathlib runtime is usable."""

    try:
        lean4.inspect_runtime(require_mathlib=True)
    except (OSError, RuntimeError):
        return False
    return True
