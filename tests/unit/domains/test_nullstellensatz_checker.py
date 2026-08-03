from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from tests.support.nullstellensatz import load_chart_certificates

from jacobian.contracts.nullstellensatz import NullstellensatzCertificateBundle
from jacobian.domains.polynomial_nullstellensatz.singular import _parse_output
from jacobian.domains.polynomial_nullstellensatz.system import (
    materialize_degree_23_system,
)
from jacobian_checkers.nullstellensatz import check_chart_cover

SYSTEM_URI = "artifact://sha256/" + "1" * 64
SYSTEM_DIGEST = "sha256:" + "2" * 64
BUNDLE_URI = "artifact://sha256/" + "3" * 64


@pytest.fixture(scope="module")
def valid_request() -> dict[str, Any]:
    bundle = NullstellensatzCertificateBundle(
        system_uri=SYSTEM_URI,
        system_digest=SYSTEM_DIGEST,
        producer_version="4.4.1p5",
        producer_digest="sha256:" + "4" * 64,
        charts=load_chart_certificates(),
    )
    return {
        "request_version": "1",
        "claim": {
            "artifact_uri": SYSTEM_URI,
            "object_digest": SYSTEM_DIGEST,
            "payload": materialize_degree_23_system().model_dump(mode="json"),
        },
        "candidate": {
            "artifact_uri": BUNDLE_URI,
            "payload": bundle.model_dump(mode="json"),
        },
        "scope": None,
        "certificate": {
            "payload": {
                "certificate_type": "polynomial.nullstellensatz.chart-cover",
                "format_version": "1",
                "payload": {
                    "system_uri": SYSTEM_URI,
                    "certificate_bundle_uri": BUNDLE_URI,
                },
            }
        },
    }


def test_checker_accepts_complete_exact_chart_cover(
    valid_request: dict[str, Any],
) -> None:
    decision = check_chart_cover(valid_request)

    assert decision == {
        "accepted": True,
        "conclusion": "TRUE",
        "arithmetic": "EXACT_RATIONAL",
        "method": "CHECKED_CERTIFICATE",
        "coverage": "EXHAUSTIVE",
        "detail": "all 12 exact chart identities independently replay to one",
        "relation_id": "polynomial.relation.infeasibility-certificate-for",
        "relationship_source_artifact_uris": [BUNDLE_URI],
        "relationship_target_artifact_uris": [SYSTEM_URI],
    }


@pytest.mark.parametrize(
    "mutation",
    (
        "wrong-generator",
        "reordered-variables",
        "altered-domain",
        "truncated-multiplier",
        "missing-term",
        "incorrect-constant",
        "wrong-scope",
        "stale-binding",
        "oversized-certificate",
    ),
)
def test_checker_rejects_adversarial_mutations(
    valid_request: dict[str, Any],
    mutation: str,
) -> None:
    request = deepcopy(valid_request)
    candidate = request["candidate"]["payload"]
    if mutation == "wrong-generator":
        candidate["charts"][0]["generators"][0]["polynomial"]["terms"][0][
            "coefficient"
        ]["num"] = "7"
    elif mutation == "reordered-variables":
        candidate["charts"][0]["variable_order"][0:2] = reversed(
            candidate["charts"][0]["variable_order"][0:2]
        )
    elif mutation == "altered-domain":
        candidate["coefficient_domain"] = "RR"
    elif mutation == "truncated-multiplier":
        candidate["charts"][0]["multipliers"].pop()
    elif mutation == "missing-term":
        terms = next(
            multiplier["multiplier"]["terms"]
            for multiplier in candidate["charts"][0]["multipliers"]
            if multiplier["multiplier"]["terms"]
        )
        terms.pop()
    elif mutation == "incorrect-constant":
        candidate["charts"][0]["identity_rhs"] = {"num": "2", "den": "1"}
    elif mutation == "wrong-scope":
        request["scope"] = request["claim"]
    elif mutation == "stale-binding":
        candidate["system_digest"] = "sha256:" + "9" * 64
    else:
        candidate["producer_version"] = "x" * 2_000_001

    decision = check_chart_cover(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"
    assert decision["coverage"] == "NOT_APPLICABLE"


def test_materialized_system_has_exact_disjunctive_chart_cover() -> None:
    system = materialize_degree_23_system()

    assert system.component_degrees == (2, 3)
    assert len(system.charts) == 12
    assert {
        (
            chart.selected_quadratic_coefficient,
            chart.selected_cubic_coefficient,
        )
        for chart in system.charts
    } == {
        (quadratic, cubic)
        for quadratic in ("a20", "a11", "a02")
        for cubic in ("b30", "b21", "b12", "b03")
    }
    assert all(
        chart.generators[-1].polynomial_id == "rabinowitsch"
        and len(chart.generators[-1].polynomial.terms) == 2
        for chart in system.charts
    )


def test_singular_tagged_output_parser_preserves_exact_multipliers() -> None:
    expected = load_chart_certificates()
    lines = []
    for chart in expected:
        lines.append(f"JCB_BEGIN|{chart.chart_id}")
        for index, multiplier in enumerate(chart.multipliers, start=1):
            lines.append(f"JCB_MULT|{index}")
            for term in multiplier.multiplier.terms:
                coefficient = term.coefficient.num
                if term.coefficient.den != "1":
                    coefficient += "/" + term.coefficient.den
                lines.append(
                    "JCB_TERM|"
                    + coefficient
                    + "|"
                    + ",".join(str(exponent) for exponent in term.exponents)
                )
        lines.append(f"JCB_END|{chart.chart_id}")

    parsed = _parse_output(
        ("\n".join(lines) + "\n").encode("ascii"),
        materialize_degree_23_system(),
    )

    assert parsed == expected


@pytest.mark.parametrize("mutation", ("missing", "duplicate"))
def test_singular_tagged_output_parser_rejects_incomplete_multiplier_markers(
    mutation: str,
) -> None:
    lines = []
    for chart_index, chart in enumerate(materialize_degree_23_system().charts):
        lines.append(f"JCB_BEGIN|{chart.chart_id}")
        for index in range(1, 11):
            if mutation == "missing" and chart_index == 0 and index == 10:
                continue
            lines.append(f"JCB_MULT|{index}")
        if mutation == "duplicate" and chart_index == 0:
            lines.append("JCB_MULT|1")
        lines.append(f"JCB_END|{chart.chart_id}")

    with pytest.raises(ValueError):
        _parse_output(
            ("\n".join(lines) + "\n").encode("ascii"),
            materialize_degree_23_system(),
        )
