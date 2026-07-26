"""Isolated SymPy worker for rational linear optimization."""

from __future__ import annotations

import json
import sys
from typing import Any


def _rational(value: dict[str, Any]) -> Any:
    import sympy

    return sympy.Rational(int(value["num"]), int(value["den"]))


def _wire(value: Any) -> dict[str, str]:
    import sympy

    rational = sympy.Rational(value)
    return {"num": str(rational.p), "den": str(rational.q)}


def _linear_program(payload: dict[str, Any]) -> dict[str, Any]:
    import sympy
    from sympy.solvers.simplex import (
        InfeasibleLPError,
        UnboundedLPError,
        linprog,
    )

    program = payload["program"]
    objective = sympy.Matrix([[_rational(v) for v in program["objective"]]])
    coefficients = sympy.Matrix(
        [[_rational(value) for value in row] for row in program["coefficients"]]
    )
    rhs = sympy.Matrix([_rational(value) for value in program["rhs"]])
    try:
        primal_value, primal_values = linprog(
            objective,
            A=coefficients.col_join(-coefficients),
            b=rhs.col_join(-rhs),
        )
    except (InfeasibleLPError, UnboundedLPError) as exc:
        return {
            "status": "NO_CERTIFICATE",
            "detail": (
                "SymPy produced no primal candidate; solver status is not a "
                f"certificate: {type(exc).__name__}."
            ),
        }

    primal = sympy.Matrix(primal_values)
    residuals = coefficients * primal - rhs
    primal_payload = {
        "primal_candidate": [_wire(value) for value in primal],
        "primal_objective": _wire(primal_value),
        "primal_residuals": [_wire(value) for value in residuals],
    }
    try:
        negated_dual_value, dual_values = linprog(
            (-rhs).transpose(),
            A=coefficients.transpose(),
            b=objective.transpose(),
            bounds=(None, None),
        )
    except (InfeasibleLPError, UnboundedLPError) as exc:
        return {
            "status": "PRIMAL_ONLY",
            **primal_payload,
            "detail": (
                "SymPy produced a primal candidate but no dual candidate; "
                f"solver status is not a certificate: {type(exc).__name__}."
            ),
        }

    dual = sympy.Matrix(dual_values)
    dual_value = -negated_dual_value
    slacks = objective.transpose() - coefficients.transpose() * dual
    if (
        any(value < 0 for value in primal)
        or any(value != 0 for value in residuals)
        or any(value < 0 for value in slacks)
        or primal_value != dual_value
    ):
        return {
            "status": "PRIMAL_ONLY",
            **primal_payload,
            "detail": (
                "The maintained solver candidates failed the exact "
                "producer-side primal/dual consistency checks."
            ),
        }
    return {
        "status": "CERTIFICATE_PRODUCED",
        **primal_payload,
        "dual_candidate": [_wire(value) for value in dual],
        "dual_objective": _wire(dual_value),
        "dual_slacks": [_wire(value) for value in slacks],
        "certificate_available": True,
        "detail": (
            "SymPy produced exact primal and dual candidates with equal "
            "objective values; independent replay remains required."
        ),
    }


def main() -> int:
    payload = json.loads(sys.stdin.read())
    sys.stdout.write(
        json.dumps(
            _linear_program(payload),
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
