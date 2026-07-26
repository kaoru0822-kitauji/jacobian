"""Isolated Arb worker for validated real-function enclosures."""

from __future__ import annotations

import json
import sys
from typing import Any


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
    payload = json.loads(sys.stdin.read())
    sys.stdout.write(
        json.dumps(
            _point_enclosure(payload),
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
