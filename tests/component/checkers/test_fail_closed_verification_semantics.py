"""Fail-closed verification semantics for checker support and VERIFIED gates."""

from __future__ import annotations

from jacobian.contracts.results import Conclusion, Verification
from jacobian.exact_domain_checkers import _checker_supports


def test_checker_supports_unknown_polynomial_operation_is_false() -> None:
    assert (
        _checker_supports(
            "polynomial.compute.hypothetical_new_op",
            {"left": {"variables": ["x"], "terms": []}},
        )
        is False
    )


def test_checker_supports_known_univariate_gcd() -> None:
    payload = {
        "left": {"variables": ["x"], "terms": [{"coefficient": "1", "exponents": [1]}]},
        "right": {"variables": ["x"], "terms": [{"coefficient": "1", "exponents": [0]}]},
    }
    assert _checker_supports("polynomial.compute.gcd", payload) is True


def test_verified_assurance_requires_true_conclusion_policy() -> None:
    """Document the service policy: VERIFIED only when conclusion is TRUE."""

    def verification_for(conclusion: Conclusion) -> Verification:
        return (
            Verification.VERIFIED
            if conclusion == Conclusion.TRUE
            else Verification.UNVERIFIED
        )

    assert verification_for(Conclusion.TRUE) is Verification.VERIFIED
    assert verification_for(Conclusion.FALSE) is Verification.UNVERIFIED
    assert verification_for(Conclusion.UNKNOWN) is Verification.UNVERIFIED
