"""Independent checker declarations for finite-field operations."""

from jacobian.checker_operations import ExactReplayCheckerDeclaration
from jacobian.domains.finite_fields.contracts import LinearMapRankRequest

FINITE_FIELD_EXACT_REPLAY_CHECKERS = (
    ExactReplayCheckerDeclaration(
        "finite_field.linear_map.rank.compute",
        LinearMapRankRequest,
        "check_finite_field_linear_map_rank",
        "finite-field.linear-map-rank.sympy-replay",
        entrypoint_module="jacobian_checkers.finite_field_rank",
        replay_method="SymPy prime-field rank replay",
        reason=(
            "operator-authorized SymPy replay independent of the Python-FLINT producer"
        ),
    ),
)

__all__ = ["FINITE_FIELD_EXACT_REPLAY_CHECKERS"]
