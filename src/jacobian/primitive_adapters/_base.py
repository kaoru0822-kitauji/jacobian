"""Shared infrastructure for pinned SymPy/NetworkX primitive adapters.

A :class:`PrimitiveAdapter` implements the
:class:`jacobian.capabilities.CapabilityAdapter` protocol with explicit
``COMPUTED`` assurance, bounded inputs, and no self-verification.  The backend
function receives validated JSON input and returns a JSON-serialisable dict;
the adapter wraps it in a :class:`CapabilityResult` with honest scope and
completeness metadata.
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction
from typing import Any

import networkx as nx

from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityCompleteness,
    CapabilityCompletenessStatus,
    CapabilityDescriptor,
    CapabilityMode,
    CapabilityRequest,
    CapabilityResult,
    CapabilityScope,
)
from jacobian.contracts.results import Execution, ExecutionStatus
from jacobian.provider_runtime import known_provider_runtime

_OBJECT_SCHEMA: dict[str, Any] = {"type": "object"}
_INTEROPERABLE_INT = 2**53 - 1


def _schema(properties: dict[str, Any], *, required: tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


def _int_field(*, minimum: int = 0, maximum: int) -> dict[str, Any]:
    return {"type": "integer", "minimum": minimum, "maximum": maximum}


def _int_array_field(
    *,
    min_items: int = 1,
    max_items: int,
    item_minimum: int = -_INTEROPERABLE_INT,
    item_maximum: int = _INTEROPERABLE_INT,
) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "integer", "minimum": item_minimum, "maximum": item_maximum},
        "minItems": min_items,
        "maxItems": max_items,
    }


def _string_field(*, max_length: int = 4096) -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "maxLength": max_length}


def _string_array_field(
    *,
    min_items: int = 1,
    max_items: int,
    item_max_length: int = 256,
) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string", "minLength": 1, "maxLength": item_max_length},
        "minItems": min_items,
        "maxItems": max_items,
        "uniqueItems": True,
    }


def _edge_array_field(*, max_items: int) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {
            "type": "array",
            "items": {"type": "string", "minLength": 1, "maxLength": 256},
            "minItems": 2,
            "maxItems": 2,
        },
        "maxItems": max_items,
        "uniqueItems": True,
    }


def _rational_field(*, maximum: int = _INTEROPERABLE_INT) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "numerator": {
                "type": "integer",
                "minimum": -_INTEROPERABLE_INT,
                "maximum": _INTEROPERABLE_INT,
            },
            "denominator": {"type": "integer", "minimum": 1, "maximum": maximum},
        },
        "required": ["numerator", "denominator"],
        "additionalProperties": False,
    }


def _rational_array_field(*, max_items: int) -> dict[str, Any]:
    return {
        "type": "array",
        "items": _rational_field(),
        "maxItems": max_items,
    }


def _matrix_field(*, max_rows: int, max_cols: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "rows": _int_field(minimum=1, maximum=max_rows),
            "cols": _int_field(minimum=1, maximum=max_cols),
            "entries": {
                "type": "array",
                "items": {
                    "type": "integer",
                    "minimum": -_INTEROPERABLE_INT,
                    "maximum": _INTEROPERABLE_INT,
                },
                "minItems": 1,
                "maxItems": max_rows * max_cols,
            },
        },
        "required": ["rows", "cols", "entries"],
        "additionalProperties": False,
    }


def _rational_matrix_field(*, max_rows: int, max_cols: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "rows": _int_field(minimum=1, maximum=max_rows),
            "cols": _int_field(minimum=1, maximum=max_cols),
            "entries": _rational_array_field(max_items=max_rows * max_cols),
        },
        "required": ["rows", "cols", "entries"],
        "additionalProperties": False,
    }


class PrimitiveAdapter:
    """One exact deterministic primitive backed by a pinned Python distribution.

    The ``invoke`` callable receives the validated input dict and must return a
    JSON-serialisable dict.  The adapter never promotes the result to
    ``VERIFIED``; the assurance basis explicitly states that independent
    checker replay is an open obligation.
    """

    def __init__(
        self,
        *,
        capability_id: str,
        title: str,
        description: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any] | None = None,
        invoke: Callable[[dict[str, Any]], dict[str, Any]],
        provider: str,
        tags: tuple[str, ...] = (),
        read_only: bool = True,
        scope_description: str | None = None,
    ) -> None:
        self._invoke_fn = invoke
        self._scope_description = scope_description
        runtime = known_provider_runtime(provider, features=tags)
        self._descriptor = CapabilityDescriptor(
            capability_id=capability_id,
            version="1",
            title=title,
            description=description,
            provider=provider,
            provider_runtime=runtime,
            modes=(CapabilityMode.EXPLORE,),
            input_schema=input_schema,
            output_schema=output_schema or _OBJECT_SCHEMA,
            read_only=read_only,
            tags=tags,
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        try:
            output = self._invoke_fn(request.input)
        except _PrimitiveError as exc:
            return _error_result(self.descriptor, request, exc.message)
        except Exception:
            return _error_result(
                self.descriptor,
                request,
                "the pinned backend stopped before returning a result",
            )
        scope_parameters = {
            k: v for k, v in request.input.items() if isinstance(v, (str, int, bool))
        }
        if not scope_parameters and request.input:
            scope_parameters = {"input_keys": ",".join(sorted(request.input.keys()))}
        scope = (
            CapabilityScope(
                description=self._scope_description or "the bounded input domain",
                parameters=scope_parameters,
            )
            if request.input
            else None
        )
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            output=output,
            scope=scope,
            completeness=CapabilityCompleteness(
                status=CapabilityCompletenessStatus.COMPLETE,
                basis=(
                    "deterministic exact computation over the bounded declared input"
                ),
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis=(
                    "pinned SymPy/NetworkX deterministic computation; independent "
                    "checker replay is an open obligation"
                ),
            ),
        )


class _PrimitiveError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _error_result(
    descriptor: CapabilityDescriptor,
    request: CapabilityRequest,
    message: str,
) -> CapabilityResult:
    from jacobian.contracts.capabilities import CapabilityDiagnostic

    diagnostic = CapabilityDiagnostic(
        code="PRIMITIVE_EXECUTION_FAILED",
        stage="primitive_backend",
        message=message,
        hint="Inspect the input bounds and retry with a valid bounded request.",
    )
    return CapabilityResult(
        capability_id=descriptor.capability_id,
        capability_version=descriptor.version,
        mode=request.mode,
        execution=Execution(status=ExecutionStatus.ERROR, detail=message),
        output={"error": diagnostic.model_dump(mode="json", exclude_none=True)},
        diagnostics=(diagnostic,),
        assurance=CapabilityAssurance(
            level=CapabilityAssuranceLevel.HEURISTIC,
            basis="execution failure; no mathematical conclusion",
        ),
    )


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise _PrimitiveError(message)


def _frac_to_json(value: Any) -> dict[str, int]:
    from fractions import Fraction

    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if isinstance(value, int):
        return {"numerator": value, "denominator": 1}
    raise _PrimitiveError(f"cannot serialise {type(value).__name__} as a rational")


def _frac_list_to_json(values: list[Any]) -> list[dict[str, int]]:
    return [_frac_to_json(v) for v in values]


def _frac_matrix_to_json(
    rows: int, cols: int, values: list[Any]
) -> list[list[dict[str, int]]]:
    result: list[list[dict[str, int]]] = []
    for r in range(rows):
        row: list[dict[str, int]] = []
        for c in range(cols):
            row.append(_frac_to_json(values[r * cols + c]))
        result.append(row)
    return result


def _parse_rational(entry: dict[str, Any]) -> Fraction:
    return Fraction(entry["numerator"], entry["denominator"])


def _parse_rational_list(entries: list[dict[str, Any]]) -> list[Fraction]:
    return [_parse_rational(e) for e in entries]


def _parse_rational_matrix(
    payload: dict[str, Any],
) -> tuple[int, int, list[Fraction]]:
    rows = int(payload["rows"])
    cols = int(payload["cols"])
    entries = _parse_rational_list(payload["entries"])
    _check(len(entries) == rows * cols, "entry count does not match rows*cols")
    return rows, cols, entries


def _parse_int_matrix(
    payload: dict[str, Any],
) -> tuple[int, int, list[int]]:
    rows = int(payload["rows"])
    cols = int(payload["cols"])
    entries = [int(x) for x in payload["entries"]]
    _check(len(entries) == rows * cols, "entry count does not match rows*cols")
    return rows, cols, entries


def _build_graph(payload: dict[str, Any]) -> nx.Graph[Any]:
    vertices = list(payload["vertices"])
    edges = [tuple(e) for e in payload["edges"]]
    g: nx.Graph[Any] = nx.Graph()
    g.add_nodes_from(vertices)
    for u, v in edges:
        _check(u in vertices and v in vertices, "edge references unknown vertex")
        _check(u != v, "self-loops are not permitted in simple graphs")
        g.add_edge(u, v)
    return g
