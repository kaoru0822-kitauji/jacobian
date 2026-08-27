"""Typed contracts for p-adic valuation profiles of binomial coefficients."""

from __future__ import annotations

from pydantic import Field
from pydantic_core import PydanticCustomError

from jacobian._models import StrictModel


class BinomialValuationProfileRequest(StrictModel):
    """Parameters for computing v_p(C(n,k)) for all k from 0 to n."""

    n: int = Field(ge=0, le=1000)
    prime: int = Field(ge=2, le=10000)

    def model_post_validate(self) -> None:
        """Validate that prime is actually prime."""
        from sympy import isprime
        if not isprime(self.prime):
            raise ValueError("prime must be a prime number")


class BinomialValuationProfileRow(StrictModel):
    """One (k, v_p(C(n,k))) pair."""

    k: int = Field(ge=0)
    valuation: int = Field(ge=0)


class BinomialValuationProfileResult(StrictModel):
    """Complete v_p(C(n,k)) profile for k=0..n."""

    n: int
    prime: int
    rows: list[BinomialValuationProfileRow]


__all__ = [
    "BinomialValuationProfileRequest",
    "BinomialValuationProfileResult",
    "BinomialValuationProfileRow",
]
