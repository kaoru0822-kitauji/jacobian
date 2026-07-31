"""Isolated SymPy worker for complete factorization-derived operations."""

from __future__ import annotations

import sys
from collections.abc import Callable

from pydantic import ValidationError

from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.contracts.number_theory import (
    ArithmeticFunctionRequest,
    FactorizationRequest,
    PowerfulNumberRequest,
)
from jacobian.contracts.results import ContractModel
from jacobian.domains.number_theory.operations import (
    compute_radical,
    decide_powerful,
    decide_squarefree,
    enumerate_divisors,
    enumerate_proper_divisors,
    factorize_primes,
)

PROTOCOL = "jacobian.number-theory.factorization.sympy.v1"


def _validated_operation[
    RequestT: ContractModel,
    ResultT: ContractModel,
](
    request_model: type[RequestT],
    operation: Callable[[RequestT], ResultT],
) -> Callable[[object], ResultT]:
    def invoke(payload: object) -> ResultT:
        return operation(request_model.model_validate(payload))

    return invoke


_OPERATIONS: dict[str, Callable[[object], ContractModel]] = {
    "divisors": _validated_operation(FactorizationRequest, enumerate_divisors),
    "proper_divisors": _validated_operation(
        FactorizationRequest, enumerate_proper_divisors
    ),
    "prime_factorization": _validated_operation(FactorizationRequest, factorize_primes),
    "powerful": _validated_operation(PowerfulNumberRequest, decide_powerful),
    "squarefree": _validated_operation(ArithmeticFunctionRequest, decide_squarefree),
    "radical": _validated_operation(ArithmeticFunctionRequest, compute_radical),
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
        operation = _OPERATIONS[payload["operation"]]
        result = operation(payload["request"])
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
