"""Independent replay of selected exact rational planar-geometry results.

The checker intentionally depends only on the Python standard library. It does
not import SymPy, Jacobian domain operations, or their computational helpers.
"""

from __future__ import annotations

import hashlib
import json
import re
from fractions import Fraction
from typing import Any

_ARTIFACT_URI = re.compile(r"^artifact://sha256/[0-9a-f]{64}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_INTEGER = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
_ARTIFACT_KEYS = {
    "artifact_uri",
    "object_digest",
    "payload_digest",
    "schema_uri",
    "semantics_uri",
    "parents",
    "payload",
}
_BINDING_KEYS = {
    "claim_digest",
    "semantics_digest",
    "candidate_digest",
    "scope_digest",
    "encoding_digest",
}
_OPERATIONS = {
    "geometry.points.compute.squared_distance",
    "geometry.segment.compute.midpoint",
    "geometry.triangle.compute.orientation",
    "geometry.triangle.compute.centroid",
}


def _reject(detail: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "conclusion": "UNKNOWN",
        "arithmetic": "EXACT_RATIONAL",
        "method": "DIRECT_WITNESS",
        "coverage": "NOT_APPLICABLE",
        "detail": detail,
    }


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _valid_artifact(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != _ARTIFACT_KEYS:
        return False
    parents = value.get("parents")
    return (
        all(
            isinstance(value.get(key), str)
            and (
                _ARTIFACT_URI.fullmatch(value[key]) is not None
                if key in {"artifact_uri", "schema_uri", "semantics_uri"}
                else _DIGEST.fullmatch(value[key]) is not None
            )
            for key in (
                "artifact_uri",
                "object_digest",
                "payload_digest",
                "schema_uri",
                "semantics_uri",
            )
        )
        and isinstance(parents, list)
        and len(parents) == len(set(parents))
        and all(
            isinstance(parent, str) and _ARTIFACT_URI.fullmatch(parent) is not None
            for parent in parents
        )
    )


def _valid_bindings(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == _BINDING_KEYS
        and value["scope_digest"] is None
        and value["encoding_digest"] is None
        and all(
            isinstance(value[key], str) and _DIGEST.fullmatch(value[key]) is not None
            for key in ("claim_digest", "semantics_digest", "candidate_digest")
        )
    )


def _integer(value: object) -> int:
    if not isinstance(value, str) or _INTEGER.fullmatch(value) is None:
        raise ValueError("rational component is not a canonical integer")
    result = int(value)
    if str(result) != value:
        raise ValueError("rational component is not canonical")
    return result


def _rational(value: object) -> Fraction:
    if not isinstance(value, dict) or set(value) != {"num", "den"}:
        raise ValueError("rational value has an invalid shape")
    numerator = _integer(value["num"])
    denominator = _integer(value["den"])
    if denominator <= 0:
        raise ValueError("rational denominator must be positive")
    result = Fraction(numerator, denominator)
    if (result.numerator, result.denominator) != (numerator, denominator):
        raise ValueError("rational value is not reduced")
    return result


def _point(value: object) -> tuple[Fraction, Fraction]:
    if not isinstance(value, dict) or set(value) != {"x", "y"}:
        raise ValueError("point has an invalid shape")
    return _rational(value["x"]), _rational(value["y"])


def _pair(payload: object) -> tuple[tuple[Fraction, Fraction], ...]:
    if not isinstance(payload, dict) or set(payload) != {"first", "second"}:
        raise ValueError("point pair has an invalid shape")
    return _point(payload["first"]), _point(payload["second"])


def _triple(payload: object) -> tuple[tuple[Fraction, Fraction], ...]:
    if not isinstance(payload, dict) or set(payload) != {"first", "second", "third"}:
        raise ValueError("point triple has an invalid shape")
    return (
        _point(payload["first"]),
        _point(payload["second"]),
        _point(payload["third"]),
    )


def _expected(operation: str, claim: object) -> dict[str, object]:
    if operation == "geometry.points.compute.squared_distance":
        first, second = _pair(claim)
        value = (first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2
        return {"value": value}
    if operation == "geometry.segment.compute.midpoint":
        first, second = _pair(claim)
        return {
            "point": (
                (first[0] + second[0]) / 2,
                (first[1] + second[1]) / 2,
            )
        }
    first, second, third = _triple(claim)
    if operation == "geometry.triangle.compute.orientation":
        determinant = (second[0] - first[0]) * (third[1] - first[1]) - (
            second[1] - first[1]
        ) * (third[0] - first[0])
        return {"orientation": (determinant > 0) - (determinant < 0)}
    if operation == "geometry.triangle.compute.centroid":
        return {
            "point": (
                (first[0] + second[0] + third[0]) / 3,
                (first[1] + second[1] + third[1]) / 3,
            )
        }
    raise ValueError("unsupported exact geometry operation")


def _candidate(payload: object, operation: str) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError("candidate has an invalid shape")
    if operation == "geometry.points.compute.squared_distance":
        if set(payload) != {"value"}:
            raise ValueError("squared-distance candidate has an invalid shape")
        return {"value": _rational(payload["value"])}
    if operation in {
        "geometry.segment.compute.midpoint",
        "geometry.triangle.compute.centroid",
    }:
        if set(payload) != {"point"}:
            raise ValueError("point candidate has an invalid shape")
        return {"point": _point(payload["point"])}
    if set(payload) != {"orientation"} or type(payload["orientation"]) is not int:
        raise ValueError("orientation candidate has an invalid shape")
    return {"orientation": payload["orientation"]}


def check_exact_geometry(request: dict[str, Any]) -> dict[str, Any]:
    """Accept a bound result exactly when direct rational replay agrees."""

    try:
        if not isinstance(request, dict) or set(request) != {
            "request_version",
            "claim",
            "candidate",
            "semantics",
            "scope",
            "witness",
            "expected_bindings",
        }:
            return _reject("malformed checker request")
        if request["request_version"] != "1" or request["scope"] is not None:
            return _reject("unsupported checker request")
        claim = request["claim"]
        candidate = request["candidate"]
        semantics = request["semantics"]
        witness = request["witness"]
        if not all(
            _valid_artifact(item) for item in (claim, candidate, semantics, witness)
        ):
            return _reject("checker artifact metadata is malformed")
        bindings = request["expected_bindings"]
        if not _valid_bindings(bindings):
            return _reject("expected evidence bindings are malformed")
        if (
            bindings["claim_digest"] != claim["object_digest"]
            or bindings["candidate_digest"] != candidate["object_digest"]
            or bindings["semantics_digest"] != semantics["object_digest"]
            or semantics["artifact_uri"] != claim["semantics_uri"]
        ):
            return _reject("expected evidence bindings do not match artifacts")
        if (
            claim["semantics_uri"] != candidate["semantics_uri"]
            or claim["semantics_uri"] != witness["semantics_uri"]
            or candidate["parents"] != [claim["artifact_uri"]]
        ):
            return _reject("candidate is not exactly bound to the geometry input")
        for artifact in (claim, candidate, witness):
            if artifact["payload_digest"] != _sha256(
                _canonical_json(artifact["payload"])
            ):
                return _reject("artifact payload digest does not match")
        envelope = witness["payload"]
        if (
            not isinstance(envelope, dict)
            or set(envelope)
            != {
                "evidence_schema_version",
                "witness_format",
                "format_version",
                "role",
                "bindings",
                "payload",
            }
            or envelope["evidence_schema_version"] != "1"
            or envelope["witness_format"] != "geometry.exact_rational_result"
            or envelope["format_version"] != "1"
            or envelope["role"] != "SUPPORTS_CLAIM"
            or envelope["bindings"] != bindings
            or len(witness["parents"]) != 2
            or set(witness["parents"])
            != {claim["artifact_uri"], candidate["artifact_uri"]}
        ):
            return _reject("geometry witness envelope is malformed or rebound")
        payload = envelope["payload"]
        if (
            not isinstance(payload, dict)
            or set(payload) != {"operation_id", "input_uri", "result_uri"}
            or payload["operation_id"] not in _OPERATIONS
            or payload["input_uri"] != claim["artifact_uri"]
            or payload["result_uri"] != candidate["artifact_uri"]
        ):
            return _reject("geometry witness payload is malformed or rebound")
        operation = payload["operation_id"]
        if _candidate(candidate["payload"], operation) != _expected(
            operation, claim["payload"]
        ):
            return _reject("exact rational replay disagrees with the candidate")
        return {
            "accepted": True,
            "conclusion": "TRUE",
            "arithmetic": "EXACT_RATIONAL",
            "method": "DIRECT_WITNESS",
            "coverage": "NOT_APPLICABLE",
            "detail": "direct standard-library rational replay accepted the result",
        }
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        return _reject(str(exc))
