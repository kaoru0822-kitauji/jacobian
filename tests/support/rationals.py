"""Small builders for exact rational payloads used across test lanes."""

from __future__ import annotations


def rational_payload(
    numerator: int | str,
    denominator: int | str = 1,
) -> dict[str, str]:
    return {"num": str(numerator), "den": str(denominator)}
