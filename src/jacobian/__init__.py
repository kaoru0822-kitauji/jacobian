"""Jacobian mathematical capability runtime."""

from importlib.metadata import PackageNotFoundError, version

from jacobian.contracts.results import ResultEnvelope

__all__ = ["ResultEnvelope"]

try:
    __version__ = version("jacobian")
except PackageNotFoundError:  # pragma: no cover - only an unpackaged source tree
    __version__ = "0+unknown"
