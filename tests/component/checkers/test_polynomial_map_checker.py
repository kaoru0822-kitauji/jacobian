from __future__ import annotations

from copy import deepcopy
from typing import Any

from jacobian_checkers.polynomial_maps import (
    check_collision,
    check_identity,
    check_jacobian,
)


def _request() -> dict[str, Any]:
    bindings = {
        "claim_digest": "sha256:" + "1" * 64,
        "semantics_digest": "sha256:" + "2" * 64,
        "candidate_digest": "sha256:" + "3" * 64,
        "scope_digest": None,
        "encoding_digest": None,
    }
    map_uri = "artifact://sha256/" + "5" * 64
    return {
        "request_version": "1",
        "claim": {
            "artifact_uri": "artifact://sha256/" + "4" * 64,
            "payload": {
                "claim_schema_version": "1",
                "predicate": "POLYNOMIAL_MAP_INJECTIVE",
                "domain": "QQ",
                "map_uri": map_uri,
            },
        },
        "candidate": {
            "artifact_uri": map_uri,
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
        },
        "witness": {
            "artifact_uri": "artifact://sha256/" + "6" * 64,
            "payload": {
                "evidence_schema_version": "1",
                "witness_format": "polynomial.map_collision",
                "format_version": "1",
                "role": "REFUTES_CLAIM",
                "bindings": deepcopy(bindings),
                "payload": {
                    "first_point": [{"num": "-1", "den": "1"}],
                    "second_point": [{"num": "1", "den": "1"}],
                    "image": [{"num": "1", "den": "1"}],
                },
            },
        },
        "expected_bindings": deepcopy(bindings),
    }


def test_collision_checker_accepts_exact_distinct_preimages() -> None:
    decision = check_collision(_request())

    assert decision["accepted"] is True
    assert decision["conclusion"] == "FALSE"
    assert decision["relation_id"] == (
        "polynomial.relation.collision-refutes-injectivity"
    )


def test_collision_checker_rejects_equal_points() -> None:
    request = _request()
    request["witness"]["payload"]["payload"]["second_point"] = [
        {"num": "-1", "den": "1"}
    ]

    decision = check_collision(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_collision_checker_recomputes_instead_of_trusting_declared_image() -> None:
    request = _request()
    forged = deepcopy(request)
    forged["witness"]["payload"]["payload"]["image"] = [{"num": "2", "den": "1"}]

    decision = check_collision(forged)

    assert decision["accepted"] is False


def test_collision_checker_rejects_a_different_map_than_the_claim() -> None:
    request = _request()
    request["candidate"]["artifact_uri"] = "artifact://sha256/" + "6" * 64

    decision = check_collision(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_collision_checker_rejects_noncanonical_rationals() -> None:
    request = _request()
    request["witness"]["payload"]["payload"]["first_point"] = [
        {"num": "-2", "den": "2"}
    ]

    decision = check_collision(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_collision_checker_rejects_binding_substitution() -> None:
    request = _request()
    request["witness"]["payload"]["bindings"]["candidate_digest"] = "sha256:" + "9" * 64

    decision = check_collision(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def _identity_request() -> dict[str, Any]:
    bindings = {
        "claim_digest": "sha256:" + "1" * 64,
        "semantics_digest": "sha256:" + "2" * 64,
        "candidate_digest": "sha256:" + "3" * 64,
        "scope_digest": "sha256:" + "4" * 64,
        "encoding_digest": None,
    }
    left_uri = "artifact://sha256/" + "5" * 64
    right_uri = "artifact://sha256/" + "6" * 64
    polynomial = {
        "terms": [
            {
                "coefficient": {"num": "2", "den": "3"},
                "exponents": [2, 0],
            },
            {
                "coefficient": {"num": "-1", "den": "1"},
                "exponents": [0, 1],
            },
        ]
    }
    return {
        "request_version": "1",
        "claim": {
            "payload": {
                "claim_schema_version": "1",
                "predicate": "POLYNOMIAL_IDENTITY",
                "domain": "QQ",
                "variables": ["x", "y"],
                "left_uri": left_uri,
                "right_uri": right_uri,
            }
        },
        "scope": {
            "artifact_uri": left_uri,
            "payload": {
                "polynomial_schema_version": "1",
                "domain": "QQ",
                "variables": ["x", "y"],
                "polynomial": deepcopy(polynomial),
            },
        },
        "candidate": {
            "artifact_uri": right_uri,
            "payload": {
                "polynomial_schema_version": "1",
                "domain": "QQ",
                "variables": ["x", "y"],
                "polynomial": deepcopy(polynomial),
            },
        },
        "certificate": {
            "payload": {
                "evidence_schema_version": "1",
                "certificate_type": "polynomial.identity_replay",
                "format_version": "1",
                "bindings": deepcopy(bindings),
                "payload_digest": "sha256:" + "7" * 64,
                "payload": {
                    "method": "DIRECT_SPARSE_REPLAY",
                    "variables": ["x", "y"],
                    "left_uri": left_uri,
                    "right_uri": right_uri,
                },
            }
        },
        "expected_bindings": deepcopy(bindings),
    }


def test_identity_checker_accepts_equal_exact_polynomials() -> None:
    decision = check_identity(_identity_request())

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"
    assert decision["relationship_source_artifact_uris"] == [
        "artifact://sha256/" + "5" * 64
    ]
    assert decision["relationship_target_artifact_uris"] == [
        "artifact://sha256/" + "6" * 64
    ]


def test_identity_checker_verifies_a_nonidentity_as_false() -> None:
    request = _identity_request()
    request["candidate"]["payload"]["polynomial"]["terms"][0]["coefficient"] = {
        "num": "5",
        "den": "7",
    }

    decision = check_identity(request)

    assert decision["accepted"] is True
    assert decision["conclusion"] == "FALSE"
    assert "relation_id" not in decision
    assert "relationship_source_artifact_uris" not in decision
    assert "relationship_target_artifact_uris" not in decision


def test_identity_checker_rejects_candidate_substitution() -> None:
    request = _identity_request()
    request["candidate"]["artifact_uri"] = "artifact://sha256/" + "8" * 64

    decision = check_identity(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_identity_checker_rejects_polynomial_ring_substitution() -> None:
    request = _identity_request()
    request["candidate"]["payload"]["variables"] = ["y", "x"]

    decision = check_identity(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_identity_checker_rejects_unrelated_supporting_artifact() -> None:
    request = _identity_request()
    request["supporting_artifacts"] = [
        {
            "artifact_uri": "artifact://sha256/" + "9" * 64,
            "object_digest": "sha256:" + "9" * 64,
            "schema_uri": "artifact://sha256/" + "a" * 64,
            "semantics_uri": "artifact://sha256/" + "b" * 64,
            "payload": {},
        }
    ]

    decision = check_identity(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def _jacobian_request() -> dict[str, Any]:
    bindings = {
        "claim_digest": "sha256:" + "a" * 64,
        "semantics_digest": "sha256:" + "b" * 64,
        "candidate_digest": "sha256:" + "c" * 64,
        "scope_digest": "sha256:" + "d" * 64,
        "encoding_digest": None,
    }
    map_uri = "artifact://sha256/" + "1" * 64
    jacobian_uri = "artifact://sha256/" + "2" * 64
    return {
        "request_version": "1",
        "claim": {
            "payload": {
                "claim_schema_version": "1",
                "predicate": "EXACT_POLYNOMIAL_JACOBIAN",
                "source_map_uri": map_uri,
            }
        },
        "scope": {
            "artifact_uri": map_uri,
            "payload": {
                "map_schema_version": "1",
                "domain": "QQ",
                "variables": ["x", "y"],
                "coordinates": [
                    {
                        "terms": [
                            {
                                "coefficient": {"num": "1", "den": "1"},
                                "exponents": [2, 0],
                            }
                        ]
                    },
                    {
                        "terms": [
                            {
                                "coefficient": {"num": "1", "den": "1"},
                                "exponents": [0, 1],
                            }
                        ]
                    },
                ],
            },
        },
        "candidate": {
            "artifact_uri": jacobian_uri,
            "payload": {
                "jacobian_schema_version": "1",
                "map_uri": map_uri,
                "variable_order": ["x", "y"],
                "matrix": [
                    [
                        {
                            "terms": [
                                {
                                    "coefficient": {"num": "2", "den": "1"},
                                    "exponents": [1, 0],
                                }
                            ]
                        },
                        {"terms": []},
                    ],
                    [
                        {"terms": []},
                        {
                            "terms": [
                                {
                                    "coefficient": {"num": "1", "den": "1"},
                                    "exponents": [0, 0],
                                }
                            ]
                        },
                    ],
                ],
                "determinant": {
                    "terms": [
                        {
                            "coefficient": {"num": "2", "den": "1"},
                            "exponents": [1, 0],
                        }
                    ]
                },
                "backend": "sympy",
                "backend_version": "1.14.0",
            },
        },
        "certificate": {
            "payload": {
                "evidence_schema_version": "1",
                "certificate_type": "polynomial.jacobian_replay",
                "format_version": "1",
                "bindings": deepcopy(bindings),
                "payload_digest": "sha256:" + "e" * 64,
                "payload": {
                    "method": "DIRECT_SPARSE_REPLAY",
                    "source_map_uri": map_uri,
                    "jacobian_uri": jacobian_uri,
                },
            }
        },
        "expected_bindings": deepcopy(bindings),
    }


def test_jacobian_checker_replays_matrix_and_determinant() -> None:
    decision = check_jacobian(_jacobian_request())

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"
    assert decision["method"] == "CHECKED_CERTIFICATE"


def test_jacobian_checker_rejects_forged_determinant() -> None:
    request = _jacobian_request()
    request["candidate"]["payload"]["determinant"]["terms"][0]["coefficient"] = {
        "num": "3",
        "den": "1",
    }

    decision = check_jacobian(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"
