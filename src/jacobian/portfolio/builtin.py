"""The explicit built-in Jacobian mathematical portfolio."""

from jacobian.domains.builtins import build_builtin_domain_bundles
from jacobian.portfolio.model import PortfolioPlan


def build_builtin_portfolio() -> PortfolioPlan:
    """Build one fresh ordered portfolio from domain-owned factories."""

    return PortfolioPlan(domain_bundles=build_builtin_domain_bundles())


__all__ = ["build_builtin_portfolio"]
