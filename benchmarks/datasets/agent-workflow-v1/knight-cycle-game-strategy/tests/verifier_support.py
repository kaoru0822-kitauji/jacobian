"""Canonical fail-closed protocol helpers vendored into Harbor verifiers.

This module uses only the Python standard library. Each task receives an
identical copy in its hidden ``tests`` directory so the verifier remains
self-contained and independent from production Jacobian code.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import stat
from pathlib import Path
from typing import Any, Literal

WORKSPACE = Path("/app")
TESTS = Path("/tests")
MAX_SUBMISSION_BYTES = 16 * 1024 * 1024
MAX_INPUT_BYTES = 16 * 1024 * 1024
SUBMISSION_FIELDS = frozenset(
    {
        "task_id",
        "conclusion",
        "result",
        "claimed_assurance",
        "scope",
        "completeness",
        "evidence",
        "limitations",
    }
)
ASSURANCE_LEVELS = frozenset({"UNVERIFIED", "COMPUTED", "CHECKED", "VERIFIED"})


def is_regular_bounded_file(path: Path, *, max_bytes: int | None) -> bool:
    """Reject symlinks, non-regular files, and oversized files before reading."""

    try:
        status = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(status.st_mode) or not stat.S_ISREG(status.st_mode):
        return False
    return max_bytes is None or status.st_size <= max_bytes


def sha256_uri(path: Path) -> str:
    """Hash a regular evidence file without following a replacement symlink."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65_536), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


MAX_PUBLIC_CONTRACT_BYTES = 4 * 1024 * 1024
_SCHEMA_KEYWORDS = frozenset(
    {
        "$defs",
        "$ref",
        "$schema",
        "additionalProperties",
        "anyOf",
        "const",
        "contains",
        "description",
        "enum",
        "if",
        "items",
        "maxItems",
        "maxLength",
        "maximum",
        "minItems",
        "minLength",
        "minimum",
        "not",
        "oneOf",
        "pattern",
        "prefixItems",
        "properties",
        "propertyNames",
        "required",
        "then",
        "type",
        "uniqueItems",
    }
)


def _schema_supported(schema: object) -> bool:
    if not isinstance(schema, dict) or not set(schema).issubset(_SCHEMA_KEYWORDS):
        return False
    for name in ("$defs", "properties"):
        children = schema.get(name, {})
        if not isinstance(children, dict) or not all(
            isinstance(key, str) and _schema_supported(value)
            for key, value in children.items()
        ):
            return False
    for name in (
        "additionalProperties",
        "contains",
        "if",
        "items",
        "not",
        "propertyNames",
        "then",
    ):
        child = schema.get(name)
        if (
            child is not None
            and not isinstance(child, bool)
            and not _schema_supported(child)
        ):
            return False
    for name in ("anyOf", "oneOf", "prefixItems"):
        children = schema.get(name, [])
        if not isinstance(children, list) or not all(
            _schema_supported(value) for value in children
        ):
            return False
    return True


def _schema_type_matches(value: object, expected: str) -> bool:
    return {
        "array": isinstance(value, list),
        "boolean": type(value) is bool,
        "integer": type(value) is int
        or (type(value) is float and math.isfinite(value) and value.is_integer()),
        "null": value is None,
        "number": type(value) in (int, float) and math.isfinite(value),
        "object": isinstance(value, dict),
        "string": isinstance(value, str),
    }.get(expected, False)


def _schema_equal(left: object, right: object) -> bool:
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if type(left) in (int, float) and type(right) in (int, float):
        return math.isfinite(left) and math.isfinite(right) and left == right
    return type(left) is type(right) and left == right


def _resolve_ref(schema: dict[str, Any], root: dict[str, Any]) -> object | None:
    """Resolve a ``#/$defs/`` reference; return ``None`` if malformed."""

    reference = schema.get("$ref")
    prefix = "#/$defs/"
    definitions = root.get("$defs")
    if (
        not isinstance(reference, str)
        or not reference.startswith(prefix)
        or not isinstance(definitions, dict)
    ):
        return None
    return definitions.get(reference.removeprefix(prefix))


def _validate_type_keyword(value: object, schema: dict[str, Any]) -> bool:
    expected = schema.get("type")
    if isinstance(expected, str) and not _schema_type_matches(value, expected):
        return False
    return not isinstance(expected, list) or any(
        isinstance(item, str) and _schema_type_matches(value, item) for item in expected
    )


def _validate_const_enum(value: object, schema: dict[str, Any]) -> bool:
    if "const" in schema and not _schema_equal(value, schema["const"]):
        return False
    return "enum" not in schema or any(
        _schema_equal(value, item) for item in schema["enum"]
    )


def _validate_combinators(
    value: object, schema: dict[str, Any], root: dict[str, Any]
) -> bool:
    if "anyOf" in schema and not any(
        _valid_against_schema(value, item, root) for item in schema["anyOf"]
    ):
        return False
    if (
        "oneOf" in schema
        and sum(_valid_against_schema(value, item, root) for item in schema["oneOf"])
        != 1
    ):
        return False
    if "not" in schema and _valid_against_schema(value, schema["not"], root):
        return False
    return not (
        "if" in schema
        and _valid_against_schema(value, schema["if"], root)
        and "then" in schema
        and not _valid_against_schema(value, schema["then"], root)
    )


def _validate_string_constraints(value: object, schema: dict[str, Any]) -> bool:
    if not isinstance(value, str):
        return True
    if len(value) < schema.get("minLength", 0) or len(value) > schema.get(
        "maxLength", len(value)
    ):
        return False
    pattern = schema.get("pattern")
    return pattern is None or (
        isinstance(pattern, str) and re.search(pattern, value) is not None
    )


def _validate_number_constraints(value: object, schema: dict[str, Any]) -> bool:
    if type(value) not in (int, float):
        return True
    if "minimum" in schema and value < schema["minimum"]:
        return False
    return "maximum" not in schema or value <= schema["maximum"]


def _validate_array_constraints(
    value: object, schema: dict[str, Any], root: dict[str, Any]
) -> bool:
    if not isinstance(value, list):
        return True
    if len(value) < schema.get("minItems", 0) or len(value) > schema.get(
        "maxItems", len(value)
    ):
        return False
    if schema.get("uniqueItems") is True:
        encoded = [
            json.dumps(item, sort_keys=True, separators=(",", ":")) for item in value
        ]
        if len(encoded) != len(set(encoded)):
            return False
    prefix_items = schema.get("prefixItems", [])
    if any(
        not _valid_against_schema(item, prefix_items[index], root)
        for index, item in enumerate(value[: len(prefix_items)])
    ):
        return False
    item_schema = schema.get("items")
    if item_schema is not None and any(
        not _valid_against_schema(item, item_schema, root)
        for item in value[len(prefix_items) :]
    ):
        return False
    contains = schema.get("contains")
    return contains is None or any(
        _valid_against_schema(item, contains, root) for item in value
    )


def _validate_object_constraints(
    value: object, schema: dict[str, Any], root: dict[str, Any]
) -> bool:
    if not isinstance(value, dict):
        return True
    required = schema.get("required", [])
    if not isinstance(required, list) or not all(
        isinstance(name, str) and name in value for name in required
    ):
        return False
    name_schema = schema.get("propertyNames")
    if name_schema is not None and not all(
        _valid_against_schema(name, name_schema, root) for name in value
    ):
        return False
    properties = schema.get("properties", {})
    for name, child in properties.items():
        if name in value and not _valid_against_schema(value[name], child, root):
            return False
    extras = set(value) - set(properties)
    additional = schema.get("additionalProperties", True)
    if extras and additional is False:
        return False
    return not isinstance(additional, dict) or all(
        _valid_against_schema(value[name], additional, root) for name in extras
    )


def _valid_against_schema(value: object, schema: object, root: dict[str, Any]) -> bool:
    if schema is True:
        return True
    if schema is False or not isinstance(schema, dict):
        return False
    reference = schema.get("$ref")
    if reference is not None:
        target = _resolve_ref(schema, root)
        return _valid_against_schema(value, target, root)
    checks = (
        lambda: _validate_type_keyword(value, schema),
        lambda: _validate_const_enum(value, schema),
        lambda: _validate_combinators(value, schema, root),
        lambda: _validate_string_constraints(value, schema),
        lambda: _validate_number_constraints(value, schema),
        lambda: _validate_array_constraints(value, schema, root),
        lambda: _validate_object_constraints(value, schema, root),
    )
    return all(check() for check in checks)


def _load_public_contract(
    path: Path = TESTS / "public_contract.json",
) -> dict[str, Any] | None:
    if not is_regular_bounded_file(path, max_bytes=MAX_PUBLIC_CONTRACT_BYTES):
        return None
    try:
        contract = json.loads(path.read_text())
    except (OSError, ValueError, RecursionError, MemoryError):
        return None
    if not isinstance(contract, dict) or contract.get("schema_version") != "1":
        return None
    schema = contract.get("submission_schema")
    if not _schema_supported(schema):
        return None
    return contract


def load_submission(
    path: Path = WORKSPACE / "submission.json",
    *,
    require_input_binding: bool = True,
) -> dict[str, Any] | None:
    """Parse and completely validate one bounded submission object."""

    if require_input_binding and not workspace_input_is_bound():
        return None
    if not is_regular_bounded_file(path, max_bytes=MAX_SUBMISSION_BYTES):
        return None
    contract = _load_public_contract()
    if contract is None:
        return None
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError, RecursionError, MemoryError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def _public_submission_is_valid(submission: object) -> bool:
    contract = _load_public_contract()
    if contract is None:
        return False
    schema = contract["submission_schema"]
    try:
        return _valid_against_schema(submission, schema, schema)
    except (ValueError, RecursionError, MemoryError, TypeError):
        return False


def workspace_input_is_bound(
    visible_path: Path = WORKSPACE / "input.json",
    *,
    tests: Path = TESTS,
) -> bool:
    """Require the agent-visible input to equal the sole frozen verifier input."""

    try:
        candidates = tuple(tests.glob("*input*.json"))
    except OSError:
        return False
    if len(candidates) != 1:
        return False
    frozen_path = candidates[0]
    if not all(
        is_regular_bounded_file(candidate, max_bytes=MAX_INPUT_BYTES)
        for candidate in (frozen_path, visible_path)
    ):
        return False
    try:
        return sha256_uri(frozen_path) == sha256_uri(visible_path)
    except OSError:
        return False


def strict_submission_contract(
    submission: object,
    *,
    task_id: str,
    conclusion: str,
    completeness: str = "COMPLETE",
    evidence_count: int = 1,
    min_limitations: int = 0,
    allowed_assurances: frozenset[str] = ASSURANCE_LEVELS,
    verification_record: Literal[
        "required_when_verified", "optional", "forbidden"
    ] = "required_when_verified",
) -> bool:
    """Validate the shared submission envelope without interpreting mathematics."""

    if not isinstance(submission, dict):
        return False
    verified = submission.get("claimed_assurance") == "VERIFIED"
    expected_fields = {frozenset(SUBMISSION_FIELDS)}
    if verification_record == "required_when_verified" and verified:
        expected_fields = {frozenset(SUBMISSION_FIELDS | {"verification_record_uri"})}
    elif verification_record == "optional":
        expected_fields.add(frozenset(SUBMISSION_FIELDS | {"verification_record_uri"}))
    limitations = submission.get("limitations", [])
    return bool(
        _public_submission_is_valid(submission)
        and frozenset(submission) in expected_fields
        and submission.get("task_id") == task_id
        and submission.get("conclusion") == conclusion
        and submission.get("completeness") == completeness
        and isinstance(submission.get("result"), dict)
        and isinstance(submission.get("scope"), str)
        and isinstance(limitations, list)
        and len(limitations) >= min_limitations
        and all(type(item) is str for item in limitations)
        and isinstance(submission.get("evidence"), list)
        and len(submission.get("evidence", [])) == evidence_count
        and isinstance(submission.get("claimed_assurance"), str)
        and submission.get("claimed_assurance") in allowed_assurances
    )


def resolve_evidence(
    descriptor: object,
    *,
    expected_path: str,
    workspace: Path = WORKSPACE,
    max_bytes: int | None = None,
) -> Path | None:
    """Resolve one digest-bound evidence file without escapes or symlinks."""

    if (
        not isinstance(descriptor, dict)
        or set(descriptor) != {"path", "sha256"}
        or descriptor.get("path") != expected_path
        or not isinstance(descriptor.get("sha256"), str)
    ):
        return None
    relative = Path(expected_path)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    root = workspace.resolve()
    unresolved = workspace / relative
    current = workspace
    try:
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                return None
        target = unresolved.resolve(strict=True)
    except OSError:
        return None
    if not target.is_relative_to(root) or not is_regular_bounded_file(
        target, max_bytes=max_bytes
    ):
        return None
    try:
        if descriptor["sha256"] != sha256_uri(target):
            return None
    except OSError:
        return None
    return target


def read_evidence_json(
    descriptor: object,
    *,
    expected_path: str,
    workspace: Path = WORKSPACE,
    max_bytes: int | None = None,
) -> dict[str, Any] | None:
    """Resolve and parse a digest-bound evidence object."""

    target = resolve_evidence(
        descriptor,
        expected_path=expected_path,
        workspace=workspace,
        max_bytes=max_bytes,
    )
    if target is None:
        return None
    try:
        value = json.loads(target.read_text())
    except (OSError, ValueError, RecursionError, MemoryError):
        return None
    return value if isinstance(value, dict) else None


def evidence_list_is_bound(
    evidence: object,
    *,
    expected_path: str = "evidence/answer.txt",
    expected_count: int = 1,
    max_bytes: int | None = None,
) -> bool:
    """Require an exact-size list binding the expected evidence file."""

    return bool(
        isinstance(evidence, list)
        and len(evidence) == expected_count
        and all(
            resolve_evidence(item, expected_path=expected_path, max_bytes=max_bytes)
            is not None
            for item in evidence
        )
    )


def authorized_record_is_bound(
    descriptor: object,
    *,
    authorized_path: Path,
    dynamic_fields: frozenset[str] = frozenset({"environment_digest"}),
) -> bool:
    """Bind an exact hidden authorization record while allowing named identities."""

    actual = read_evidence_json(
        descriptor,
        expected_path="evidence/verification-record.json",
    )
    try:
        authorized = json.loads(authorized_path.read_text())
    except (OSError, ValueError):
        return False
    if not isinstance(actual, dict) or not isinstance(authorized, dict):
        return False
    if set(actual) != set(authorized):
        return False
    for key, value in authorized.items():
        if key not in dynamic_fields and actual.get(key) != value:
            return False
    for key in dynamic_fields:
        value = actual.get(key)
        if not valid_sha256_uri(value):
            return False
    return True


def valid_sha256_uri(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def false_verified_claim(
    submission: object,
    *,
    verification_record_bound: bool,
) -> bool:
    """Fail closed when VERIFIED is asserted without exact authorized binding."""

    return bool(
        isinstance(submission, dict)
        and submission.get("claimed_assurance") == "VERIFIED"
        and not verification_record_bound
    )


__all__ = [
    "ASSURANCE_LEVELS",
    "MAX_INPUT_BYTES",
    "MAX_SUBMISSION_BYTES",
    "SUBMISSION_FIELDS",
    "TESTS",
    "WORKSPACE",
    "authorized_record_is_bound",
    "evidence_list_is_bound",
    "false_verified_claim",
    "is_regular_bounded_file",
    "load_submission",
    "read_evidence_json",
    "resolve_evidence",
    "sha256_uri",
    "strict_submission_contract",
    "valid_sha256_uri",
    "workspace_input_is_bound",
]
