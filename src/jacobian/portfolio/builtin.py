"""The explicit built-in Jacobian mathematical portfolio."""

from jacobian.domains.builtins import BUILTIN_DOMAIN_BUNDLES
from jacobian.portfolio.model import PortfolioPlan

BUILTIN_PORTFOLIO = PortfolioPlan(domain_bundles=BUILTIN_DOMAIN_BUNDLES)
