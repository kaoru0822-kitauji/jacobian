"""Focused tests for the refactored _valid_against_schema helpers.

These tests exercise each cohesive helper extracted from the original
monolithic validator to confirm that the split preserves complete
fail-closed JSON Schema validation semantics.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "templates"
    / "task"
    / "tests"
    / "verifier_support.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("_vs_under_test", _TEMPLATE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_vs_under_test"] = module
    spec.loader.exec_module(module)
    return module


_VS = _load_module()


# ---------------------------------------------------------------------------
# _resolve_ref
# ---------------------------------------------------------------------------


class TestResolveRef:
    def test_resolves_valid_ref(self) -> None:
        root: dict[str, Any] = {"$defs": {"pos": {"type": "integer", "minimum": 0}}}
        result = _VS._resolve_ref({"$ref": "#/$defs/pos"}, root)
        assert result == {"type": "integer", "minimum": 0}

    def test_returns_none_for_non_string_ref(self) -> None:
        result = _VS._resolve_ref({"$ref": 123}, {"$defs": {}})
        assert result is None

    def test_returns_none_for_wrong_prefix(self) -> None:
        result = _VS._resolve_ref({"$ref": "#/definitions/pos"}, {"$defs": {}})
        assert result is None

    def test_returns_none_when_no_defs(self) -> None:
        result = _VS._resolve_ref({"$ref": "#/$defs/pos"}, {})
        assert result is None

    def test_returns_none_when_defs_not_dict(self) -> None:
        result = _VS._resolve_ref({"$ref": "#/$defs/pos"}, {"$defs": []})
        assert result is None

    def test_returns_none_for_missing_def(self) -> None:
        result = _VS._resolve_ref({"$ref": "#/$defs/missing"}, {"$defs": {}})
        assert result is None


# ---------------------------------------------------------------------------
# _validate_type_keyword
# ---------------------------------------------------------------------------


class TestValidateTypeKeyword:
    @pytest.mark.parametrize(
        "value,expected,result",
        [
            ("x", "string", True),
            (42, "string", False),
            (42, "integer", True),
            (42.0, "integer", True),
            (42.5, "integer", False),
            (True, "boolean", True),
            (True, "integer", False),
            (None, "null", True),
            (3.14, "number", True),
            ([], "array", True),
            ({}, "object", True),
        ],
    )
    def test_single_type(self, value: object, expected: str, result: bool) -> None:
        assert _VS._validate_type_keyword(value, {"type": expected}) is result

    def test_list_type_matches_any(self) -> None:
        assert _VS._validate_type_keyword(42, {"type": ["string", "integer"]}) is True

    def test_list_type_matches_none(self) -> None:
        assert (
            _VS._validate_type_keyword(True, {"type": ["string", "integer"]}) is False
        )

    def test_no_type_keyword_passes(self) -> None:
        assert _VS._validate_type_keyword("x", {}) is True


# ---------------------------------------------------------------------------
# _validate_const_enum
# ---------------------------------------------------------------------------


class TestValidateConstEnum:
    def test_const_matches(self) -> None:
        assert _VS._validate_const_enum("x", {"const": "x"}) is True

    def test_const_mismatches(self) -> None:
        assert _VS._validate_const_enum("y", {"const": "x"}) is False

    def test_const_bool_distinct_from_int(self) -> None:
        assert _VS._validate_const_enum(True, {"const": 1}) is False

    def test_enum_matches(self) -> None:
        assert _VS._validate_const_enum("b", {"enum": ["a", "b", "c"]}) is True

    def test_enum_mismatches(self) -> None:
        assert _VS._validate_const_enum("d", {"enum": ["a", "b", "c"]}) is False

    def test_no_const_enum_passes(self) -> None:
        assert _VS._validate_const_enum("x", {}) is True


# ---------------------------------------------------------------------------
# _validate_combinators
# ---------------------------------------------------------------------------


class TestValidateCombinators:
    def test_any_of_matches(self) -> None:
        assert (
            _VS._validate_combinators(
                42, {"anyOf": [{"type": "string"}, {"type": "integer"}]}, {}
            )
            is True
        )

    def test_any_of_no_match(self) -> None:
        assert (
            _VS._validate_combinators(
                True, {"anyOf": [{"type": "string"}, {"type": "integer"}]}, {}
            )
            is False
        )

    def test_one_of_exactly_one(self) -> None:
        assert (
            _VS._validate_combinators(
                42, {"oneOf": [{"type": "integer"}, {"type": "string"}]}, {}
            )
            is True
        )

    def test_one_of_multiple_match(self) -> None:
        assert (
            _VS._validate_combinators(
                42, {"oneOf": [{"type": "integer"}, {"type": "number"}]}, {}
            )
            is False
        )

    def test_not_rejects_match(self) -> None:
        assert _VS._validate_combinators("x", {"not": {"type": "string"}}, {}) is False

    def test_not_passes_non_match(self) -> None:
        assert _VS._validate_combinators(42, {"not": {"type": "string"}}, {}) is True

    def test_if_then_passes_when_condition_met(self) -> None:
        assert (
            _VS._validate_combinators(
                5, {"if": {"type": "integer"}, "then": {"minimum": 0}}, {}
            )
            is True
        )

    def test_if_then_fails_when_condition_met_but_then_fails(self) -> None:
        assert (
            _VS._validate_combinators(
                -1, {"if": {"type": "integer"}, "then": {"minimum": 0}}, {}
            )
            is False
        )

    def test_if_then_passes_when_condition_not_met(self) -> None:
        assert (
            _VS._validate_combinators(
                "x", {"if": {"type": "integer"}, "then": {"minimum": 0}}, {}
            )
            is True
        )

    def test_no_combinators_passes(self) -> None:
        assert _VS._validate_combinators("x", {}, {}) is True


# ---------------------------------------------------------------------------
# _validate_string_constraints
# ---------------------------------------------------------------------------


class TestValidateStringConstraints:
    def test_min_length(self) -> None:
        assert _VS._validate_string_constraints("ab", {"minLength": 3}) is False
        assert _VS._validate_string_constraints("abc", {"minLength": 3}) is True

    def test_max_length(self) -> None:
        assert _VS._validate_string_constraints("abcd", {"maxLength": 3}) is False
        assert _VS._validate_string_constraints("abc", {"maxLength": 3}) is True

    def test_pattern_match(self) -> None:
        assert _VS._validate_string_constraints("abc", {"pattern": "^a"}) is True

    def test_pattern_no_match(self) -> None:
        assert _VS._validate_string_constraints("xbc", {"pattern": "^a"}) is False

    def test_pattern_not_string(self) -> None:
        assert _VS._validate_string_constraints("x", {"pattern": 123}) is False

    def test_non_string_passes(self) -> None:
        assert _VS._validate_string_constraints(42, {"minLength": 3}) is True


# ---------------------------------------------------------------------------
# _validate_number_constraints
# ---------------------------------------------------------------------------


class TestValidateNumberConstraints:
    def test_minimum(self) -> None:
        assert _VS._validate_number_constraints(3, {"minimum": 5}) is False
        assert _VS._validate_number_constraints(5, {"minimum": 5}) is True

    def test_maximum(self) -> None:
        assert _VS._validate_number_constraints(10, {"maximum": 5}) is False
        assert _VS._validate_number_constraints(5, {"maximum": 5}) is True

    def test_non_number_passes(self) -> None:
        assert _VS._validate_number_constraints("x", {"minimum": 5}) is True

    def test_bool_not_treated_as_number(self) -> None:
        assert _VS._validate_number_constraints(True, {"minimum": 5}) is True


# ---------------------------------------------------------------------------
# _validate_array_constraints
# ---------------------------------------------------------------------------


class TestValidateArrayConstraints:
    def test_min_items(self) -> None:
        assert _VS._validate_array_constraints([1], {"minItems": 2}, {}) is False
        assert _VS._validate_array_constraints([1, 2], {"minItems": 2}, {}) is True

    def test_max_items(self) -> None:
        assert _VS._validate_array_constraints([1, 2, 3], {"maxItems": 2}, {}) is False
        assert _VS._validate_array_constraints([1, 2], {"maxItems": 2}, {}) is True

    def test_unique_items_passes(self) -> None:
        assert (
            _VS._validate_array_constraints([1, 2, 3], {"uniqueItems": True}, {})
            is True
        )

    def test_unique_items_fails(self) -> None:
        assert (
            _VS._validate_array_constraints([1, 1, 2], {"uniqueItems": True}, {})
            is False
        )

    def test_prefix_items_valid(self) -> None:
        schema = {"prefixItems": [{"type": "integer"}, {"type": "string"}]}
        assert _VS._validate_array_constraints([1, "x", True], schema, {}) is True

    def test_prefix_items_invalid(self) -> None:
        schema = {"prefixItems": [{"type": "integer"}, {"type": "string"}]}
        assert _VS._validate_array_constraints(["x", 1], schema, {}) is False

    def test_items_after_prefix(self) -> None:
        schema = {"prefixItems": [{"type": "integer"}], "items": {"type": "string"}}
        assert _VS._validate_array_constraints([1, "a", "b"], schema, {}) is True
        assert _VS._validate_array_constraints([1, "a", 2], schema, {}) is False

    def test_contains_match(self) -> None:
        assert (
            _VS._validate_array_constraints(
                [1, "x", 3], {"contains": {"type": "string"}}, {}
            )
            is True
        )

    def test_contains_no_match(self) -> None:
        assert (
            _VS._validate_array_constraints(
                [1, 2, 3], {"contains": {"type": "string"}}, {}
            )
            is False
        )

    def test_non_array_passes(self) -> None:
        assert _VS._validate_array_constraints("x", {"minItems": 2}, {}) is True


# ---------------------------------------------------------------------------
# _validate_object_constraints
# ---------------------------------------------------------------------------


class TestValidateObjectConstraints:
    def test_required_present(self) -> None:
        assert (
            _VS._validate_object_constraints(
                {"a": 1, "b": 2}, {"required": ["a", "b"]}, {}
            )
            is True
        )

    def test_required_missing(self) -> None:
        assert (
            _VS._validate_object_constraints({"a": 1}, {"required": ["a", "b"]}, {})
            is False
        )

    def test_required_not_list(self) -> None:
        assert (
            _VS._validate_object_constraints({"a": 1}, {"required": "a"}, {}) is False
        )

    def test_property_names_valid(self) -> None:
        assert (
            _VS._validate_object_constraints(
                {"a": 1}, {"propertyNames": {"type": "string", "minLength": 1}}, {}
            )
            is True
        )

    def test_property_names_invalid(self) -> None:
        assert (
            _VS._validate_object_constraints(
                {"": 1}, {"propertyNames": {"type": "string", "minLength": 1}}, {}
            )
            is False
        )

    def test_properties_valid(self) -> None:
        schema = {"properties": {"a": {"type": "integer"}}}
        assert _VS._validate_object_constraints({"a": 1}, schema, {}) is True

    def test_properties_invalid(self) -> None:
        schema = {"properties": {"a": {"type": "integer"}}}
        assert _VS._validate_object_constraints({"a": "x"}, schema, {}) is False

    def test_additional_properties_false_rejects_extra(self) -> None:
        schema = {"properties": {"a": {}}, "additionalProperties": False}
        assert _VS._validate_object_constraints({"a": 1, "b": 2}, schema, {}) is False

    def test_additional_properties_false_allows_known(self) -> None:
        schema = {"properties": {"a": {}}, "additionalProperties": False}
        assert _VS._validate_object_constraints({"a": 1}, schema, {}) is True

    def test_additional_properties_schema_validates_extra(self) -> None:
        schema = {"properties": {"a": {}}, "additionalProperties": {"type": "integer"}}
        assert _VS._validate_object_constraints({"a": 1, "b": 2}, schema, {}) is True

    def test_additional_properties_schema_rejects_extra(self) -> None:
        schema = {"properties": {"a": {}}, "additionalProperties": {"type": "integer"}}
        assert _VS._validate_object_constraints({"a": 1, "b": "x"}, schema, {}) is False

    def test_non_object_passes(self) -> None:
        assert _VS._validate_object_constraints("x", {"required": ["a"]}, {}) is True


# ---------------------------------------------------------------------------
# _valid_against_schema integration
# ---------------------------------------------------------------------------


class TestValidAgainstSchemaIntegration:
    def _schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 1, "maxLength": 10},
                "age": {"type": "integer", "minimum": 0, "maximum": 150},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                },
                "role": {"enum": ["admin", "user"]},
            },
            "required": ["name", "age"],
            "additionalProperties": False,
        }

    def test_valid_object(self) -> None:
        s = self._schema()
        assert (
            _VS._valid_against_schema(
                {"name": "abc", "age": 30, "tags": ["x", "y"], "role": "admin"}, s, s
            )
            is True
        )

    def test_missing_required(self) -> None:
        s = self._schema()
        assert _VS._valid_against_schema({"name": "abc"}, s, s) is False

    def test_wrong_type(self) -> None:
        s = self._schema()
        assert _VS._valid_against_schema({"name": 123, "age": 30}, s, s) is False

    def test_additional_property_rejected(self) -> None:
        s = self._schema()
        assert (
            _VS._valid_against_schema({"name": "abc", "age": 30, "extra": 1}, s, s)
            is False
        )

    def test_schema_true_accepts_anything(self) -> None:
        assert _VS._valid_against_schema("anything", True, {}) is True

    def test_schema_false_rejects_everything(self) -> None:
        assert _VS._valid_against_schema("anything", False, {}) is False

    def test_non_dict_schema_rejected(self) -> None:
        assert _VS._valid_against_schema("x", "not-a-schema", {}) is False

    def test_ref_resolution(self) -> None:
        root: dict[str, Any] = {"$defs": {"pos": {"type": "integer", "minimum": 0}}}
        assert _VS._valid_against_schema(5, {"$ref": "#/$defs/pos"}, root) is True
        assert _VS._valid_against_schema(-1, {"$ref": "#/$defs/pos"}, root) is False

    def test_ref_recursive(self) -> None:
        root: dict[str, Any] = {
            "$defs": {
                "a": {"$ref": "#/$defs/b"},
                "b": {"type": "string"},
            }
        }
        assert _VS._valid_against_schema("x", {"$ref": "#/$defs/a"}, root) is True
        assert _VS._valid_against_schema(42, {"$ref": "#/$defs/a"}, root) is False
