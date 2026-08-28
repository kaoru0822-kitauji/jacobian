"""Isolated Z3 adapter for bounded hypergraph independence kernels."""

from __future__ import annotations

import json
import sys
from typing import Any

from jacobian.math.combinatorics.finite_structures.hypergraphs._independence_z3 import (
    _solve_independence_number_kernel,
)
from jacobian.math.combinatorics.finite_structures.hypergraphs._models import (
    HypergraphIndependenceRequest,
)


def main() -> int:
    try:
        payload: Any = json.loads(sys.stdin.buffer.read())
        if not isinstance(payload, dict):
            raise ValueError("worker payload must be an object")
        kind = payload["kind"]
        if kind == "solve":
            request = HypergraphIndependenceRequest.model_validate(payload["request"])
            result = _solve_independence_number_kernel(request)
            sys.stdout.write(
                json.dumps(
                    result.model_dump(
                        mode="json",
                        exclude={
                            "hypergraph",
                            "hypergraph_digest",
                            "resource_budget",
                        },
                    ),
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            )
            return 0
        raise ValueError("worker payload has invalid kind")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
