from __future__ import annotations

from copy import deepcopy
from typing import Any

from jacobian_checkers.polynomial_intervals import check_enclosure


def _rational(num: str, den: str = "1") -> dict[str, str]:
    return {"num": num, "den": den}


def _term(coefficient: int, exponent: int) -> dict[str, Any]:
    return {
        "coefficient": _rational(str(coefficient)),
        "exponents": [exponent],
    }


def _polynomial(variable: str, terms: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "polynomial_schema_version": "1",
        "domain": "QQ",
        "variable": variable,
        "polynomial": {"terms": terms},
    }


def _interval(lo: str, hi: str) -> dict[str, Any]:
    return {"interval_schema_version": "1", "lo": _rational(lo), "hi": _rational(hi)}


def _request(
    *,
    polynomial: dict[str, Any],
    interval: dict[str, Any],
    bernstein_coefficients: list[dict[str, str]],
    lo: str,
    hi: str,
    degree: int,
) -> dict[str, Any]:
    bindings = {
        "claim_digest": "sha256:" + "1" * 64,
        "semantics_digest": "sha256:" + "2" * 64,
        "candidate_digest": "sha256:" + "3" * 64,
        "scope_digest": "sha256:" + "4" * 64,
        "encoding_digest": None,
    }
    polynomial_uri = "artifact://sha256/" + "5" * 64
    enclosure_uri = "artifact://sha256/" + "6" * 64
    return {
        "request_version": "1",
        "claim": {
            "payload": {
                "claim_schema_version": "1",
                "predicate": "POLYNOMIAL_INTERVAL_BERNSTEIN_ENCLOSURE",
                "domain": "QQ",
                "polynomial_uri": polynomial_uri,
                "interval": deepcopy(interval),
            }
        },
        "scope": {
            "artifact_uri": polynomial_uri,
            "payload": polynomial,
        },
        "candidate": {
            "artifact_uri": enclosure_uri,
            "payload": {
                "enclosure_schema_version": "1",
                "polynomial_uri": polynomial_uri,
                "interval": deepcopy(interval),
                "degree": degree,
                "bernstein_coefficients": deepcopy(bernstein_coefficients),
                "lo": _rational(lo),
                "hi": _rational(hi),
                "backend": "sympy",
                "backend_version": "1.14.0",
            },
        },
        "certificate": {
            "payload": {
                "evidence_schema_version": "1",
                "certificate_type": ("polynomial.interval_bernstein_enclosure_replay"),
                "format_version": "1",
                "bindings": deepcopy(bindings),
                "payload_digest": "sha256:" + "0" * 64,
                "payload": {
                    "method": "BERNSTEIN_COEFFICIENT_REPLAY",
                    "polynomial_uri": polynomial_uri,
                    "interval": deepcopy(interval),
                    "degree": degree,
                    "bernstein_coefficients": deepcopy(bernstein_coefficients),
                    "lo": _rational(lo),
                    "hi": _rational(hi),
                },
            }
        },
        "expected_bindings": deepcopy(bindings),
    }


def test_enclosure_checker_accepts_a_valid_linear_polynomial() -> None:
    # p(x) = 2x + 1 on [0, 1]; Bernstein coefficients (degree 1) are [1, 3].
    request = _request(
        polynomial=_polynomial("x", [_term(2, 1), _term(1, 0)]),
        interval=_interval("0", "1"),
        bernstein_coefficients=[_rational("1"), _rational("3")],
        lo="1",
        hi="3",
        degree=1,
    )

    decision = check_enclosure(request)

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"
    assert decision["relation_id"] == "polynomial.relation.valid-bernstein-enclosure"
    assert decision["relationship_source_artifact_uris"] == [
        "artifact://sha256/" + "6" * 64
    ]
    assert decision["relationship_target_artifact_uris"] == [
        "artifact://sha256/" + "5" * 64
    ]
    assert "obligation_uri" not in decision


def test_enclosure_checker_accepts_a_quadratic_on_a_shifted_interval() -> None:
    # p(x) = x^2 on [-1, 1]; shifted q(t) = (2t - 1)^2 = 1 - 4t + 4t^2.
    # Bernstein coefficients (degree 2): b_0 = 1, b_1 = 1 - 4*(1/2) = -1,
    # b_2 = 1 - 4 + 4 = 1. Enclosure [-1, 1] is a valid bound (exact range is [0,1]).
    request = _request(
        polynomial=_polynomial("x", [_term(1, 2)]),
        interval=_interval("-1", "1"),
        bernstein_coefficients=[_rational("1"), _rational("-1"), _rational("1")],
        lo="-1",
        hi="1",
        degree=2,
    )

    decision = check_enclosure(request)

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"


def test_enclosure_checker_refutes_wrong_bernstein_coefficients() -> None:
    request = _request(
        polynomial=_polynomial("x", [_term(2, 1), _term(1, 0)]),
        interval=_interval("0", "1"),
        bernstein_coefficients=[_rational("0"), _rational("3")],
        lo="0",
        hi="3",
        degree=1,
    )

    decision = check_enclosure(request)

    assert decision["accepted"] is True
    assert decision["conclusion"] == "FALSE"
    assert "relation_id" not in decision


def test_enclosure_checker_rejects_bounds_not_matching_coefficients() -> None:
    request = _request(
        polynomial=_polynomial("x", [_term(2, 1), _term(1, 0)]),
        interval=_interval("0", "1"),
        bernstein_coefficients=[_rational("1"), _rational("3")],
        lo="0",
        hi="3",
        degree=1,
    )

    decision = check_enclosure(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_enclosure_checker_rejects_candidate_replay_mismatch() -> None:
    request = _request(
        polynomial=_polynomial("x", [_term(2, 1), _term(1, 0)]),
        interval=_interval("0", "1"),
        bernstein_coefficients=[_rational("1"), _rational("3")],
        lo="1",
        hi="3",
        degree=1,
    )
    request["candidate"]["payload"]["bernstein_coefficients"][0] = _rational("0")

    decision = check_enclosure(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_enclosure_checker_rejects_noncanonical_rational() -> None:
    request = _request(
        polynomial=_polynomial("x", [_term(2, 1), _term(1, 0)]),
        interval=_interval("0", "1"),
        bernstein_coefficients=[_rational("1"), _rational("3")],
        lo="1",
        hi="3",
        degree=1,
    )
    request["candidate"]["payload"]["lo"] = _rational("2", "2")

    decision = check_enclosure(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_enclosure_checker_rejects_degenerate_interval() -> None:
    request = _request(
        polynomial=_polynomial("x", [_term(1, 0)]),
        interval=_interval("1", "1"),
        bernstein_coefficients=[_rational("1")],
        lo="1",
        hi="1",
        degree=0,
    )

    decision = check_enclosure(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_enclosure_checker_rejects_wrong_degree() -> None:
    request = _request(
        polynomial=_polynomial("x", [_term(1, 2)]),
        interval=_interval("0", "1"),
        bernstein_coefficients=[_rational("0"), _rational("1")],
        lo="0",
        hi="1",
        degree=1,
    )

    decision = check_enclosure(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"
