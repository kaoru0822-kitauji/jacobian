"""Isolated maintained-backend workers for bounded validated analysis."""

from __future__ import annotations

import json
import sys
from typing import Any


def _arb_point(payload: dict[str, Any]) -> dict[str, Any]:
    from flint import arb, ctx, fmpq

    argument = payload["argument"]
    with ctx.workprec(int(payload["precision_bits"])):
        value = arb(fmpq(int(argument["num"]), int(argument["den"])))
        function = str(payload["function"]).lower()
        result = getattr(value, function)()
        if not result.is_finite():
            return {"status": "NONFINITE"}
        lower_mantissa, lower_exponent = result.lower().man_exp()
        upper_mantissa, upper_exponent = result.upper().man_exp()
        accuracy = int(result.rel_accuracy_bits())
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
            "relative_accuracy_bits": None if exact else accuracy,
            "exact": exact,
        }


def _sympy_rational(value: dict[str, Any]) -> Any:
    import sympy

    return sympy.Rational(int(value["num"]), int(value["den"]))


def _wire_sympy_rational(value: Any) -> dict[str, str]:
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
    objective_values = [_sympy_rational(value) for value in program["objective"]]
    objective = sympy.Matrix([objective_values])
    objective_column = objective.transpose()
    coefficients = sympy.Matrix(
        [[_sympy_rational(value) for value in row] for row in program["coefficients"]]
    )
    rhs = sympy.Matrix([_sympy_rational(value) for value in program["rhs"]])

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
                "SymPy did not produce a primal candidate; its solver status "
                f"is not a certificate: {type(exc).__name__}."
            ),
        }

    primal = sympy.Matrix(primal_values)
    primal_residuals = coefficients * primal - rhs
    primal_payload = {
        "primal_candidate": [_wire_sympy_rational(value) for value in primal],
        "primal_objective": _wire_sympy_rational(primal_value),
        "primal_residuals": [_wire_sympy_rational(value) for value in primal_residuals],
    }

    try:
        negated_dual_value, dual_values = linprog(
            (-rhs).transpose(),
            A=coefficients.transpose(),
            b=objective_column,
            bounds=(None, None),
        )
    except (InfeasibleLPError, UnboundedLPError) as exc:
        return {
            "status": "PRIMAL_ONLY",
            **primal_payload,
            "detail": (
                "SymPy produced a primal candidate but no dual candidate; "
                f"its solver status is not a certificate: {type(exc).__name__}."
            ),
        }

    dual = sympy.Matrix(dual_values)
    dual_value = -negated_dual_value
    dual_slacks = objective_column - coefficients.transpose() * dual
    if (
        any(value < 0 for value in primal)
        or any(value != 0 for value in primal_residuals)
        or any(value < 0 for value in dual_slacks)
        or primal_value != dual_value
    ):
        return {
            "status": "PRIMAL_ONLY",
            **primal_payload,
            "detail": (
                "The maintained solver candidates did not satisfy the exact "
                "producer-side primal/dual consistency checks."
            ),
        }
    return {
        "status": "CERTIFICATE_PRODUCED",
        **primal_payload,
        "dual_candidate": [_wire_sympy_rational(value) for value in dual],
        "dual_objective": _wire_sympy_rational(dual_value),
        "dual_slacks": [_wire_sympy_rational(value) for value in dual_slacks],
        "certificate_available": True,
        "detail": (
            "SymPy produced exact primal and dual candidates with equal objective "
            "values; independent replay remains required."
        ),
    }


def main() -> int:
    request = json.loads(sys.stdin.read())
    operation = request["operation"]
    payload = request["payload"]
    if operation == "arb_point":
        result = _arb_point(payload)
    elif operation == "linear_program":
        result = _linear_program(payload)
    else:
        raise ValueError("unsupported validated-analysis worker operation")
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
