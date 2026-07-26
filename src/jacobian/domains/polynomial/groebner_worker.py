"""Isolated SymPy worker for one bounded Gröbner-basis computation."""

from __future__ import annotations

import sys

from pydantic import ValidationError

from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.contracts.polynomial_operations import PolynomialGroebnerBasisRequest
from jacobian.domains.polynomial.operations import polynomial_groebner_basis

PROTOCOL = "jacobian.polynomial.groebner.sympy.v1"


def main() -> int:
    try:
        payload = loads_strict_json(sys.stdin.buffer.read())
        if not isinstance(payload, dict) or set(payload) != {"protocol", "request"}:
            raise ValueError("unexpected worker request fields")
        if payload["protocol"] != PROTOCOL:
            raise ValueError("unsupported worker protocol")
        request = PolynomialGroebnerBasisRequest.model_validate(payload["request"])
        result = polynomial_groebner_basis(request)
        sys.stdout.buffer.write(
            canonicalize_json(
                {
                    "protocol": PROTOCOL,
                    "result": result.model_dump(mode="json"),
                }
            )
        )
        return 0
    except (TypeError, ValueError, ValidationError):
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
