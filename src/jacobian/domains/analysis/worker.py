"""Isolated Arb worker for validated real-function enclosures."""

from __future__ import annotations

import sys
from typing import Any

from pydantic import ValidationError

from jacobian.canonical import (
    CanonicalizationError,
    canonicalize_json,
    loads_strict_json,
)


def _point_enclosure(payload: dict[str, Any]) -> dict[str, Any]:
    from flint import arb, ctx, fmpq

    argument = payload["argument"]
    with ctx.workprec(int(payload["precision_bits"])):
        value = arb(fmpq(int(argument["num"]), int(argument["den"])))
        result = getattr(value, str(payload["function"]).lower())()
        if not result.is_finite():
            return {"status": "NONFINITE"}
        lower_mantissa, lower_exponent = result.lower().man_exp()
        upper_mantissa, upper_exponent = result.upper().man_exp()
        exact = bool(result.is_exact())
        return {
            "status": "ENCLOSED",
            "lower": {
                "mantissa": str(lower_mantissa),
                "exponent": int(lower_exponent),
            },
            "upper": {
                "mantissa": str(upper_mantissa),
                "exponent": int(upper_exponent),
            },
            "relative_accuracy_bits": (
                None if exact else int(result.rel_accuracy_bits())
            ),
            "exact": exact,
        }


def main() -> int:
    try:
        payload = loads_strict_json(sys.stdin.buffer.read())
        if not isinstance(payload, dict):
            raise ValueError("analysis worker request must be an object")
        result = _point_enclosure(payload)
    except (CanonicalizationError, TypeError, ValueError, ValidationError):
        sys.stderr.write("validated analysis worker request or execution failed\n")
        return 2
    sys.stdout.buffer.write(canonicalize_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
