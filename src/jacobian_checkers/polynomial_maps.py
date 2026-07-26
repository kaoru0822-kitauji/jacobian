"""Independent exact replay for sparse rational polynomial-map collisions."""

from __future__ import annotations

import re
from fractions import Fraction
from itertools import permutations
from typing import Any

_INTEGER = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
_VARIABLE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
_MAX_DIMENSION = 4
_MAX_TERMS = 1024
_MAX_SOURCE_EXPONENT = 32
_MAX_DERIVED_EXPONENT = 4 * _MAX_SOURCE_EXPONENT - 1
_MAX_INTERMEDIATE_TERMS = 250_000

Exponent = tuple[int, ...]
Polynomial = dict[Exponent, Fraction]
ParsedPolynomial = tuple[tuple[Fraction, Exponent], ...]


def _reject(detail: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "conclusion": "UNKNOWN",
        "arithmetic": "EXACT_RATIONAL",
        "method": "DIRECT_WITNESS",
        "coverage": "NOT_APPLICABLE",
        "detail": detail,
    }


def _parse_rational(value: object) -> Fraction:
    if not isinstance(value, dict) or set(value) != {"num", "den"}:
        raise ValueError("rational must contain num and den")
    numerator = value["num"]
    denominator = value["den"]
    if (
        not isinstance(numerator, str)
        or not isinstance(denominator, str)
        or _INTEGER.fullmatch(numerator) is None
        or _INTEGER.fullmatch(denominator) is None
    ):
        raise ValueError("rational integers are not canonical")
    parsed = Fraction(int(numerator), int(denominator))
    if str(parsed.numerator) != numerator or str(parsed.denominator) != denominator:
        raise ValueError("rational is not reduced and canonical")
    return parsed


def _parse_point(value: object, dimension: int) -> tuple[Fraction, ...]:
    if not isinstance(value, list) or len(value) != dimension:
        raise ValueError("point dimension does not match the map")
    return tuple(_parse_rational(coordinate) for coordinate in value)


def _parse_map(
    value: object,
) -> tuple[int, tuple[str, ...], tuple[ParsedPolynomial, ...]]:
    if not isinstance(value, dict):
        raise ValueError("candidate map must be an object")
    if value.get("map_schema_version") != "1" or value.get("domain") != "QQ":
        raise ValueError("unsupported polynomial-map semantics")
    variables = value.get("variables")
    coordinates = value.get("coordinates")
    if (
        not isinstance(variables, list)
        or not 1 <= len(variables) <= _MAX_DIMENSION
        or any(
            not isinstance(variable, str) or _VARIABLE.fullmatch(variable) is None
            for variable in variables
        )
        or len(set(variables)) != len(variables)
        or not isinstance(coordinates, list)
        or len(coordinates) != len(variables)
    ):
        raise ValueError("malformed square rational polynomial map")
    dimension = len(variables)
    parsed_coordinates: list[ParsedPolynomial] = []
    for coordinate in coordinates:
        parsed_coordinates.append(
            _parse_polynomial(
                coordinate,
                dimension,
                maximum_exponent=_MAX_SOURCE_EXPONENT,
            )
        )
    return dimension, tuple(variables), tuple(parsed_coordinates)


def _parse_polynomial(
    value: object,
    dimension: int,
    *,
    maximum_exponent: int,
) -> ParsedPolynomial:
    if not isinstance(value, dict) or set(value) != {"terms"}:
        raise ValueError("polynomial coordinate must contain terms")
    terms = value["terms"]
    if not isinstance(terms, list) or len(terms) > _MAX_TERMS:
        raise ValueError("polynomial term list exceeds checker limits")
    parsed_terms: list[tuple[Fraction, Exponent]] = []
    seen: set[Exponent] = set()
    last: Exponent | None = None
    for term in terms:
        if not isinstance(term, dict) or set(term) != {
            "coefficient",
            "exponents",
        }:
            raise ValueError("malformed polynomial term")
        coefficient = _parse_rational(term["coefficient"])
        exponents = term["exponents"]
        if (
            coefficient == 0
            or not isinstance(exponents, list)
            or len(exponents) != dimension
            or any(
                not isinstance(exponent, int)
                or isinstance(exponent, bool)
                or not 0 <= exponent <= maximum_exponent
                for exponent in exponents
            )
        ):
            raise ValueError("invalid polynomial term")
        exponent_tuple = tuple(exponents)
        if exponent_tuple in seen or (last is not None and exponent_tuple >= last):
            raise ValueError("polynomial terms are not in canonical order")
        seen.add(exponent_tuple)
        last = exponent_tuple
        parsed_terms.append((coefficient, exponent_tuple))
    return tuple(parsed_terms)


def _evaluate(
    coordinates: tuple[ParsedPolynomial, ...],
    point: tuple[Fraction, ...],
) -> tuple[Fraction, ...]:
    return tuple(
        sum(
            (
                coefficient * _monomial_value(point, exponents)
                for coefficient, exponents in polynomial
            ),
            start=Fraction(0),
        )
        for polynomial in coordinates
    )


def _monomial_value(
    point: tuple[Fraction, ...],
    exponents: tuple[int, ...],
) -> Fraction:
    result = Fraction(1)
    for value, exponent in zip(point, exponents, strict=True):
        result *= value**exponent
    return result


def check_collision(request: dict[str, Any]) -> dict[str, Any]:
    """Check that two distinct rational points have the same exact map image."""

    try:
        if request.get("request_version") != "1":
            return _reject("unsupported request version")
        claim = request["claim"]["payload"]
        candidate_artifact = request["candidate"]
        if (
            not isinstance(claim, dict)
            or set(claim) != {"claim_schema_version", "predicate", "domain", "map_uri"}
            or claim.get("claim_schema_version") != "1"
            or claim.get("predicate") != "POLYNOMIAL_MAP_INJECTIVE"
            or claim.get("domain") != "QQ"
            or not isinstance(candidate_artifact, dict)
            or claim.get("map_uri") != candidate_artifact.get("artifact_uri")
        ):
            return _reject("unexpected polynomial-map claim")
        witness = request["witness"]["payload"]
        if (
            not isinstance(witness, dict)
            or witness.get("evidence_schema_version") != "1"
            or witness.get("witness_format") != "polynomial.map_collision"
            or witness.get("format_version") != "1"
            or witness.get("role") != "REFUTES_CLAIM"
        ):
            return _reject("unexpected collision witness format or role")
        if witness.get("bindings") != request.get("expected_bindings"):
            return _reject("collision witness bindings do not match")
        dimension, _, coordinates = _parse_map(candidate_artifact["payload"])
        payload = witness.get("payload")
        if not isinstance(payload, dict) or set(payload) != {
            "first_point",
            "second_point",
            "image",
        }:
            return _reject("collision witness payload is malformed")
        first = _parse_point(payload["first_point"], dimension)
        second = _parse_point(payload["second_point"], dimension)
        declared_image = _parse_point(payload["image"], dimension)
        if first == second:
            return _reject("collision points are not distinct")
        first_image = _evaluate(coordinates, first)
        second_image = _evaluate(coordinates, second)
        if first_image != second_image or first_image != declared_image:
            return _reject("declared collision does not replay exactly")
        return {
            "accepted": True,
            "conclusion": "FALSE",
            "arithmetic": "EXACT_RATIONAL",
            "method": "DIRECT_WITNESS",
            "coverage": "NOT_APPLICABLE",
            "detail": (
                "distinct rational points have the same exact polynomial-map image"
            ),
        }
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return _reject("malformed polynomial-map collision request")


def check_jacobian(request: dict[str, Any]) -> dict[str, Any]:
    """Replay a sparse polynomial Jacobian without importing SymPy."""

    try:
        if request.get("request_version") != "1":
            return _reject("unsupported request version")
        claim_artifact = request["claim"]
        candidate_artifact = request["candidate"]
        scope_artifact = request["scope"]
        certificate = request["certificate"]["payload"]
        if (
            not isinstance(claim_artifact, dict)
            or not isinstance(candidate_artifact, dict)
            or not isinstance(scope_artifact, dict)
            or not isinstance(certificate, dict)
        ):
            return _reject("Jacobian replay artifacts are malformed")
        claim = claim_artifact.get("payload")
        candidate = candidate_artifact.get("payload")
        source_map = scope_artifact.get("payload")
        if (
            not isinstance(claim, dict)
            or claim.get("claim_schema_version") != "1"
            or claim.get("predicate") != "EXACT_POLYNOMIAL_JACOBIAN"
        ):
            return _reject("unexpected polynomial Jacobian claim")
        if (
            certificate.get("evidence_schema_version") != "1"
            or certificate.get("certificate_type") != "polynomial.jacobian_replay"
            or certificate.get("format_version") != "1"
            or certificate.get("bindings") != request.get("expected_bindings")
        ):
            return _reject("unexpected Jacobian certificate format or bindings")
        payload = certificate.get("payload")
        if (
            not isinstance(payload, dict)
            or set(payload) != {"method", "source_map_uri", "jacobian_uri"}
            or payload.get("method") != "DIRECT_SPARSE_REPLAY"
        ):
            return _reject("Jacobian replay payload is malformed")
        source_map_uri = scope_artifact.get("artifact_uri")
        jacobian_uri = candidate_artifact.get("artifact_uri")
        if (
            claim.get("source_map_uri") != source_map_uri
            or payload.get("source_map_uri") != source_map_uri
            or payload.get("jacobian_uri") != jacobian_uri
        ):
            return _reject("Jacobian replay artifact identities do not match")
        dimension, variables, coordinates = _parse_map(source_map)
        matrix, determinant = _parse_jacobian_candidate(
            candidate,
            dimension=dimension,
            variables=variables,
            source_map_uri=source_map_uri,
        )
        expected_matrix = tuple(
            tuple(
                _differentiate(_as_polynomial(poly), column)
                for column in range(dimension)
            )
            for poly in coordinates
        )
        if matrix != expected_matrix:
            return _reject("declared Jacobian matrix does not replay exactly")
        if determinant != _determinant(expected_matrix, dimension):
            return _reject("declared Jacobian determinant does not replay exactly")
        return {
            "accepted": True,
            "conclusion": "TRUE",
            "arithmetic": "EXACT_RATIONAL",
            "method": "CHECKED_CERTIFICATE",
            "coverage": "NOT_APPLICABLE",
            "detail": (
                "Jacobian matrix and determinant replayed by independent sparse "
                "rational arithmetic"
            ),
        }
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return _reject("malformed polynomial Jacobian replay request")


def _parse_jacobian_candidate(
    value: object,
    *,
    dimension: int,
    variables: tuple[str, ...],
    source_map_uri: object,
) -> tuple[tuple[tuple[Polynomial, ...], ...], Polynomial]:
    if not isinstance(value, dict) or set(value) != {
        "jacobian_schema_version",
        "map_uri",
        "variable_order",
        "matrix",
        "determinant",
        "backend",
        "backend_version",
    }:
        raise ValueError("malformed polynomial Jacobian candidate")
    matrix = value["matrix"]
    if (
        value["jacobian_schema_version"] != "1"
        or value["map_uri"] != source_map_uri
        or value["variable_order"] != list(variables)
        or value["backend"] != "sympy"
        or not isinstance(value["backend_version"], str)
        or not value["backend_version"]
        or not isinstance(matrix, list)
        or len(matrix) != dimension
        or any(not isinstance(row, list) or len(row) != dimension for row in matrix)
    ):
        raise ValueError("polynomial Jacobian metadata does not match the source")
    parsed_matrix = tuple(
        tuple(
            _as_polynomial(
                _parse_polynomial(
                    entry,
                    dimension,
                    maximum_exponent=_MAX_DERIVED_EXPONENT,
                )
            )
            for entry in row
        )
        for row in matrix
    )
    determinant = _as_polynomial(
        _parse_polynomial(
            value["determinant"],
            dimension,
            maximum_exponent=_MAX_DERIVED_EXPONENT,
        )
    )
    return parsed_matrix, determinant


def _as_polynomial(terms: ParsedPolynomial) -> Polynomial:
    return {exponents: coefficient for coefficient, exponents in terms}


def _differentiate(polynomial: Polynomial, variable: int) -> Polynomial:
    result: Polynomial = {}
    for exponents, coefficient in polynomial.items():
        exponent = exponents[variable]
        if exponent == 0:
            continue
        derived = list(exponents)
        derived[variable] -= 1
        result[tuple(derived)] = coefficient * exponent
    return result


def _multiply(left: Polynomial, right: Polynomial) -> Polynomial:
    if not left or not right:
        return {}
    if len(left) * len(right) > _MAX_INTERMEDIATE_TERMS:
        raise ValueError("polynomial replay exceeds the checker term budget")
    result: Polynomial = {}
    for left_exponents, left_coefficient in left.items():
        for right_exponents, right_coefficient in right.items():
            exponents = tuple(
                left_degree + right_degree
                for left_degree, right_degree in zip(
                    left_exponents, right_exponents, strict=True
                )
            )
            result[exponents] = (
                result.get(exponents, Fraction(0))
                + left_coefficient * right_coefficient
            )
            if result[exponents] == 0:
                del result[exponents]
            if len(result) > _MAX_INTERMEDIATE_TERMS:
                raise ValueError("polynomial replay exceeds the checker term budget")
    return result


def _add_scaled(
    target: Polynomial,
    source: Polynomial,
    scale: int,
) -> Polynomial:
    result = dict(target)
    for exponents, coefficient in source.items():
        result[exponents] = result.get(exponents, Fraction(0)) + scale * coefficient
        if result[exponents] == 0:
            del result[exponents]
    if len(result) > _MAX_INTERMEDIATE_TERMS:
        raise ValueError("polynomial replay exceeds the checker term budget")
    return result


def _determinant(
    matrix: tuple[tuple[Polynomial, ...], ...],
    dimension: int,
) -> Polynomial:
    result: Polynomial = {}
    one = {(0,) * dimension: Fraction(1)}
    for permutation in permutations(range(dimension)):
        term = one
        for row, column in enumerate(permutation):
            term = _multiply(term, matrix[row][column])
        inversions = sum(
            permutation[left] > permutation[right]
            for left in range(dimension)
            for right in range(left + 1, dimension)
        )
        result = _add_scaled(result, term, -1 if inversions % 2 else 1)
    return result
