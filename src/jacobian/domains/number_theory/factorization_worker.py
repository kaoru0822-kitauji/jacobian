"""Isolated SymPy worker for complete factorization-derived operations."""

from __future__ import annotations

import sys
from collections.abc import Callable

from pydantic import ValidationError

from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.contracts.number_theory import (
    ArithmeticFunctionRequest,
    FactorizationRequest,
)
from jacobian.contracts.results import ContractModel
from jacobian.domains.number_theory.operations import (
    compute_radical,
    decide_squarefree,
    enumerate_divisors,
    enumerate_proper_divisors,
    factorize_primes,
)

PROTOCOL = "jacobian.number-theory.factorization.sympy.v1"

_OPERATIONS: dict[
    str,
    tuple[type[ContractModel], Callable[[ContractModel], ContractModel]],
] = {
    "divisors": (FactorizationRequest, enumerate_divisors),
    "proper_divisors": (FactorizationRequest, enumerate_proper_divisors),
    "prime_factorization": (FactorizationRequest, factorize_primes),
    "squarefree": (ArithmeticFunctionRequest, decide_squarefree),
    "radical": (ArithmeticFunctionRequest, compute_radical),
}


def main() -> int:
    try:
        payload = loads_strict_json(sys.stdin.buffer.read())
        if not isinstance(payload, dict) or set(payload) != {
            "operation",
            "protocol",
            "request",
        }:
            raise ValueError("unexpected worker request fields")
        if payload["protocol"] != PROTOCOL:
            raise ValueError("unsupported worker protocol")
        request_model, operation = _OPERATIONS[payload["operation"]]
        request = request_model.model_validate(payload["request"])
        result = operation(request)
        sys.stdout.buffer.write(
            canonicalize_json(
                {
                    "protocol": PROTOCOL,
                    "result": result.model_dump(mode="json"),
                }
            )
        )
        return 0
    except (KeyError, TypeError, ValueError, ValidationError):
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
