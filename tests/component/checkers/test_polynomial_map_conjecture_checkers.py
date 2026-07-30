from __future__ import annotations

from copy import deepcopy
from typing import Any

from jacobian_checkers.polynomial_maps import (
    check_collision_refutes_inverse,
    check_keller_condition,
)


def _bindings() -> dict[str, str | None]:
    return {
        "claim_digest": "sha256:" + "1" * 64,
        "semantics_digest": "sha256:" + "2" * 64,
        "candidate_digest": "sha256:" + "3" * 64,
        "scope_digest": "sha256:" + "4" * 64,
        "encoding_digest": None,
    }


def _map(uri: str, *, square: bool = False) -> dict[str, Any]:
    if square:
        return {
            "artifact_uri": uri,
            "payload": {
                "map_schema_version": "1",
                "domain": "QQ",
                "variables": ["x"],
                "coordinates": [
                    {
                        "terms": [
                            {
                                "coefficient": {"num": "1", "den": "1"},
                                "exponents": [2],
                            }
                        ]
                    }
                ],
            },
        }
    return {
        "artifact_uri": uri,
        "payload": {
            "map_schema_version": "1",
            "domain": "QQ",
            "variables": ["x"],
            "coordinates": [
                {
                    "terms": [
                        {
                            "coefficient": {"num": "1", "den": "1"},
                            "exponents": [1],
                        }
                    ]
                }
            ],
        },
    }


def _keller_request() -> dict[str, Any]:
    bindings = _bindings()
    map_uri = "artifact://sha256/" + "5" * 64
    jacobian_uri = "artifact://sha256/" + "6" * 64
    claim_uri = "artifact://sha256/" + "7" * 64
    certificate_uri = "artifact://sha256/" + "8" * 64
    jacobian = {
        "artifact_uri": jacobian_uri,
        "payload": {
            "jacobian_schema_version": "1",
            "map_uri": map_uri,
            "variable_order": ["x"],
            "matrix": [
                [
                    {
                        "terms": [
                            {
                                "coefficient": {"num": "1", "den": "1"},
                                "exponents": [0],
                            }
                        ]
                    }
                ]
            ],
            "determinant": {
                "terms": [
                    {
                        "coefficient": {"num": "1", "den": "1"},
                        "exponents": [0],
                    }
                ]
            },
            "backend": "sympy",
            "backend_version": "1",
        },
    }
    replay = {
        "method": "DIRECT_SPARSE_KELLER_REPLAY",
        "map_uri": map_uri,
        "jacobian_uri": jacobian_uri,
    }
    return {
        "request_version": "1",
        "claim": {
            "artifact_uri": claim_uri,
            "payload": {
                "claim_schema_version": "1",
                "predicate": "POLYNOMIAL_MAP_KELLER_CONDITION",
                "domain": "QQ",
                "map_uri": map_uri,
                "jacobian_uri": jacobian_uri,
            },
        },
        "scope": _map(map_uri),
        "candidate": jacobian,
        "certificate": {
            "artifact_uri": certificate_uri,
            "payload": {
                "evidence_schema_version": "1",
                "certificate_type": "polynomial.map.keller_condition.replay",
                "format_version": "1",
                "bindings": bindings,
                "payload_digest": "sha256:" + "9" * 64,
                "payload": replay,
            },
        },
        "expected_bindings": bindings,
    }


def _inverse_obstruction_request() -> dict[str, Any]:
    bindings = _bindings()
    map_uri = "artifact://sha256/" + "5" * 64
    claim_uri = "artifact://sha256/" + "6" * 64
    witness_uri = "artifact://sha256/" + "7" * 64
    return {
        "request_version": "1",
        "claim": {
            "artifact_uri": claim_uri,
            "payload": {
                "claim_schema_version": "1",
                "predicate": "POLYNOMIAL_MAP_NO_TWO_SIDED_INVERSE",
                "domain": "QQ",
                "map_uri": map_uri,
            },
        },
        "candidate": _map(map_uri, square=True),
        "witness": {
            "artifact_uri": witness_uri,
            "payload": {
                "evidence_schema_version": "1",
                "witness_format": "polynomial.map_collision_refutes_inverse",
                "format_version": "1",
                "role": "REFUTES_CLAIM",
                "bindings": bindings,
                "payload": {
                    "first_point": [{"num": "-1", "den": "1"}],
                    "second_point": [{"num": "1", "den": "1"}],
                    "image": [{"num": "1", "den": "1"}],
                },
            },
        },
        "expected_bindings": bindings,
    }


def test_keller_checker_replays_constant_jacobian() -> None:
    decision = check_keller_condition(_keller_request())

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"
    assert decision["relation_id"] == "polynomial.relation.keller-condition"


def test_keller_checker_rejects_a_forged_jacobian() -> None:
    request = _keller_request()
    forged = deepcopy(request)
    forged["candidate"]["payload"]["determinant"]["terms"][0]["coefficient"] = {
        "num": "2",
        "den": "1",
    }

    decision = check_keller_condition(forged)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_collision_checker_binds_collision_to_inverse_obstruction() -> None:
    decision = check_collision_refutes_inverse(_inverse_obstruction_request())

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"
    assert decision["relation_id"] == (
        "polynomial.relation.collision-refutes-two-sided-inverse"
    )


def test_collision_checker_does_not_trust_declared_image() -> None:
    request = _inverse_obstruction_request()
    forged = deepcopy(request)
    forged["witness"]["payload"]["payload"]["image"] = [{"num": "2", "den": "1"}]

    decision = check_collision_refutes_inverse(forged)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"
