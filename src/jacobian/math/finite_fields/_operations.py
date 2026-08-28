"""Finite-field operation declarations over authoritative native values."""

from jacobian.catalog._examples import example
from jacobian.catalog.models import MathTool, MathTools
from jacobian.math.finite_fields import (
    FiniteLinearMap,
    FiniteMapTable,
    ProjectiveLine,
    RankResult,
    finite_map_table,
    linear_map_rank,
    projective_line,
    restrict_scalars,
)
from jacobian.math.finite_fields._models import (
    FiniteMapTableRequest,
    LinearMapRankRequest,
    ProjectiveLineRequest,
    RestrictScalarsRequest,
)

_FIELD: dict[str, object] = {
    "characteristic": 2,
    "modulus_coefficients": [1, 1, 1],
    "generator": "a",
}
_ROWS: dict[str, object] = {"name": "b", "labels": ["b1", "b2"]}
_IMAGE: dict[str, object] = {"name": "image", "labels": ["y1"]}
_BASIS_AXIS: dict[str, object] = {"name": "basis", "labels": ["B1"]}


def _element(first: int, second: int) -> dict[str, object]:
    return {"presentation": _FIELD, "coordinates": [first, second]}


def _direction(first: tuple[int, int], second: tuple[int, int]) -> dict[str, object]:
    return {
        "presentation": _FIELD,
        "axis": _ROWS,
        "coordinates": [_element(*first), _element(*second)],
    }


_ZERO = _element(0, 0)
_ONE = _element(1, 0)
_SUBSPACE: dict[str, object] = {
    "presentation": _FIELD,
    "basis_axis": _BASIS_AXIS,
    "basis": [
        {
            "presentation": _FIELD,
            "row_axis": _ROWS,
            "column_axis": _IMAGE,
            "entries": [[_ONE], [_ZERO]],
        }
    ],
}
_DIRECTIONS = (
    _direction((0, 0), (1, 0)),
    _direction((1, 0), (0, 0)),
    _direction((1, 0), (1, 0)),
    _direction((1, 0), (0, 1)),
    _direction((1, 0), (1, 1)),
)
_PROJECTIVE_LINE: dict[str, object] = {
    "presentation": _FIELD,
    "axis": _ROWS,
    "points": list(_DIRECTIONS),
}


def _linear_map(rank: int) -> dict[str, object]:
    return {
        "source_axis": _BASIS_AXIS,
        "target_axis": {"name": "Res(image)", "labels": ["y1:1", "y1:a"]},
        "matrix": {"prime": 2, "entries": [[rank], [0]], "columns": 1},
    }


_LINEAR_MAPS = tuple(_linear_map(rank) for rank in (0, 1, 1, 1, 1))
_LEDGER: dict[str, object] = {
    "subspace": _SUBSPACE,
    "entries": [
        {"direction": direction, "linear_map": linear_map, "rank": rank}
        for direction, linear_map, rank in zip(
            _DIRECTIONS, _LINEAR_MAPS, (0, 1, 1, 1, 1), strict=True
        )
    ],
}
_POLYNOMIAL_MAP: dict[str, object] = {
    "domain": _FIELD,
    "codomain": _FIELD,
    "polynomial": {
        "presentation": _FIELD,
        "variable": "x",
        "coefficients": [_ZERO, _ZERO, _ZERO, _ONE],
    },
}
_TABLE: dict[str, object] = {
    "map": _POLYNOMIAL_MAP,
    "entries": [
        [_element(0, 0), _element(0, 0)],
        [_element(1, 0), _element(1, 0)],
        [_element(0, 1), _element(1, 0)],
        [_element(1, 1), _element(1, 0)],
    ],
}


def _enumerate_projective_line(request: ProjectiveLineRequest) -> ProjectiveLine:
    return projective_line(request.presentation, request.axis)


def _restrict(request: RestrictScalarsRequest) -> FiniteLinearMap:
    return restrict_scalars(request.subspace, request.direction)


def _rank(request: LinearMapRankRequest) -> RankResult:
    return linear_map_rank(request.subspace, request.direction)


def _finite_map_table(request: FiniteMapTableRequest) -> FiniteMapTable:
    return finite_map_table(request.polynomial_map)


def finite_field_operations() -> MathTools:
    projective_line_operation = MathTool(
        operation_id="finite_field.projective_line.enumerate",
        request_type=ProjectiveLineRequest,
        result_type=ProjectiveLine,
        run=_enumerate_projective_line,
        title="Enumerate an exact finite projective line",
        description="Return every normalized direction in deterministic order.",
        tags=("finite-field", "projective"),
        examples=(
            example(
                "projective_line_over_gf_four",
                "Enumerate the projective line on a two-coordinate GF(4) axis.",
                {"presentation": _FIELD, "axis": _ROWS},
            ),
        ),
    )
    restrict_operation = MathTool(
        operation_id="finite_field.restrict_scalars.compute",
        request_type=RestrictScalarsRequest,
        result_type=FiniteLinearMap,
        run=_restrict,
        title="Restrict a finite-field matrix action to its prime field",
        description="Construct the exact prime-field map B -> B^T b.",
        tags=("finite-field", "linear-map", "restriction-of-scalars"),
        examples=(
            example(
                "one_basis_vector",
                "Restrict a one-vector GF(4) subspace along one projective direction.",
                {"subspace": _SUBSPACE, "direction": _DIRECTIONS[0]},
            ),
        ),
    )
    rank_operation = MathTool(
        operation_id="finite_field.linear_map.rank.compute",
        request_type=LinearMapRankRequest,
        result_type=RankResult,
        run=_rank,
        title="Compute finite linear-map rank over the prime field",
        description="Return the exact rank bound to its direction and map.",
        tags=("finite-field", "linear-map", "rank", "exact"),
        examples=(
            example(
                "restricted_map_rank",
                "Compute the rank of a restricted GF(4) map over GF(2).",
                {"subspace": _SUBSPACE, "direction": _DIRECTIONS[0]},
            ),
        ),
    )
    table_operation = MathTool(
        operation_id="finite_field.polynomial_map.table.compute",
        request_type=FiniteMapTableRequest,
        result_type=FiniteMapTable,
        run=_finite_map_table,
        title="Evaluate a polynomial on its complete finite field",
        description="Return the exact domain-bound map table in canonical order.",
        tags=("finite-field", "polynomial", "map-table", "exact"),
        examples=(
            example(
                "cubic_map_over_gf_four",
                "Evaluate x³ on every element of GF(4).",
                {"polynomial_map": _POLYNOMIAL_MAP},
            ),
        ),
    )
    return (
        projective_line_operation,
        restrict_operation,
        rank_operation,
        table_operation,
    )


__all__ = ["finite_field_operations"]
