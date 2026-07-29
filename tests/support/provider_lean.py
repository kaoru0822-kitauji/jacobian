"""Readiness probe for the pinned Lean and Mathlib test runtime."""

PINNED_MATHLIB_RUNTIME_UNAVAILABLE_REASON = (
    "the pinned Lean and Mathlib runtime is unavailable"
)


def pinned_mathlib_runtime_available() -> bool:
    """Return whether the production pinned Lean/Mathlib probe succeeds.

    The implementation is imported lazily so this support module remains safe
    during collection of unit and component tests.
    """

    from jacobian.provider_runtime import lean_provider_runtime

    runtime = lean_provider_runtime(
        profiles={"mathlib": {"mathlib_commit": "pinned"}},
        checker_ids=(),
    )
    return runtime.availability.value == "available"
