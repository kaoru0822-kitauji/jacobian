"""Standard-library-only replay of bounded Nullstellensatz identities."""

from __future__ import annotations

import json
import re
from fractions import Fraction
from typing import Any

_INTEGER = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
_VARIABLES = (
    "a20",
    "a11",
    "a02",
    "b20",
    "b11",
    "b02",
    "b30",
    "b21",
    "b12",
    "b03",
    "t",
)
_QUADRATIC = ("a20", "a11", "a02")
_CUBIC = ("b30", "b21", "b12", "b03")
_GENERATOR_IDS = (
    "j30",
    "j21",
    "j12",
    "j03",
    "j20",
    "j11",
    "j02",
    "j10",
    "j01",
    "rabinowitsch",
)
_MAX_EXPONENT = 32
_MAX_TERMS_PER_POLYNOMIAL = 1024
_MAX_TERMS_PER_CHART = 4096
_MAX_TERMS_PER_BUNDLE = 16384
_MAX_COEFFICIENT_DIGITS = 256
_MAX_CERTIFICATE_BYTES = 2_000_000

type Polynomial = dict[tuple[int, ...], Fraction]


def _reject(detail: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "conclusion": "UNKNOWN",
        "arithmetic": "EXACT_RATIONAL",
        "method": "CHECKED_CERTIFICATE",
        "coverage": "NOT_APPLICABLE",
        "detail": detail,
    }


def _rational(value: object) -> Fraction:
    if not isinstance(value, dict) or set(value) != {"num", "den"}:
        raise ValueError("rational must contain only num and den")
    numerator = value["num"]
    denominator = value["den"]
    if (
        not isinstance(numerator, str)
        or not isinstance(denominator, str)
        or _INTEGER.fullmatch(numerator) is None
        or _INTEGER.fullmatch(denominator) is None
        or len(numerator.lstrip("-")) > _MAX_COEFFICIENT_DIGITS
        or len(denominator) > _MAX_COEFFICIENT_DIGITS
    ):
        raise ValueError("invalid bounded rational")
    parsed = Fraction(int(numerator), int(denominator))
    if str(parsed.numerator) != numerator or str(parsed.denominator) != denominator:
        raise ValueError("rational is not canonical")
    return parsed


def _polynomial(value: object, dimension: int) -> Polynomial:
    if not isinstance(value, dict) or set(value) != {"terms"}:
        raise ValueError("polynomial must contain only terms")
    terms = value["terms"]
    if not isinstance(terms, list) or len(terms) > _MAX_TERMS_PER_POLYNOMIAL:
        raise ValueError("polynomial term limit exceeded")
    result: Polynomial = {}
    previous: tuple[int, ...] | None = None
    for term in terms:
        if not isinstance(term, dict) or set(term) != {"coefficient", "exponents"}:
            raise ValueError("malformed polynomial term")
        coefficient = _rational(term["coefficient"])
        exponents = term["exponents"]
        if (
            coefficient == 0
            or not isinstance(exponents, list)
            or len(exponents) != dimension
            or any(
                not isinstance(exponent, int)
                or isinstance(exponent, bool)
                or not 0 <= exponent <= _MAX_EXPONENT
                for exponent in exponents
            )
            or sum(exponents) > _MAX_EXPONENT
        ):
            raise ValueError("invalid polynomial term")
        exponent_tuple = tuple(exponents)
        if previous is not None and exponent_tuple >= previous:
            raise ValueError("polynomial terms are not canonical")
        previous = exponent_tuple
        result[exponent_tuple] = coefficient
    return result


def _add(left: Polynomial, right: Polynomial) -> Polynomial:
    result = dict(left)
    for exponent, coefficient in right.items():
        value = result.get(exponent, Fraction(0)) + coefficient
        if value:
            result[exponent] = value
        else:
            result.pop(exponent, None)
    return result


def _multiply(left: Polynomial, right: Polynomial) -> Polynomial:
    result: Polynomial = {}
    for left_exponents, left_coefficient in left.items():
        for right_exponents, right_coefficient in right.items():
            exponents = tuple(
                a + b for a, b in zip(left_exponents, right_exponents, strict=True)
            )
            if sum(exponents) > 2 * _MAX_EXPONENT:
                raise ValueError("identity expansion exponent limit exceeded")
            result[exponents] = (
                result.get(exponents, Fraction(0))
                + left_coefficient * right_coefficient
            )
            if result[exponents] == 0:
                del result[exponents]
            if len(result) > _MAX_TERMS_PER_CHART:
                raise ValueError("identity expansion term limit exceeded")
    return result


def _mono(**powers: int) -> tuple[int, ...]:
    return tuple(powers.get(variable, 0) for variable in _VARIABLES)


def _expected_base() -> dict[str, Polynomial]:
    return {
        "j30": {_mono(a20=1, b21=1): Fraction(2), _mono(a11=1, b30=1): Fraction(-3)},
        "j21": {
            _mono(a20=1, b12=1): Fraction(4),
            _mono(a11=1, b21=1): Fraction(-1),
            _mono(a02=1, b30=1): Fraction(-6),
        },
        "j12": {
            _mono(a20=1, b03=1): Fraction(6),
            _mono(a11=1, b12=1): Fraction(1),
            _mono(a02=1, b21=1): Fraction(-4),
        },
        "j03": {_mono(a11=1, b03=1): Fraction(3), _mono(a02=1, b12=1): Fraction(-2)},
        "j20": {
            _mono(b21=1): Fraction(1),
            _mono(a20=1, b11=1): Fraction(2),
            _mono(a11=1, b20=1): Fraction(-2),
        },
        "j11": {
            _mono(b12=1): Fraction(2),
            _mono(a20=1, b02=1): Fraction(4),
            _mono(a02=1, b20=1): Fraction(-4),
        },
        "j02": {
            _mono(b03=1): Fraction(3),
            _mono(a11=1, b02=1): Fraction(2),
            _mono(a02=1, b11=1): Fraction(-2),
        },
        "j10": {_mono(b11=1): Fraction(1), _mono(a20=1): Fraction(2)},
        "j01": {_mono(b02=1): Fraction(2), _mono(a11=1): Fraction(1)},
    }


def _named_polynomials(value: object) -> tuple[tuple[str, Polynomial], ...]:
    if not isinstance(value, list) or len(value) != 10:
        raise ValueError("each chart must contain ten generators")
    parsed = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"polynomial_id", "polynomial"}:
            raise ValueError("malformed named polynomial")
        polynomial_id = item["polynomial_id"]
        if not isinstance(polynomial_id, str):
            raise ValueError("generator ID must be a string")
        parsed.append((polynomial_id, _polynomial(item["polynomial"], len(_VARIABLES))))
    if tuple(item[0] for item in parsed) != _GENERATOR_IDS:
        raise ValueError("unexpected generator order")
    return tuple(parsed)


def _validate_system_chart(
    chart: object,
    expected_base: dict[str, Polynomial],
) -> tuple[str, tuple[tuple[str, Polynomial], ...]]:
    if not isinstance(chart, dict) or set(chart) != {
        "chart_id",
        "selected_quadratic_coefficient",
        "selected_cubic_coefficient",
        "variables",
        "generators",
    }:
        raise ValueError("malformed system chart")
    quadratic = chart["selected_quadratic_coefficient"]
    cubic = chart["selected_cubic_coefficient"]
    chart_id = chart["chart_id"]
    if quadratic not in _QUADRATIC or cubic not in _CUBIC:
        raise ValueError("invalid system chart coordinate")
    if chart_id != f"{quadratic}-{cubic}" or chart["variables"] != list(_VARIABLES):
        raise ValueError("invalid system chart identity")
    generators = _named_polynomials(chart["generators"])
    if any(
        polynomial != expected_base[generator_id]
        for generator_id, polynomial in generators[:-1]
    ):
        raise ValueError("system generator differs from the frozen slice")
    if generators[-1][1] != {
        _mono(t=1, **{quadratic: 1, cubic: 1}): Fraction(1),
        _mono(): Fraction(-1),
    }:
        raise ValueError("incorrect Rabinowitsch chart generator")
    return chart_id, generators


def _validate_system(value: object) -> dict[str, tuple[tuple[str, Polynomial], ...]]:
    if not isinstance(value, dict):
        raise ValueError("system payload must be an object")
    required = {
        "system_schema_version",
        "statement_id",
        "coefficient_domain",
        "source_characteristic",
        "component_degrees",
        "normalization",
        "chart_encoding",
        "chart_count",
        "charts",
    }
    if set(value) != required:
        raise ValueError("unexpected system fields")
    header = (
        value["system_schema_version"],
        value["statement_id"],
        value["coefficient_domain"],
        value["source_characteristic"],
        value["component_degrees"],
        value["normalization"],
        value["chart_encoding"],
        value["chart_count"],
    )
    expected_header = (
        "1",
        "normalized-bivariate-jacobian-degree-2-3",
        "QQ",
        "0",
        [2, 3],
        "F(0)=0;JF(0)=I;det(JF)=1",
        "rabinowitsch-product-cover",
        12,
    )
    charts = value["charts"]
    if header != expected_header or not isinstance(charts, list) or len(charts) != 12:
        raise ValueError("unsupported normalized Jacobian system")
    parsed = dict(_validate_system_chart(chart, _expected_base()) for chart in charts)
    if len(parsed) != 12 or set(parsed) != {
        f"{a}-{b}" for a in _QUADRATIC for b in _CUBIC
    }:
        raise ValueError("incomplete or duplicate chart cover")
    return parsed


def _validate_bundle(value: object, claim: dict[str, Any]) -> list[object]:
    if not isinstance(value, dict) or set(value) != {
        "certificate_schema_version",
        "certificate_format",
        "format_version",
        "coefficient_domain",
        "system_uri",
        "system_digest",
        "producer",
        "producer_version",
        "producer_digest",
        "charts",
    }:
        raise ValueError("unexpected certificate bundle fields")
    binding = (
        value["certificate_schema_version"],
        value["certificate_format"],
        value["format_version"],
        value["coefficient_domain"],
        value["system_uri"],
        value["system_digest"],
    )
    expected = (
        "1",
        "polynomial.nullstellensatz.chart-cover",
        "1",
        "QQ",
        claim["artifact_uri"],
        claim["object_digest"],
    )
    charts = value["charts"]
    if binding != expected or not isinstance(charts, list) or len(charts) != 12:
        raise ValueError("certificate is not bound to the exact system")
    return charts


def _validate_envelope(
    certificate: object,
    claim: dict[str, Any],
    candidate: dict[str, Any],
) -> None:
    if not isinstance(certificate, dict):
        raise ValueError("certificate envelope must be an object")
    metadata = (certificate.get("certificate_type"), certificate.get("format_version"))
    expected_payload = {
        "system_uri": claim["artifact_uri"],
        "certificate_bundle_uri": candidate["artifact_uri"],
    }
    if metadata != ("polynomial.nullstellensatz.chart-cover", "1"):
        raise ValueError("unexpected certificate envelope format")
    if certificate.get("payload") != expected_payload:
        raise ValueError("unexpected certificate envelope payload")


def _replay_multipliers(
    generators: tuple[tuple[str, Polynomial], ...],
    multipliers: list[object],
) -> tuple[Polynomial, int]:
    identity: Polynomial = {}
    term_count = 0
    for (generator_id, generator), record in zip(generators, multipliers, strict=True):
        if not isinstance(record, dict) or set(record) != {
            "generator_id",
            "multiplier",
        }:
            raise ValueError("malformed multiplier record")
        if record["generator_id"] != generator_id:
            raise ValueError("multiplier is not paired with its generator")
        multiplier = _polynomial(record["multiplier"], len(_VARIABLES))
        term_count += len(multiplier)
        identity = _add(identity, _multiply(multiplier, generator))
    return identity, term_count


def _check_chart_identity(
    chart: object,
    system: dict[str, tuple[tuple[str, Polynomial], ...]],
) -> tuple[str, int]:
    if not isinstance(chart, dict) or set(chart) != {
        "chart_id",
        "variable_order",
        "generators",
        "multipliers",
        "identity_rhs",
    }:
        raise ValueError("malformed chart certificate")
    chart_id = chart["chart_id"]
    if chart_id not in system or chart["variable_order"] != list(_VARIABLES):
        raise ValueError("wrong chart or variable order")
    generators = _named_polynomials(chart["generators"])
    multipliers = chart["multipliers"]
    if generators != system[chart_id]:
        raise ValueError("certificate generator differs from bound system")
    if not isinstance(multipliers, list) or len(multipliers) != 10:
        raise ValueError("each generator requires one multiplier")
    identity, chart_terms = _replay_multipliers(generators, multipliers)
    if chart_terms > _MAX_TERMS_PER_CHART:
        raise ValueError("chart multiplier term limit exceeded")
    if _rational(chart["identity_rhs"]) != 1:
        raise ValueError("identity right-hand side is not one")
    if identity != {(0,) * len(_VARIABLES): Fraction(1)}:
        raise ValueError("sum(h_i*f_i) is not one")
    return chart_id, chart_terms


def _accepted(
    claim: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "accepted": True,
        "conclusion": "TRUE",
        "arithmetic": "EXACT_RATIONAL",
        "method": "CHECKED_CERTIFICATE",
        "coverage": "EXHAUSTIVE",
        "detail": "all 12 exact chart identities independently replay to one",
        "relation_id": "polynomial.relation.infeasibility-certificate-for",
        "relationship_source_artifact_uris": [candidate["artifact_uri"]],
        "relationship_target_artifact_uris": [claim["artifact_uri"]],
    }


def check_chart_cover(request: dict[str, Any]) -> dict[str, Any]:
    """Check all 12 bound identities without producer or Gröbner code."""

    try:
        if request.get("request_version") != "1" or request.get("scope") is not None:
            raise ValueError("unsupported checker request envelope")
        claim = request["claim"]
        candidate = request["candidate"]
        candidate_bytes = json.dumps(
            candidate["payload"], sort_keys=True, separators=(",", ":")
        ).encode()
        if len(candidate_bytes) > _MAX_CERTIFICATE_BYTES:
            raise ValueError("certificate byte limit exceeded")
        system = _validate_system(claim["payload"])
        charts = _validate_bundle(candidate["payload"], claim)
        _validate_envelope(request["certificate"]["payload"], claim, candidate)
        checked = [_check_chart_identity(chart, system) for chart in charts]
        seen = {chart_id for chart_id, _term_count in checked}
        total_terms = sum(term_count for _chart_id, term_count in checked)
        if len(seen) != 12 or total_terms > _MAX_TERMS_PER_BUNDLE:
            raise ValueError("certificate does not exhaust the bounded chart cover")
        return _accepted(claim, candidate)
    except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError):
        return _reject("malformed or oversized Nullstellensatz certificate")


__all__ = ["check_chart_cover"]
