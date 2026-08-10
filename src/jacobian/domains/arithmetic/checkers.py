"""Independent checker declarations owned by exact arithmetic."""

from jacobian.checker_operations import ExactReplayCheckerDeclaration
from jacobian.contracts.arithmetic import RealQuadraticOrderRequest

ARITHMETIC_EXACT_REPLAY_CHECKERS = (
    ExactReplayCheckerDeclaration(
        "arithmetic.real_quadratic.order.compute",
        RealQuadraticOrderRequest,
        "check_real_quadratic_order",
        "arithmetic.real-quadratic-order.fraction-square-replay",
        entrypoint_module="jacobian_checkers.real_quadratic",
        replay_method="standard-library Fraction and integer-square replay",
        reason=(
            "operator-authorized standard-library checker independently compares "
            "opposing real-quadratic terms without importing SymPy or producer code"
        ),
    ),
)


__all__ = ["ARITHMETIC_EXACT_REPLAY_CHECKERS"]
