"""Independent exact determinant replay over rational matrices.

This checker intentionally uses only the Python standard library. It does not
import Jacobian contracts, SymPy, or determinant producer code.
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
_MAX_DIMENSION = 32


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
    if (
        not isinstance(value["artifact_uri"], str)
        or _ARTIFACT_URI.fullmatch(value["artifact_uri"]) is None
        or not isinstance(value["object_digest"], str)
        or _DIGEST.fullmatch(value["object_digest"]) is None
        or not isinstance(value["payload_digest"], str)
        or _DIGEST.fullmatch(value["payload_digest"]) is None
        or not isinstance(value["schema_uri"], str)
        or _ARTIFACT_URI.fullmatch(value["schema_uri"]) is None
        or not isinstance(value["semantics_uri"], str)
        or _ARTIFACT_URI.fullmatch(value["semantics_uri"]) is None
    ):
        return False
    parents = value["parents"]
    return (
        isinstance(parents, list)
        and len(parents) == len(set(parents))
        and all(
            isinstance(parent, str) and _ARTIFACT_URI.fullmatch(parent) is not None
            for parent in parents
        )
    )


def _valid_bindings(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != _BINDING_KEYS:
        return False
    if value["scope_digest"] is not None or value["encoding_digest"] is not None:
        return False
    return all(
        isinstance(value[key], str) and _DIGEST.fullmatch(value[key]) is not None
        for key in ("claim_digest", "semantics_digest", "candidate_digest")
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
    if result.numerator != numerator or result.denominator != denominator:
        raise ValueError("rational value is not reduced")
    return result


def _matrix(payload: object) -> list[list[Fraction]]:
    if not isinstance(payload, dict) or set(payload) != {
        "matrix_schema_version",
        "domain",
        "entries",
    }:
        raise ValueError("rational matrix has an invalid shape")
    if payload["matrix_schema_version"] != "1" or payload["domain"] != "QQ":
        raise ValueError("rational matrix uses unsupported semantics")
    entries = payload["entries"]
    if (
        not isinstance(entries, list)
        or not 1 <= len(entries) <= _MAX_DIMENSION
        or not isinstance(entries[0], list)
        or len(entries[0]) != len(entries)
        or any(not isinstance(row, list) or len(row) != len(entries) for row in entries)
    ):
        raise ValueError("determinant requires a bounded square matrix")
    return [[_rational(value) for value in row] for row in entries]


def _candidate(
    payload: object,
    *,
    claim: dict[str, Any],
    candidate: dict[str, Any],
) -> Fraction:
    if not isinstance(payload, dict) or set(payload) != {
        "result_schema_version",
        "matrix_uri",
        "determinant",
        "method",
        "backend",
        "backend_version",
    }:
        raise ValueError("determinant candidate has an invalid shape")
    if (
        payload["result_schema_version"] != "1"
        or payload["matrix_uri"] != claim["artifact_uri"]
        or payload["method"] != "FRACTION_FREE_BAREISS"
        or payload["backend"] != "sympy"
        or not isinstance(payload["backend_version"], str)
        or not payload["backend_version"]
        or candidate["parents"] != [claim["artifact_uri"]]
    ):
        raise ValueError("determinant candidate is not bound to the source matrix")
    return _rational(payload["determinant"])


def _determinant(matrix: list[list[Fraction]]) -> Fraction:
    """Exact Gaussian-elimination determinant with explicit row swaps."""

    work = [row[:] for row in matrix]
    determinant = Fraction(1)
    for column in range(len(work)):
        pivot_row = next(
            (row for row in range(column, len(work)) if work[row][column] != 0),
            None,
        )
        if pivot_row is None:
            return Fraction(0)
        if pivot_row != column:
            work[column], work[pivot_row] = work[pivot_row], work[column]
            determinant = -determinant
        pivot = work[column][column]
        determinant *= pivot
        for row in range(column + 1, len(work)):
            multiplier = work[row][column] / pivot
            for target_column in range(column + 1, len(work)):
                work[row][target_column] -= multiplier * work[column][target_column]
            work[row][column] = Fraction(0)
    return determinant


def check_rational_determinant(request: dict[str, Any]) -> dict[str, Any]:
    """Accept only a fully bound candidate equal to an exact independent replay."""

    try:
        if not isinstance(request, dict) or set(request) != {
            "request_version",
            "claim",
            "candidate",
            "scope",
            "witness",
            "expected_bindings",
        }:
            return _reject("malformed checker request")
        if request["request_version"] != "1" or request["scope"] is not None:
            return _reject("unsupported checker request")
        claim = request["claim"]
        candidate = request["candidate"]
        witness = request["witness"]
        if not all(_valid_artifact(item) for item in (claim, candidate, witness)):
            return _reject("checker artifact metadata is malformed")
        expected_bindings = request["expected_bindings"]
        if not _valid_bindings(expected_bindings):
            return _reject("expected evidence bindings are malformed")
        if (
            claim["semantics_uri"] != candidate["semantics_uri"]
            or claim["semantics_uri"] != witness["semantics_uri"]
        ):
            return _reject("checker artifacts use different semantics")
        for artifact, label in (
            (claim, "source matrix"),
            (candidate, "determinant candidate"),
            (witness, "determinant witness"),
        ):
            if artifact["payload_digest"] != _sha256(
                _canonical_json(artifact["payload"])
            ):
                return _reject(f"{label} payload digest does not match")

        matrix = _matrix(claim["payload"])
        declared = _candidate(
            candidate["payload"],
            claim=claim,
            candidate=candidate,
        )
        if (
            expected_bindings["claim_digest"] != claim["object_digest"]
            or expected_bindings["candidate_digest"] != candidate["object_digest"]
        ):
            return _reject("expected evidence bindings do not match artifacts")
        envelope = witness["payload"]
        if not isinstance(envelope, dict) or set(envelope) != {
            "evidence_schema_version",
            "witness_format",
            "format_version",
            "role",
            "bindings",
            "payload",
        }:
            return _reject("determinant witness envelope is malformed")
        if (
            envelope["evidence_schema_version"] != "1"
            or envelope["witness_format"] != "matrix.rational_determinant"
            or envelope["format_version"] != "1"
            or envelope["role"] != "SUPPORTS_CLAIM"
            or envelope["bindings"] != expected_bindings
        ):
            return _reject("determinant witness envelope is not exactly bound")
        if envelope["payload"] != {
            "matrix_uri": claim["artifact_uri"],
            "determinant_uri": candidate["artifact_uri"],
        }:
            return _reject("determinant witness points at different artifacts")
        if len(witness["parents"]) != 2 or set(witness["parents"]) != {
            claim["artifact_uri"],
            candidate["artifact_uri"],
        }:
            return _reject("determinant witness is missing required lineage")

        computed = _determinant(matrix)
        if computed != declared:
            return _reject("declared determinant does not match exact recomputation")
        return {
            "accepted": True,
            "conclusion": "TRUE",
            "arithmetic": "EXACT_RATIONAL",
            "method": "DIRECT_WITNESS",
            "coverage": "NOT_APPLICABLE",
            "detail": (
                f"recomputed the determinant exactly for the full "
                f"{len(matrix)} by {len(matrix)} rational matrix"
            ),
        }
    except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError):
        return _reject("malformed checker request")
