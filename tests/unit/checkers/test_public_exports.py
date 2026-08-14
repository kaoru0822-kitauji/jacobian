from __future__ import annotations

from types import ModuleType

from jacobian_checkers import exact_domain_operations, polynomial_maps


def _public_exports(module: ModuleType) -> tuple[str, ...]:
    return tuple(module.__all__)


def test_polynomial_map_checker_exports_are_explicit() -> None:
    assert _public_exports(polynomial_maps) == (
        "check_collision",
        "check_collision_refutes_inverse",
        "check_identity",
        "check_jacobian",
        "check_keller_condition",
        "check_map_inverse",
    )


def test_exact_domain_checker_exports_include_modular_residue_replay() -> None:
    assert "check_modular_polynomial_residue_image" in _public_exports(
        exact_domain_operations
    )
