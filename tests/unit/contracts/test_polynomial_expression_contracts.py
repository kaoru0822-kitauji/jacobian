from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.polynomial_expressions import (
    PolynomialExpressionArtifact,
    PolynomialExpressionNormalizeRequest,
    analyze_polynomial_expression,
)
from jacobian.schema_registry import model_schema


def _variable(name: str = "x") -> dict[str, object]:
    return {"kind": "variable", "name": name}


def _artifact(expression: dict[str, object]) -> dict[str, object]:
    return {
        "variables": ["x", "y"],
        "expression": expression,
    }


def test_typed_expression_contract_accepts_bounded_polynomial_ast() -> None:
    artifact = PolynomialExpressionArtifact.model_validate(
        _artifact(
            {
                "kind": "add",
                "operands": [
                    {
                        "kind": "multiply",
                        "operands": [
                            {
                                "kind": "rational",
                                "value": {"num": "3", "den": "2"},
                            },
                            {
                                "kind": "power",
                                "base": _variable("x"),
                                "exponent": 2,
                            },
                        ],
                    },
                    {"kind": "negate", "operand": _variable("y")},
                ],
            }
        )
    )

    analysis = analyze_polynomial_expression(
        artifact.expression,
        artifact.variables,
    )

    assert artifact.domain == "QQ"
    assert analysis.node_count == 7
    assert analysis.depth == 4
    assert analysis.expanded_term_upper_bound == 2
    assert analysis.maximum_exponents == (2, 1)


def test_expression_schema_is_a_closed_discriminated_ast() -> None:
    schema = model_schema(PolynomialExpressionNormalizeRequest)
    serialized = str(schema)

    assert "PolynomialAddExpression" in serialized
    assert "PolynomialPowerExpression" in serialized
    assert "discriminator" in serialized
    assert "formula" not in schema["properties"]["expression"]["$ref"]


@pytest.mark.parametrize(
    "expression",
    [
        {"kind": "variable", "name": "z"},
        {"kind": "formula", "value": "__import__('os').system('id')"},
        {"kind": "power", "base": _variable(), "exponent": True},
        {
            "kind": "rational",
            "value": {"num": "2", "den": "2"},
        },
    ],
    ids=(
        "undeclared_variable",
        "untyped_formula_string",
        "boolean_exponent",
        "noncanonical_rational",
    ),
)
def test_expression_contract_rejects_unsafe_or_ambiguous_nodes(
    expression: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        PolynomialExpressionArtifact.model_validate(_artifact(expression))


def test_expression_contract_rejects_expansion_term_blowup() -> None:
    with pytest.raises(ValidationError, match="1024-term budget"):
        PolynomialExpressionArtifact.model_validate(
            _artifact(
                {
                    "kind": "power",
                    "base": {
                        "kind": "add",
                        "operands": [_variable("x") for _ in range(16)],
                    },
                    "exponent": 4,
                }
            )
        )


def test_expression_contract_rejects_derived_exponent_beyond_output_ring() -> None:
    with pytest.raises(ValidationError, match="exponent exceeds 127"):
        PolynomialExpressionArtifact.model_validate(
            _artifact(
                {
                    "kind": "power",
                    "base": {
                        "kind": "power",
                        "base": _variable("x"),
                        "exponent": 32,
                    },
                    "exponent": 4,
                }
            )
        )


def test_expression_contract_rejects_coefficient_growth_budget() -> None:
    with pytest.raises(ValidationError, match="coefficient digit budget"):
        PolynomialExpressionArtifact.model_validate(
            _artifact(
                {
                    "kind": "power",
                    "base": {
                        "kind": "rational",
                        "value": {"num": "9" * 256, "den": "1"},
                    },
                    "exponent": 32,
                }
            )
        )


def test_expression_contract_rejects_excessive_depth() -> None:
    expression: dict[str, object] = _variable()
    for _ in range(16):
        expression = {"kind": "negate", "operand": expression}

    with pytest.raises(ValidationError, match="depth 16"):
        PolynomialExpressionArtifact.model_validate(_artifact(expression))
